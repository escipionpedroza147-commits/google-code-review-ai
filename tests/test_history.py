"""Tests for review history and analytics — storage, retrieval, and endpoints."""

import pytest
from unittest.mock import AsyncMock, patch
from datetime import datetime
from fastapi.testclient import TestClient

from main import app
from src.services.history_service import ReviewHistoryStore, ReviewRecord, ReviewAnalytics


@pytest.fixture
def client():
    return TestClient(app)


@pytest.fixture
def store():
    """Fresh history store for each test."""
    return ReviewHistoryStore()


# ── ReviewHistoryStore ─────────────────────────────────────────────

class TestReviewHistoryStore:
    def test_empty_store(self, store):
        assert store.count == 0
        assert store.get_history() == []

    def test_log_review(self, store):
        record = store.log_review(
            review_type="code",
            language="python",
            score=85,
            finding_count=3,
            findings_by_severity={"high": 1, "medium": 2},
            categories=["security", "quality"],
            lines_reviewed=100,
        )
        assert record.id == "rev-000001"
        assert record.review_type == "code"
        assert record.language == "python"
        assert record.score == 85
        assert store.count == 1

    def test_log_multiple_reviews(self, store):
        for i in range(5):
            store.log_review(
                review_type="code",
                language="python",
                score=80 + i,
                finding_count=i,
                findings_by_severity={},
                categories=[],
                lines_reviewed=50,
            )
        assert store.count == 5

    def test_log_review_with_filename(self, store):
        record = store.log_review(
            review_type="code",
            language="javascript",
            score=90,
            finding_count=1,
            findings_by_severity={"low": 1},
            categories=["style"],
            lines_reviewed=30,
            filename="app.js",
        )
        assert record.filename == "app.js"

    def test_auto_incrementing_ids(self, store):
        r1 = store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        r2 = store.log_review(
            review_type="diff", language="python", score=0,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=20,
        )
        assert r1.id == "rev-000001"
        assert r2.id == "rev-000002"

    def test_timestamp_set(self, store):
        record = store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        assert isinstance(record.timestamp, datetime)


# ── History Retrieval ──────────────────────────────────────────────

class TestHistoryRetrieval:
    def test_get_history_default(self, store):
        for i in range(3):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=0, findings_by_severity={},
                categories=[], lines_reviewed=10,
            )
        history = store.get_history()
        assert len(history) == 3
        # Most recent first
        assert history[0].id == "rev-000003"

    def test_get_history_with_limit(self, store):
        for i in range(10):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=0, findings_by_severity={},
                categories=[], lines_reviewed=10,
            )
        history = store.get_history(limit=3)
        assert len(history) == 3

    def test_get_history_with_offset(self, store):
        for i in range(5):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=0, findings_by_severity={},
                categories=[], lines_reviewed=10,
            )
        history = store.get_history(limit=2, offset=2)
        assert len(history) == 2
        assert history[0].id == "rev-000003"

    def test_filter_by_review_type(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        store.log_review(
            review_type="diff", language="python", score=0,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=20,
        )
        store.log_review(
            review_type="code", language="javascript", score=90,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=15,
        )
        code_reviews = store.get_history(review_type="code")
        assert len(code_reviews) == 2
        diff_reviews = store.get_history(review_type="diff")
        assert len(diff_reviews) == 1

    def test_filter_by_language(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        store.log_review(
            review_type="code", language="javascript", score=90,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=15,
        )
        py_reviews = store.get_history(language="python")
        assert len(py_reviews) == 1
        assert py_reviews[0].language == "python"


# ── Analytics ──────────────────────────────────────────────────────

class TestAnalytics:
    def test_empty_analytics(self, store):
        analytics = store.get_analytics()
        assert analytics.total_reviews == 0
        assert analytics.avg_score == 0.0
        assert analytics.most_common_issues == []

    def test_analytics_total_reviews(self, store):
        for i in range(5):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=2, findings_by_severity={"high": 1, "low": 1},
                categories=["security", "style"], lines_reviewed=50,
            )
        analytics = store.get_analytics()
        assert analytics.total_reviews == 5

    def test_analytics_by_type(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        store.log_review(
            review_type="diff", language="python", score=0,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=20,
        )
        store.log_review(
            review_type="code", language="python", score=90,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=30,
        )
        analytics = store.get_analytics()
        assert analytics.reviews_by_type["code"] == 2
        assert analytics.reviews_by_type["diff"] == 1

    def test_analytics_by_language(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        store.log_review(
            review_type="code", language="javascript", score=90,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=15,
        )
        store.log_review(
            review_type="code", language="python", score=70,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=20,
        )
        analytics = store.get_analytics()
        assert analytics.reviews_by_language["python"] == 2
        assert analytics.reviews_by_language["javascript"] == 1

    def test_analytics_avg_score(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=10,
        )
        store.log_review(
            review_type="code", language="python", score=90,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=20,
        )
        analytics = store.get_analytics()
        assert analytics.avg_score == 85.0

    def test_analytics_avg_findings(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=4, findings_by_severity={"high": 4},
            categories=["security"], lines_reviewed=10,
        )
        store.log_review(
            review_type="code", language="python", score=90,
            finding_count=2, findings_by_severity={"low": 2},
            categories=["style"], lines_reviewed=20,
        )
        analytics = store.get_analytics()
        assert analytics.avg_findings_per_review == 3.0

    def test_analytics_most_common_issues(self, store):
        for _ in range(5):
            store.log_review(
                review_type="code", language="python", score=70,
                finding_count=2,
                findings_by_severity={"high": 1, "medium": 1},
                categories=["security", "quality"],
                lines_reviewed=50,
            )
        for _ in range(3):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=1,
                findings_by_severity={"low": 1},
                categories=["style"],
                lines_reviewed=30,
            )
        analytics = store.get_analytics()
        assert len(analytics.most_common_issues) >= 1
        # security appeared 5 times, style 3 times
        top_issue = analytics.most_common_issues[0]
        assert top_issue["category"] == "security"
        assert top_issue["count"] == 5

    def test_analytics_severity_distribution(self, store):
        store.log_review(
            review_type="code", language="python", score=60,
            finding_count=3,
            findings_by_severity={"critical": 1, "high": 2},
            categories=["security"],
            lines_reviewed=50,
        )
        analytics = store.get_analytics()
        assert analytics.severity_distribution["critical"] == 1
        assert analytics.severity_distribution["high"] == 2

    def test_analytics_total_lines(self, store):
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=100,
        )
        store.log_review(
            review_type="code", language="python", score=80,
            finding_count=0, findings_by_severity={},
            categories=[], lines_reviewed=200,
        )
        analytics = store.get_analytics()
        assert analytics.total_lines_reviewed == 300

    def test_analytics_recent_reviews(self, store):
        for i in range(15):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=0, findings_by_severity={},
                categories=[], lines_reviewed=10,
            )
        analytics = store.get_analytics()
        assert len(analytics.recent_reviews) == 10  # Capped at 10


