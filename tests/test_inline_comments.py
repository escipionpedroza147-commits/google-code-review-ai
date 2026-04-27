"""Tests for inline code review comments — generation, suggestions, and endpoint."""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.core.inline_comments import (
    InlineComment,
    generate_inline_comments,
    summarize_inline_comments,
)
from src.models.schemas import Language, Severity


@pytest.fixture
def client():
    return TestClient(app)


# ── InlineComment Model ────────────────────────────────────────────

class TestInlineComment:
    def test_basic_creation(self):
        c = InlineComment(
            line=5,
            severity=Severity.HIGH,
            category="security",
            message="Issue found",
        )
        assert c.line == 5
        assert c.end_line == 5
        assert c.severity == Severity.HIGH
        assert c.suggestion is None
        assert c.fix is None

    def test_with_suggestion_and_fix(self):
        c = InlineComment(
            line=10,
            severity=Severity.LOW,
            category="style",
            message="Use const",
            suggestion="Replace var with const",
            fix="const x = 1;",
        )
        assert c.suggestion == "Replace var with const"
        assert c.fix == "const x = 1;"

    def test_multiline_comment(self):
        c = InlineComment(
            line=1,
            severity=Severity.MEDIUM,
            category="logic",
            message="Complex block",
            end_line=5,
        )
        assert c.end_line == 5

    def test_to_dict(self):
        c = InlineComment(
            line=3,
            severity=Severity.INFO,
            category="style",
            message="Trailing whitespace",
        )
        d = c.to_dict()
        assert d["line"] == 3
        assert d["severity"] == "info"
        assert d["category"] == "style"
        assert "suggestion" not in d
        assert "fix" not in d

    def test_to_dict_with_optional_fields(self):
        c = InlineComment(
            line=7,
            severity=Severity.HIGH,
            category="security",
            message="SQL injection",
            suggestion="Use params",
            fix="cursor.execute(q, (uid,))",
        )
        d = c.to_dict()
        assert d["suggestion"] == "Use params"
        assert d["fix"] == "cursor.execute(q, (uid,))"


# ── generate_inline_comments ───────────────────────────────────────

class TestGenerateInlineComments:
    def test_clean_code_minimal_comments(self):
        code = 'def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b'
        comments = generate_inline_comments(code, Language.PYTHON)
        critical = [c for c in comments if c.severity == Severity.CRITICAL]
        assert len(critical) == 0

    def test_detects_hardcoded_secret(self):
        code = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"'
        comments = generate_inline_comments(code, Language.PYTHON)
        secrets = [c for c in comments if "secret" in c.message.lower() or "hardcoded" in c.message.lower()]
        assert len(secrets) >= 1
        assert secrets[0].severity == Severity.CRITICAL

    def test_detects_eval(self):
        code = "result = eval(user_input)"
        comments = generate_inline_comments(code, Language.PYTHON)
        evals = [c for c in comments if "eval" in c.message.lower() or "exec" in c.message.lower()]
        assert len(evals) >= 1

    def test_python_missing_type_hint(self):
        code = "def process(data):\n    return data"
        comments = generate_inline_comments(code, Language.PYTHON)
        hints = [c for c in comments if "type" in c.message.lower() and "annotation" in c.message.lower()]
        assert len(hints) >= 1
        assert hints[0].severity == Severity.INFO

    def test_python_mutable_default(self):
        code = "def append_to(item, target=[]):\n    target.append(item)\n    return target"
        comments = generate_inline_comments(code, Language.PYTHON)
        mutables = [c for c in comments if "mutable" in c.message.lower()]
        assert len(mutables) >= 1
        assert mutables[0].severity == Severity.HIGH

    def test_auto_language_detection(self):
        code = "import os\ndef main():\n    print('hello')"
        comments = generate_inline_comments(code, Language.AUTO)
        # Should detect Python and run Python-specific checks
        assert isinstance(comments, list)

    def test_with_filename_detection(self):
        code = "const x = 1;"
        comments = generate_inline_comments(code, Language.AUTO, filename="app.js")
        assert isinstance(comments, list)

    def test_comments_sorted_by_line(self):
        code = "eval(x)\n" * 3 + "y = 1\n" + "eval(z)\n"
        comments = generate_inline_comments(code, Language.PYTHON)
        for i in range(len(comments) - 1):
            assert comments[i].line <= comments[i + 1].line

    def test_no_duplicate_comments(self):
        code = 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"'
        comments = generate_inline_comments(code, Language.PYTHON)
        keys = [(c.line, c.message[:50]) for c in comments]
        assert len(keys) == len(set(keys))

    def test_js_var_detection(self):
        code = "var x = 5;\nvar y = 10;"
        comments = generate_inline_comments(code, Language.JAVASCRIPT)
        var_issues = [c for c in comments if "var" in c.message.lower()]
        assert len(var_issues) >= 1

    def test_js_loose_equality(self):
        code = "if (x == null) { return; }"
        comments = generate_inline_comments(code, Language.JAVASCRIPT)
        eq_issues = [c for c in comments if "==" in c.message or "equality" in c.message.lower()]
        assert len(eq_issues) >= 1

    def test_long_line_detection(self):
        code = "x = " + "a" * 200
        comments = generate_inline_comments(code, Language.PYTHON)
        long_lines = [c for c in comments if "character" in c.message.lower()]
        assert len(long_lines) >= 1


