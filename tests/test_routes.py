"""Tests for API routes — all endpoints via TestClient."""

import hashlib
import hmac
import json
import pytest
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from datetime import datetime

from main import app
from src.models.schemas import (
    CodeReviewResponse, DiffReviewResponse, ReviewFinding, Severity,
)


@pytest.fixture
def client():
    return TestClient(app)


# ── Health ──────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/api/v1/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert "version" in data

    def test_health_has_provider(self, client):
        resp = client.get("/api/v1/health")
        data = resp.json()
        assert "provider" in data


# ── Stats ───────────────────────────────────────────────────────────

class TestStatsEndpoint:
    def test_stats_returns_ok(self, client):
        resp = client.get("/api/v1/stats")
        assert resp.status_code == 200
        data = resp.json()
        assert "total_reviews" in data
        assert "started_at" in data

    def test_stats_has_all_fields(self, client):
        resp = client.get("/api/v1/stats")
        data = resp.json()
        for key in ["total_reviews", "code_reviews", "diff_reviews", "static_analyses", "webhook_events", "average_score"]:
            assert key in data


# ── Static Analysis ────────────────────────────────────────────────

class TestStaticAnalysisEndpoint:
    def test_static_analysis_clean_code(self, client):
        resp = client.post("/api/v1/analyze/static", json={
            "code": "def add(a: int, b: int) -> int:\n    return a + b"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "findings" in data
        assert "score" in data
        assert "language_detected" in data

    def test_static_analysis_finds_secrets(self, client):
        resp = client.post("/api/v1/analyze/static", json={
            "code": 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"',
            "language": "python",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["finding_count"] >= 1

    def test_static_analysis_with_filename(self, client):
        resp = client.post("/api/v1/analyze/static", json={
            "code": "const x = 1;",
            "filename": "app.js",
        })
        assert resp.status_code == 200
        assert resp.json()["language_detected"] == "javascript"

    def test_static_analysis_empty_code_rejected(self, client):
        resp = client.post("/api/v1/analyze/static", json={"code": ""})
        assert resp.status_code == 422

    def test_static_analysis_no_body_rejected(self, client):
        resp = client.post("/api/v1/analyze/static")
        assert resp.status_code == 422


# ── Code Review ────────────────────────────────────────────────────

class TestCodeReviewEndpoint:
    @patch("src.api.routes.review_code", new_callable=AsyncMock)
    def test_code_review_success(self, mock_review, client):
        mock_review.return_value = CodeReviewResponse(
            findings=[],
            summary="Clean code.",
            score=95,
            metrics={"total_findings": 0},
            reviewed_at=datetime.now(),
            language_detected="python",
            lines_reviewed=5,
        )
        resp = client.post("/api/v1/review/code", json={
            "code": "def hello(): pass"
        })
        assert resp.status_code == 200
        assert resp.json()["score"] == 95

    @patch("src.api.routes.review_code", new_callable=AsyncMock)
    def test_code_review_with_findings(self, mock_review, client):
        mock_review.return_value = CodeReviewResponse(
            findings=[ReviewFinding(
                severity=Severity.HIGH,
                category="security",
                title="Issue",
                description="Found issue",
                suggestion="Fix it",
            )],
            summary="Issues found.",
            score=60,
            metrics={"total_findings": 1},
            reviewed_at=datetime.now(),
            language_detected="python",
            lines_reviewed=10,
        )
        resp = client.post("/api/v1/review/code", json={
            "code": "eval(input())",
            "language": "python",
        })
        assert resp.status_code == 200
        assert len(resp.json()["findings"]) == 1

    def test_code_review_empty_code_rejected(self, client):
        resp = client.post("/api/v1/review/code", json={"code": ""})
        assert resp.status_code == 422

    @patch("src.api.routes.review_code", new_callable=AsyncMock)
    def test_code_review_error_returns_500(self, mock_review, client):
        mock_review.side_effect = Exception("AI provider down")
        resp = client.post("/api/v1/review/code", json={
            "code": "x = 1"
        })
        assert resp.status_code == 500


# ── Diff Review ────────────────────────────────────────────────────

class TestDiffReviewEndpoint:
    @patch("src.api.routes.review_diff", new_callable=AsyncMock)
    def test_diff_review_approve(self, mock_review, client):
        mock_review.return_value = DiffReviewResponse(
            findings=[],
            summary="LGTM",
            approve=True,
            approval_reason="Clean diff",
            risk_level=Severity.LOW,
            files_reviewed=1,
            additions_reviewed=5,
            deletions_reviewed=2,
        )
        resp = client.post("/api/v1/review/diff", json={
            "diff": "+ new line\n- old line"
        })
        assert resp.status_code == 200
        assert resp.json()["approve"] is True

    @patch("src.api.routes.review_diff", new_callable=AsyncMock)
    def test_diff_review_reject(self, mock_review, client):
        mock_review.return_value = DiffReviewResponse(
            findings=[ReviewFinding(
                severity=Severity.CRITICAL,
                category="security",
                title="SQL Injection",
                description="New code introduces SQL injection",
                suggestion="Use params",
            )],
            summary="Critical issues",
            approve=False,
            approval_reason="Critical security issue",
            risk_level=Severity.CRITICAL,
            files_reviewed=1,
            additions_reviewed=10,
            deletions_reviewed=0,
        )
        resp = client.post("/api/v1/review/diff", json={
            "diff": "+ query = f'SELECT * FROM users WHERE id = {uid}'",
            "pr_title": "Add user lookup",
        })
        assert resp.status_code == 200
        assert resp.json()["approve"] is False

    def test_diff_review_empty_diff_rejected(self, client):
        resp = client.post("/api/v1/review/diff", json={"diff": ""})
        assert resp.status_code == 422


# ── GitHub Webhook ──────────────────────────────────────────────────

class TestGitHubWebhook:
    def test_webhook_no_secret_configured(self, client):
        resp = client.post("/api/v1/webhook/github", json={})
        assert resp.status_code == 500

    @patch("src.api.routes.settings")
    def test_webhook_missing_signature(self, mock_settings, client):
        mock_settings.github_webhook_secret = "test-secret"
        resp = client.post(
            "/api/v1/webhook/github",
            json={"action": "opened"},
        )
        assert resp.status_code == 401

    @patch("src.api.routes.settings")
    def test_webhook_invalid_signature(self, mock_settings, client):
        mock_settings.github_webhook_secret = "test-secret"
        resp = client.post(
            "/api/v1/webhook/github",
            json={"action": "opened"},
            headers={"X-Hub-Signature-256": "sha256=invalid", "X-GitHub-Event": "pull_request"},
        )
        assert resp.status_code == 401

    @patch("src.api.routes.settings")
    def test_webhook_valid_pr_event(self, mock_settings, client):
        secret = "test-secret"
        mock_settings.github_webhook_secret = secret
        payload = {"action": "opened", "pull_request": {"number": 42, "title": "Fix bug"}}
        body = json.dumps(payload).encode()
        sig = "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()

        resp = client.post(
            "/api/v1/webhook/github",
            content=body,
            headers={
                "X-Hub-Signature-256": sig,
                "X-GitHub-Event": "pull_request",
                "Content-Type": "application/json",
            },
        )
        assert resp.status_code == 200
        assert resp.json()["status"] == "accepted"
        assert resp.json()["pr_number"] == 42


# ── 404 ─────────────────────────────────────────────────────────────

class TestNotFound:
    def test_unknown_route(self, client):
        resp = client.get("/api/v1/nonexistent")
        assert resp.status_code in (404, 405)
