"""Language-specific analysis rules — extends static analyzer per language.

Each language module provides targeted checks beyond the universal patterns
in static_analyzer.py. These rules catch language-specific anti-patterns,
common bugs, and best-practice violations.
"""

import re
from typing import Optional

from src.models.schemas import Language, ReviewFinding, Severity


def run_language_rules(
    code: str, lines: list[str], language: Language
) -> list[ReviewFinding]:
    """Dispatch to language-specific rule sets.

    Args:
        code: Full source code as a string.
        lines: Code split into individual lines.
        language: Detected or specified language.

    Returns:
        List of language-specific findings.
    """
    dispatch = {
        Language.PYTHON: _python_rules,
        Language.JAVASCRIPT: _javascript_rules,
        Language.TYPESCRIPT: _typescript_rules,
    }
    handler = dispatch.get(language)
    if handler:
        return handler(code, lines)
    return []


def _python_rules(code: str, lines: list[str]) -> list[ReviewFinding]:
    """Python-specific analysis rules.

    Args:
        code: Full source code.
        lines: Code split into lines.

    Returns:
        List of Python-specific findings.
    """
    findings: list[ReviewFinding] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # Type: ignore without explanation
        if "# type: ignore" in stripped and not re.search(
            r"# type: ignore\[", stripped
        ):
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="maintainability",
                line=i + 1,
                title="Broad type: ignore",
                description="Using `# type: ignore` without specifying which error to ignore.",
                suggestion="Specify the error code: `# type: ignore[assignment]`.",
                code_snippet=stripped[:80],
            ))

        # Star imports
        if re.match(r'^from\s+\S+\s+import\s+\*', stripped):
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="maintainability",
                line=i + 1,
                title="Wildcard Import",
                description="Star imports pollute the namespace and make it unclear where names come from.",
                suggestion="Import specific names: `from module import name1, name2`.",
                code_snippet=stripped[:80],
            ))

        # assert in production code (not test files)
        if re.match(r'^assert\s', stripped):
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="logic",
                line=i + 1,
                title="Assert in Production Code",
                description="assert statements are stripped with `python -O`. Don't use for runtime validation.",
                suggestion="Use `if not condition: raise ValueError(...)` instead.",
                code_snippet=stripped[:80],
            ))

        # Global variable mutation
        if re.match(r'^global\s', stripped):
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="maintainability",
                line=i + 1,
                title="Global Variable Usage",
                description="Global state makes code harder to test and reason about.",
                suggestion="Pass values as function parameters or use a class/dataclass.",
                code_snippet=stripped[:80],
            ))

    # Missing if __name__ == '__main__' guard
    if re.search(r'^\w+\(', code, re.MULTILINE) and "if __name__" not in code:
        # Only flag if there are top-level calls (not just definitions)
        top_level_calls = [
            line for line in lines
            if re.match(r'^[a-zA-Z_]\w*\(', line.strip())
            and not line.strip().startswith("def ")
            and not line.strip().startswith("class ")
        ]
        if top_level_calls:
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="quality",
                title="Missing __name__ Guard",
                description="Top-level function calls without `if __name__ == '__main__':` guard.",
                suggestion="Wrap top-level execution in `if __name__ == '__main__':` block.",
            ))

    return findings


