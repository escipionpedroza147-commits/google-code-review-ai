"""Inline code review comments — generates line-by-line annotations.

Provides structured inline comments with line numbers, severity levels,
and fix suggestions. Designed for IDE and GitHub PR integrations.
"""

import re
from typing import Optional

from src.core.static_analyzer import run_static_checks, detect_language, calculate_score
from src.models.schemas import Language, ReviewFinding, Severity


class InlineComment:
    """A single inline review comment anchored to a specific line."""

    def __init__(
        self,
        line: int,
        severity: Severity,
        category: str,
        message: str,
        suggestion: Optional[str] = None,
        fix: Optional[str] = None,
        end_line: Optional[int] = None,
    ) -> None:
        """Initialize an inline comment.

        Args:
            line: The 1-indexed line number this comment targets.
            severity: The severity level (info, low, medium, high, critical).
            category: Category of the issue (security, performance, etc.).
            message: Description of the issue found.
            suggestion: A human-readable suggestion for fixing the issue.
            fix: The exact replacement code to fix the issue.
            end_line: Optional end line for multi-line comments.
        """
        self.line = line
        self.end_line = end_line or line
        self.severity = severity
        self.category = category
        self.message = message
        self.suggestion = suggestion
        self.fix = fix

    def to_dict(self) -> dict:
        """Serialize the inline comment to a dictionary.

        Returns:
            Dictionary representation of the comment.
        """
        result: dict = {
            "line": self.line,
            "end_line": self.end_line,
            "severity": self.severity.value,
            "category": self.category,
            "message": self.message,
        }
        if self.suggestion:
            result["suggestion"] = self.suggestion
        if self.fix:
            result["fix"] = self.fix
        return result


def generate_inline_comments(
    code: str,
    language: Language = Language.AUTO,
    filename: Optional[str] = None,
) -> list[InlineComment]:
    """Generate inline review comments for the given source code.

    Runs static analysis and converts findings into line-anchored
    inline comments with severity, suggestions, and optional fixes.

    Args:
        code: The source code to review.
        language: Programming language (auto-detected if AUTO).
        filename: Optional filename for better language detection.

    Returns:
        List of InlineComment objects sorted by line number.
    """
    if language == Language.AUTO:
        language = detect_language(code, filename)

    findings = run_static_checks(code, language)
    lines = code.split("\n")
    comments: list[InlineComment] = []

    for finding in findings:
        line_num = finding.line or 1
        comment = InlineComment(
            line=line_num,
            severity=finding.severity,
            category=finding.category,
            message=finding.description,
            suggestion=finding.suggestion,
            fix=finding.fixed_code,
        )
        comments.append(comment)

    # Add language-specific inline suggestions
    comments.extend(_generate_python_suggestions(lines, language))
    comments.extend(_generate_js_ts_suggestions(lines, language))
    comments.extend(_generate_universal_suggestions(lines, language))

    # Deduplicate by line + message
    seen: set[tuple[int, str]] = set()
    unique_comments: list[InlineComment] = []
    for c in comments:
        key = (c.line, c.message[:50])
        if key not in seen:
            seen.add(key)
            unique_comments.append(c)

    # Sort by line number, then severity
    severity_order = {
        Severity.CRITICAL: 0,
        Severity.HIGH: 1,
        Severity.MEDIUM: 2,
        Severity.LOW: 3,
        Severity.INFO: 4,
    }
    unique_comments.sort(
        key=lambda c: (c.line, severity_order.get(c.severity, 5))
    )

    return unique_comments