# ── summarize_inline_comments ──────────────────────────────────────

class TestSummarizeInlineComments:
    def test_empty_summary(self):
        summary = summarize_inline_comments([])
        assert summary["total_comments"] == 0
        assert summary["by_severity"] == {}
        assert summary["by_category"] == {}

    def test_severity_counts(self):
        comments = [
            InlineComment(line=1, severity=Severity.HIGH, category="security", message="A"),
            InlineComment(line=2, severity=Severity.HIGH, category="logic", message="B"),
            InlineComment(line=3, severity=Severity.LOW, category="style", message="C"),
        ]
        summary = summarize_inline_comments(comments)
        assert summary["total_comments"] == 3
        assert summary["by_severity"]["high"] == 2
        assert summary["by_severity"]["low"] == 1

    def test_category_counts(self):
        comments = [
            InlineComment(line=1, severity=Severity.MEDIUM, category="security", message="A"),
            InlineComment(line=2, severity=Severity.LOW, category="security", message="B"),
            InlineComment(line=3, severity=Severity.INFO, category="style", message="C"),
        ]
        summary = summarize_inline_comments(comments)
        assert summary["by_category"]["security"] == 2
        assert summary["by_category"]["style"] == 1


# ── API Endpoint ───────────────────────────────────────────────────

class TestInlineReviewEndpoint:
    def test_inline_review_clean_code(self, client):
        resp = client.post("/api/v1/review/inline", json={
            "code": 'def add(a: int, b: int) -> int:\n    """Add two numbers."""\n    return a + b'
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "comments" in data
        assert "summary" in data
        assert "score" in data
        assert "language_detected" in data
        assert "total_comments" in data
        assert data["lines_reviewed"] == 3

    def test_inline_review_with_issues(self, client):
        resp = client.post("/api/v1/review/inline", json={
            "code": 'api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"\nresult = eval(user_input)',
            "language": "python",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_comments"] >= 2
        assert data["score"] < 100

    def test_inline_review_with_filename(self, client):
        resp = client.post("/api/v1/review/inline", json={
            "code": "var x = 5;",
            "filename": "app.js",
        })
        assert resp.status_code == 200
        assert resp.json()["language_detected"] == "javascript"

    def test_inline_review_empty_code_rejected(self, client):
        resp = client.post("/api/v1/review/inline", json={"code": ""})
        assert resp.status_code == 422

    def test_inline_review_response_structure(self, client):
        resp = client.post("/api/v1/review/inline", json={
            "code": "x = 1",
        })
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["comments"], list)
        assert isinstance(data["summary"], dict)
        assert isinstance(data["score"], int)
        assert 0 <= data["score"] <= 100

    def test_inline_comment_has_required_fields(self, client):
        resp = client.post("/api/v1/review/inline", json={
            "code": 'token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij"',
            "language": "python",
        })
        assert resp.status_code == 200
        data = resp.json()
        if data["comments"]:
            comment = data["comments"][0]
            assert "line" in comment
            assert "severity" in comment
            assert "category" in comment
            assert "message" in comment
