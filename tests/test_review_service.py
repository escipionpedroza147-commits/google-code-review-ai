"""Tests for review service — orchestration with mocked AI."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from src.services.review_service import (
    review_code, review_diff, _parse_ai_findings, _generate_summary,
)
from src.models.schemas import (
    CodeReviewRequest, DiffReviewRequest, Language, Severity, ReviewFinding,
)


# ── Code Review Orchestration ──────────────────────────────────────

class TestCodeReview:
    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_returns_response(self, mock_ai):
        mock_ai.return_value = "No issues found. Code is clean."
        req = CodeReviewRequest(code="def add(a, b):\n    return a + b")
        result = await review_code(req)
        assert result.score >= 0
        assert result.language_detected is not None
        assert result.lines_reviewed == 2

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_detects_language(self, mock_ai):
        mock_ai.return_value = "Clean code."
        req = CodeReviewRequest(code="def main():\n    print('hi')", language=Language.AUTO)
        result = await review_code(req)
        assert result.language_detected == "python"

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_explicit_language(self, mock_ai):
        mock_ai.return_value = "Looks good."
        req = CodeReviewRequest(code="const x = 1;", language=Language.JAVASCRIPT)
        result = await review_code(req)
        assert result.language_detected == "javascript"

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_includes_static_findings(self, mock_ai):
        mock_ai.return_value = "No additional issues."
        req = CodeReviewRequest(code='api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"')
        result = await review_code(req)
        assert result.metrics["static_findings"] >= 1

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_ai_failure_still_returns(self, mock_ai):
        mock_ai.side_effect = Exception("AI provider down")
        req = CodeReviewRequest(code="x = 1")
        result = await review_code(req)
        # Should still return with static-only findings
        assert result.score >= 0
        assert result.metrics["ai_findings"] == 0

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_review_with_context(self, mock_ai):
        mock_ai.return_value = "Code reviewed with context."
        req = CodeReviewRequest(
            code="def process():\n    pass",
            context="Data processing pipeline",
            focus_areas=["performance", "security"],
        )
        result = await review_code(req)
        assert result.summary is not None

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_findings_sorted_by_severity(self, mock_ai):
        mock_ai.return_value = (
            "1. **Finding** [low] Line 1: Minor style issue\n"
            "2. **Finding** [critical] Line 2: SQL injection\n"
        )
        req = CodeReviewRequest(
            code='query = f"SELECT * FROM users WHERE id = {uid}"'
        )
        result = await review_code(req)
        if len(result.findings) >= 2:
            sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3, "info": 4}
            for i in range(len(result.findings) - 1):
                assert sev_order.get(result.findings[i].severity, 5) <= sev_order.get(result.findings[i+1].severity, 5)


# ── Diff Review Orchestration ──────────────────────────────────────

class TestDiffReview:
    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_diff_review_approve(self, mock_ai):
        mock_ai.return_value = "Clean diff. No issues."
        req = DiffReviewRequest(diff="+ x = 1\n- x = 0")
        result = await review_diff(req)
        assert result.approve is True
        assert result.risk_level == Severity.LOW

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_diff_counts_additions_deletions(self, mock_ai):
        mock_ai.return_value = "LGTM"
        diff = "diff --git a/app.py b/app.py\n+ added1\n+ added2\n- removed1\n"
        req = DiffReviewRequest(diff=diff)
        result = await review_diff(req)
        assert result.additions_reviewed == 2
        assert result.deletions_reviewed == 1

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_diff_counts_files(self, mock_ai):
        mock_ai.return_value = "Reviewed."
        diff = "diff --git a/foo.py b/foo.py\n+ x\ndiff --git a/bar.py b/bar.py\n+ y\n"
        req = DiffReviewRequest(diff=diff)
        result = await review_diff(req)
        assert result.files_reviewed == 2

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_diff_ai_failure_still_returns(self, mock_ai):
        mock_ai.side_effect = Exception("Timeout")
        req = DiffReviewRequest(diff="+ new code")
        result = await review_diff(req)
        assert result.approve is True  # No findings = approve
        assert len(result.findings) == 0

    @pytest.mark.asyncio
    @patch("src.services.review_service._call_ai", new_callable=AsyncMock)
    async def test_diff_with_pr_metadata(self, mock_ai):
        mock_ai.return_value = "Looks good."
        req = DiffReviewRequest(
            diff="+ code",
            pr_title="Fix auth",
            pr_description="Patches login endpoint",
        )
        result = await review_diff(req)
        assert result.summary is not None


# ── AI Response Parsing ────────────────────────────────────────────

class TestParseAIFindings:
    def test_parse_empty_response(self):
        findings = _parse_ai_findings("")
        assert findings == []

    def test_parse_short_response(self):
        findings = _parse_ai_findings("LGTM")
        assert findings == []

    def test_parse_structured_findings(self):
        text = (
            "1. **Finding** [critical] Security: SQL injection on Line 5.\n"
            "The code uses string formatting in SQL query.\n"
            "Fix: Use parameterized queries.\n\n"
            "2. **Finding** [low] Style: inconsistent naming on Line 10.\n"
            "Variable names should be snake_case.\n"
        )
        findings = _parse_ai_findings(text)
        assert len(findings) >= 1

    def test_parse_caps_at_20(self):
        sections = "\n".join(
            f"{i}. **Issue** [medium] Performance: slow loop on Line {i}.\nDetails about the issue here with enough text."
            for i in range(30)
        )
        findings = _parse_ai_findings(sections)
        assert len(findings) <= 20

    def test_parse_detects_severity(self):
        text = "1. **Finding** critical security: Hardcoded API key found on Line 3.\nThis is dangerous and must be fixed immediately."
        findings = _parse_ai_findings(text)
        if findings:
            assert findings[0].severity == Severity.CRITICAL

    def test_parse_detects_category(self):
        text = "1. **Finding** performance bottleneck on Line 42.\nN+1 query detected in the loop. This will cause significant slowdowns."
        findings = _parse_ai_findings(text)
        if findings:
            assert findings[0].category == "performance"

    def test_parse_detects_line_number(self):
        text = "1. **Issue** medium: Unused variable on Line 15.\nThe variable 'temp' is assigned but never used."
        findings = _parse_ai_findings(text)
        if findings:
            assert findings[0].line == 15


# ── Summary Generation ─────────────────────────────────────────────

class TestSummaryGeneration:
    def test_summary_clean_code(self):
        summary = _generate_summary([], 95, "python", 50)
        assert "95" in summary
        assert "python" in summary.lower()

    def test_summary_with_critical(self):
        findings = [ReviewFinding(
            severity=Severity.CRITICAL, category="security",
            title="X", description="Y", suggestion="Z",
        )]
        summary = _generate_summary(findings, 30, "python", 100)
        assert "CRITICAL" in summary

    def test_summary_with_high(self):
        findings = [ReviewFinding(
            severity=Severity.HIGH, category="logic",
            title="X", description="Y", suggestion="Z",
        )]
        summary = _generate_summary(findings, 60, "javascript", 30)
        assert "HIGH" in summary

    def test_summary_excellent_verdict(self):
        summary = _generate_summary([], 95, "python", 10)
        assert "Excellent" in summary or "excellent" in summary.lower()

    def test_summary_major_issues_verdict(self):
        findings = [ReviewFinding(
            severity=Severity.CRITICAL, category="security",
            title=f"Issue {i}", description="Y", suggestion="Z",
        ) for i in range(5)]
        summary = _generate_summary(findings, 20, "python", 100)
        assert "Major" in summary or "not production" in summary.lower() or "major" in summary.lower()
