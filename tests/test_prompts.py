"""Tests for prompt templates — formatting and variable substitution."""

import pytest
from src.core.prompts import SYSTEM_PROMPT, CODE_REVIEW_PROMPT, DIFF_REVIEW_PROMPT


class TestSystemPrompt:
    def test_system_prompt_exists(self):
        assert len(SYSTEM_PROMPT) > 100

    def test_mentions_security(self):
        assert "security" in SYSTEM_PROMPT.lower()

    def test_mentions_performance(self):
        assert "performance" in SYSTEM_PROMPT.lower()

    def test_mentions_impact_prioritization(self):
        assert "impact" in SYSTEM_PROMPT.lower() or "prioritize" in SYSTEM_PROMPT.lower()

    def test_mentions_line_numbers(self):
        assert "line" in SYSTEM_PROMPT.lower()


class TestCodeReviewPrompt:
    def test_has_placeholders(self):
        assert "{language}" in CODE_REVIEW_PROMPT
        assert "{code}" in CODE_REVIEW_PROMPT
        assert "{static_findings}" in CODE_REVIEW_PROMPT
        assert "{focus_areas}" in CODE_REVIEW_PROMPT

    def test_format_succeeds(self):
        result = CODE_REVIEW_PROMPT.format(
            language="python",
            code="def foo(): pass",
            context_section="Context: test module",
            static_findings="None detected.",
            focus_areas="security, performance",
        )
        assert "python" in result
        assert "def foo(): pass" in result
        assert "security, performance" in result

    def test_format_with_empty_context(self):
        result = CODE_REVIEW_PROMPT.format(
            language="go",
            code="func main() {}",
            context_section="",
            static_findings="- [critical] Line 5: SQL injection",
            focus_areas="security",
        )
        assert "go" in result
        assert "SQL injection" in result

    def test_format_with_long_code(self):
        long_code = "x = 1\n" * 500
        result = CODE_REVIEW_PROMPT.format(
            language="python",
            code=long_code,
            context_section="",
            static_findings="None.",
            focus_areas="all",
        )
        assert "x = 1" in result


class TestDiffReviewPrompt:
    def test_has_placeholders(self):
        assert "{pr_title}" in DIFF_REVIEW_PROMPT
        assert "{diff}" in DIFF_REVIEW_PROMPT

    def test_format_succeeds(self):
        result = DIFF_REVIEW_PROMPT.format(
            pr_title="Fix auth bug",
            pr_description_section="Patches SQL injection in login",
            diff="+ sanitized = escape(input)\n- query = raw_input",
        )
        assert "Fix auth bug" in result
        assert "sanitized" in result

    def test_format_no_description(self):
        result = DIFF_REVIEW_PROMPT.format(
            pr_title="Quick fix",
            pr_description_section="",
            diff="+ x = 1",
        )
        assert "Quick fix" in result

    def test_mentions_approve(self):
        assert "APPROVE" in DIFF_REVIEW_PROMPT or "approve" in DIFF_REVIEW_PROMPT.lower()

    def test_mentions_risk(self):
        assert "risk" in DIFF_REVIEW_PROMPT.lower() or "Risk" in DIFF_REVIEW_PROMPT