# ── Clear History ──────────────────────────────────────────────────

class TestClearHistory:
    def test_clear_empty_store(self, store):
        count = store.clear()
        assert count == 0
        assert store.count == 0

    def test_clear_with_records(self, store):
        for i in range(5):
            store.log_review(
                review_type="code", language="python", score=80,
                finding_count=0, findings_by_severity={},
                categories=[], lines_reviewed=10,
            )
        count = store.clear()
        assert count == 5
        assert store.count == 0


# ── ReviewRecord Model ─────────────────────────────────────────────

class TestReviewRecord:
    def test_valid_record(self):
        record = ReviewRecord(
            id="rev-000001",
            review_type="code",
            language="python",
            score=85,
            finding_count=3,
            findings_by_severity={"high": 1, "medium": 2},
            categories=["security"],
            lines_reviewed=100,
            timestamp=datetime.now(),
        )
        assert record.id == "rev-000001"
        assert record.score == 85

    def test_record_serialization(self):
        record = ReviewRecord(
            id="rev-000001",
            review_type="code",
            language="python",
            score=85,
            finding_count=3,
            findings_by_severity={},
            categories=[],
            lines_reviewed=50,
            timestamp=datetime.now(),
        )
        data = record.model_dump()
        assert data["id"] == "rev-000001"
        assert data["review_type"] == "code"


# ── API Endpoints ──────────────────────────────────────────────────

class TestHistoryEndpoint:
    def test_history_returns_ok(self, client):
        resp = client.get("/api/v1/history")
        assert resp.status_code == 200
        data = resp.json()
        assert "records" in data
        assert "total" in data
        assert "limit" in data
        assert "offset" in data

    def test_history_with_filters(self, client):
        resp = client.get("/api/v1/history?review_type=code&language=python&limit=10&offset=0")
        assert resp.status_code == 200


class TestAnalyticsEndpoint:
    def test_analytics_returns_ok(self, client):
        resp = client.get("/api/v1/analytics")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reviews" in data
        assert "reviews_by_type" in data
        assert "reviews_by_language" in data
        assert "avg_score" in data
        assert "avg_findings_per_review" in data
        assert "most_common_issues" in data
        assert "severity_distribution" in data
        assert "total_lines_reviewed" in data

    def test_analytics_after_static_analysis(self, client):
        # Do a static analysis to populate history
        client.post("/api/v1/analyze/static", json={
            "code": "def add(a, b): return a + b"
        })
        resp = client.get("/api/v1/analytics")
        assert resp.status_code == 200
