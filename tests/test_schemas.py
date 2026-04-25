"""Tests for Pydantic schemas — validation, enums, constraints."""

import pytest
from pydantic import ValidationError
from src.models.schemas import (
    Severity, Language, ReviewFinding, CodeReviewRequest,
    CodeReviewResponse, DiffReviewRequest, DiffReviewResponse,
    HealthResponse,
)
from datetime import datetime


class TestSeverityEnum:
    def test_all_values(self):
        assert Severity.CRITICAL == "critical"
        assert Severity.HIGH == "high"
        assert Severity.MEDIUM == "medium"
        assert Severity.LOW == "low"
        assert Severity.INFO == "info"

    def test_severity_count(self):
        assert len(Severity) == 5


class TestLanguageEnum:
    def test_all_values(self):
        assert Language.PYTHON == "python"
        assert Language.JAVASCRIPT == "javascript"
        assert Language.TYPESCRIPT == "typescript"
        assert Language.GO == "go"
        assert Language.JAVA == "java"
        assert Language.RUST == "rust"
        assert Language.CPP == "cpp"
        assert Language.AUTO == "auto"

    def test_language_count(self):
        assert len(Language) == 8


class TestReviewFinding:
    def test_minimal_finding(self):
        f = ReviewFinding(
            severity=Severity.HIGH,
            category="security",
            title="SQL Injection",
            description="Found SQL injection",
            suggestion="Use parameterized queries",
        )
        assert f.severity == Severity.HIGH
        assert f.line is None
        assert f.file is None
        assert f.code_snippet is None
        assert f.fixed_code is None

    def test_full_finding(self):
        f = ReviewFinding(
            severity=Severity.CRITICAL,
            category="security",
            file="app.py",
            line=42,
            title="Hardcoded Key",
            description="API key in source",
            suggestion="Use env vars",
            code_snippet="key = 'abc'",
            fixed_code="key = os.getenv('KEY')",
        )
        assert f.line == 42
        assert f.file == "app.py"


class TestCodeReviewRequest:
    def test_minimal_request(self):
        req = CodeReviewRequest(code="print('hello')")
        assert req.language == Language.AUTO
        assert req.filename is None
        assert req.context is None
        assert req.focus_areas is None

    def test_full_request(self):
        req = CodeReviewRequest(
            code="def add(a, b): return a + b",
            language=Language.PYTHON,
            filename="math.py",
            context="Simple math utility",
            focus_areas=["performance", "security"],
        )
        assert req.language == Language.PYTHON
        assert len(req.focus_areas) == 2

    def test_empty_code_rejected(self):
        with pytest.raises(ValidationError):
            CodeReviewRequest(code="")

    def test_code_required(self):
        with pytest.raises(ValidationError):
            CodeReviewRequest()


class TestCodeReviewResponse:
    def test_valid_response(self):
        resp = CodeReviewResponse(
            findings=[],
            summary="Clean code.",
            score=95,
            metrics={"total": 0},
            reviewed_at=datetime.now(),
            language_detected="python",
            lines_reviewed=10,
        )
        assert resp.score == 95

    def test_score_min_boundary(self):
        resp = CodeReviewResponse(
            findings=[], summary="Bad", score=0,
            metrics={}, reviewed_at=datetime.now(),
            language_detected="python", lines_reviewed=1,
        )
        assert resp.score == 0

    def test_score_max_boundary(self):
        resp = CodeReviewResponse(
            findings=[], summary="Perfect", score=100,
            metrics={}, reviewed_at=datetime.now(),
            language_detected="python", lines_reviewed=1,
        )
        assert resp.score == 100

    def test_score_out_of_range(self):
        with pytest.raises(ValidationError):
            CodeReviewResponse(
                findings=[], summary="X", score=101,
                metrics={}, reviewed_at=datetime.now(),
                language_detected="python", lines_reviewed=1,
            )

    def test_negative_score_rejected(self):
        with pytest.raises(ValidationError):
            CodeReviewResponse(
                findings=[], summary="X", score=-1,
                metrics={}, reviewed_at=datetime.now(),
                language_detected="python", lines_reviewed=1,
            )


class TestDiffReviewRequest:
    def test_minimal_diff(self):
        req = DiffReviewRequest(diff="+ added line")
        assert req.base_branch == "main"
        assert req.pr_title is None

    def test_full_diff(self):
        req = DiffReviewRequest(
            diff="+ new code",
            base_branch="develop",
            pr_title="Fix auth bug",
            pr_description="Patches SQL injection in login",
        )
        assert req.pr_title == "Fix auth bug"

    def test_empty_diff_rejected(self):
        with pytest.raises(ValidationError):
            DiffReviewRequest(diff="")


class TestDiffReviewResponse:
    def test_valid_response(self):
        resp = DiffReviewResponse(
            findings=[],
            summary="LGTM",
            approve=True,
            approval_reason="Clean",
            risk_level=Severity.LOW,
            files_reviewed=2,
            additions_reviewed=10,
            deletions_reviewed=3,
        )
        assert resp.approve is True


class TestHealthResponse:
    def test_defaults(self):
        h = HealthResponse()
        assert h.status == "ok"
        assert h.version == "1.0.0"

    def test_custom_values(self):
        h = HealthResponse(status="ok", version="2.0.0", provider="gemini")
        assert h.provider == "gemini"