def _generate_python_suggestions(
    lines: list[str], language: Language
) -> list[InlineComment]:
    """Generate Python-specific inline suggestions.

    Args:
        lines: Source code split into lines.
        language: Detected language.

    Returns:
        List of Python-specific inline comments.
    """
    if language != Language.PYTHON:
        return []

    comments: list[InlineComment] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Missing type hints on function definitions
        if re.match(r'^def \w+\(', stripped) and '->' not in stripped:
            if not stripped.startswith('def test_'):  # Skip test functions
                comments.append(InlineComment(
                    line=i + 1,
                    severity=Severity.INFO,
                    category="style",
                    message="Function missing return type annotation.",
                    suggestion="Add a return type hint, e.g., -> None or -> str.",
                ))

        # Mutable default arguments
        if re.match(r'^def \w+\(', stripped):
            if re.search(r'=\s*\[\]|=\s*\{\}|=\s*set\(\)', stripped):
                comments.append(InlineComment(
                    line=i + 1,
                    severity=Severity.HIGH,
                    category="logic",
                    message="Mutable default argument. Default mutable objects are shared across calls.",
                    suggestion="Use None as default and create the mutable inside the function body.",
                    fix="Use `= None` then `if param is None: param = []` in the body.",
                ))

        # String concatenation in loops
        if re.search(r'(\w+)\s*\+=\s*["\']', stripped) or re.search(
            r'(\w+)\s*=\s*(\w+)\s*\+\s*["\']', stripped
        ):
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.LOW,
                category="performance",
                message="String concatenation may be inefficient in a loop.",
                suggestion="Consider using list append and str.join() for better performance.",
            ))

    return comments


def _generate_js_ts_suggestions(
    lines: list[str], language: Language
) -> list[InlineComment]:
    """Generate JavaScript/TypeScript-specific inline suggestions.

    Args:
        lines: Source code split into lines.
        language: Detected language.

    Returns:
        List of JS/TS-specific inline comments.
    """
    if language not in (Language.JAVASCRIPT, Language.TYPESCRIPT):
        return []

    comments: list[InlineComment] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # var usage (should be let/const)
        if re.match(r'\bvar\s+', stripped):
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.LOW,
                category="style",
                message="Use 'let' or 'const' instead of 'var'. 'var' has function scope which can cause bugs.",
                suggestion="Replace 'var' with 'const' (if not reassigned) or 'let'.",
                fix=stripped.replace("var ", "const ", 1),
            ))

        # == instead of ===
        if re.search(r'[^=!]==[^=]', stripped) and '===' not in stripped:
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.MEDIUM,
                category="logic",
                message="Use strict equality (===) instead of loose equality (==) to avoid type coercion bugs.",
                suggestion="Replace == with === for predictable comparisons.",
            ))

        # console.log in production code
        if re.match(r'console\.log\(', stripped):
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.LOW,
                category="quality",
                message="console.log() found. Use a proper logging library for production code.",
                suggestion="Use a structured logger (winston, pino) or remove before deploy.",
            ))

    return comments


def _generate_universal_suggestions(
    lines: list[str], language: Language
) -> list[InlineComment]:
    """Generate language-agnostic inline suggestions.

    Args:
        lines: Source code split into lines.
        language: Detected language.

    Returns:
        List of universal inline comments.
    """
    comments: list[InlineComment] = []

    for i, line in enumerate(lines):
        # Very long lines
        if len(line.rstrip()) > 120:
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.INFO,
                category="style",
                message=f"Line is {len(line.rstrip())} characters. Consider breaking it up for readability.",
                suggestion="Break into multiple lines or extract variables for clarity.",
            ))

        # Trailing whitespace
        if line != line.rstrip() and line.strip():
            comments.append(InlineComment(
                line=i + 1,
                severity=Severity.INFO,
                category="style",
                message="Trailing whitespace detected.",
                suggestion="Remove trailing whitespace. Configure your editor to trim on save.",
            ))

    return comments


def summarize_inline_comments(comments: list[InlineComment]) -> dict:
    """Generate a summary of inline comments.

    Args:
        comments: List of inline comments to summarize.

    Returns:
        Dictionary with severity counts, category counts, and total.
    """
    severity_counts: dict[str, int] = {}
    category_counts: dict[str, int] = {}

    for c in comments:
        sev = c.severity.value
        severity_counts[sev] = severity_counts.get(sev, 0) + 1
        category_counts[c.category] = category_counts.get(c.category, 0) + 1

    return {
        "total_comments": len(comments),
        "by_severity": severity_counts,
        "by_category": category_counts,
    }