def _javascript_rules(code: str, lines: list[str]) -> list[ReviewFinding]:
    """JavaScript-specific analysis rules.

    Args:
        code: Full source code.
        lines: Code split into lines.

    Returns:
        List of JavaScript-specific findings.
    """
    findings: list[ReviewFinding] = []

    for i, line in enumerate(lines):
        stripped = line.strip()

        # var keyword (should use let/const)
        if re.match(r'\bvar\s+\w+', stripped):
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="quality",
                line=i + 1,
                title="Use let/const Instead of var",
                description="'var' has function scope and hoisting behavior that causes subtle bugs.",
                suggestion="Use 'const' for values that don't change, 'let' for ones that do.",
                code_snippet=stripped[:80],
            ))

        # == instead of ===
        if re.search(r'[^=!]==[^=]', stripped) and '===' not in stripped:
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="logic",
                line=i + 1,
                title="Loose Equality (==)",
                description="Use strict equality (===) to avoid type coercion surprises.",
                suggestion="Replace == with === and != with !==.",
                code_snippet=stripped[:80],
            ))

        # document.write
        if 'document.write(' in stripped:
            findings.append(ReviewFinding(
                severity=Severity.HIGH,
                category="security",
                line=i + 1,
                title="document.write() Usage",
                description="document.write() can overwrite the entire page and is vulnerable to XSS.",
                suggestion="Use DOM methods like createElement/appendChild or innerHTML with sanitization.",
                code_snippet=stripped[:80],
            ))

        # innerHTML with variable (potential XSS)
        if re.search(r'\.innerHTML\s*=', stripped) and not re.search(r'\.innerHTML\s*=\s*["\'`]', stripped):
            findings.append(ReviewFinding(
                severity=Severity.HIGH,
                category="security",
                line=i + 1,
                title="Potential XSS via innerHTML",
                description="Setting innerHTML with a variable can introduce XSS vulnerabilities.",
                suggestion="Use textContent for text, or sanitize HTML with DOMPurify.",
                code_snippet=stripped[:80],
            ))

        # Callback hell indicator (nested callbacks >2 levels)
        if stripped.count('function(') >= 2 or stripped.count('=>') >= 2:
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="maintainability",
                line=i + 1,
                title="Nested Callbacks",
                description="Multiple callbacks on one line suggest callback nesting.",
                suggestion="Use async/await or Promises for cleaner async control flow.",
                code_snippet=stripped[:80],
            ))

        # setTimeout/setInterval with string
        if re.search(r'set(?:Timeout|Interval)\s*\(\s*["\']', stripped):
            findings.append(ReviewFinding(
                severity=Severity.HIGH,
                category="security",
                line=i + 1,
                title="String Argument to setTimeout/setInterval",
                description="Passing a string to setTimeout/setInterval uses eval() internally.",
                suggestion="Pass a function reference or arrow function instead.",
                code_snippet=stripped[:80],
            ))

    return findings


def _typescript_rules(code: str, lines: list[str]) -> list[ReviewFinding]:
    """TypeScript-specific analysis rules.

    Includes all JavaScript rules plus TypeScript-specific checks.

    Args:
        code: Full source code.
        lines: Code split into lines.

    Returns:
        List of TypeScript-specific findings.
    """
    # Start with JS rules since TS is a superset
    findings = _javascript_rules(code, lines)

    for i, line in enumerate(lines):
        stripped = line.strip()

        # any type usage
        if re.search(r':\s*any\b', stripped) or re.search(r'as\s+any\b', stripped):
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="maintainability",
                line=i + 1,
                title="Use of 'any' Type",
                description="'any' disables type checking. Use specific types or 'unknown'.",
                suggestion="Replace 'any' with a specific type, generic, or 'unknown'.",
                code_snippet=stripped[:80],
            ))

        # @ts-ignore without explanation
        if "// @ts-ignore" in stripped or "// @ts-expect-error" in stripped:
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="maintainability",
                line=i + 1,
                title="TypeScript Error Suppression",
                description="Suppressing TypeScript errors hides real issues.",
                suggestion="Fix the type error instead, or add a comment explaining why it's suppressed.",
                code_snippet=stripped[:80],
            ))

        # Non-null assertion (!) overuse
        if re.search(r'\w+!\.\w+', stripped) or re.search(r'\w+!\[', stripped):
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="logic",
                line=i + 1,
                title="Non-null Assertion Operator",
                description="Non-null assertion (!) bypasses null checking. Can cause runtime errors.",
                suggestion="Use optional chaining (?.) or proper null checks instead.",
                code_snippet=stripped[:80],
            ))

    return findings


def get_supported_languages() -> list[dict[str, str]]:
    """Return metadata about supported languages and their analysis depth.

    Returns:
        List of dicts with language name, extensions, and analysis level.
    """
    return [
        {
            "language": "python",
            "extensions": [".py"],
            "analysis_level": "full",
            "description": "Security, quality, complexity, type hints, imports, globals",
        },
        {
            "language": "javascript",
            "extensions": [".js", ".jsx", ".mjs", ".cjs"],
            "analysis_level": "full",
            "description": "Security, XSS, DOM, equality, var/let/const, async patterns",
        },
        {
            "language": "typescript",
            "extensions": [".ts", ".tsx"],
            "analysis_level": "full",
            "description": "All JS rules plus type safety, any usage, ts-ignore",
        },
        {
            "language": "go",
            "extensions": [".go"],
            "analysis_level": "core",
            "description": "Secrets, complexity, universal checks",
        },
        {
            "language": "java",
            "extensions": [".java"],
            "analysis_level": "core",
            "description": "Secrets, SQL injection, complexity",
        },
        {
            "language": "rust",
            "extensions": [".rs"],
            "analysis_level": "core",
            "description": "Secrets, complexity, universal checks",
        },
        {
            "language": "cpp",
            "extensions": [".cpp", ".cc", ".c", ".h", ".hpp"],
            "analysis_level": "core",
            "description": "Secrets, complexity, universal checks",
        },
    ]
