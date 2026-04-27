"""Static code analysis — catches issues without AI, zero cost.

These checks run first. AI only handles what static analysis can't.
This keeps costs down and latency low.
"""

import re
from typing import Optional
from src.models.schemas import ReviewFinding, Severity, Language


def detect_language(code: str, filename: Optional[str] = None) -> Language:
    """Detect programming language from content and filename."""
    if filename:
        ext_map = {
            ".py": Language.PYTHON,
            ".js": Language.JAVASCRIPT,
            ".ts": Language.TYPESCRIPT,
            ".tsx": Language.TYPESCRIPT,
            ".go": Language.GO,
            ".java": Language.JAVA,
            ".rs": Language.RUST,
            ".cpp": Language.CPP,
            ".cc": Language.CPP,
            ".c": Language.CPP,
        }
        for ext, lang in ext_map.items():
            if filename.endswith(ext):
                return lang

    # Content-based detection
    if "def " in code and ("import " in code or "print(" in code):
        return Language.PYTHON
    if "func " in code and "package " in code:
        return Language.GO
    if "fn " in code and ("let mut" in code or "impl " in code):
        return Language.RUST
    if "const " in code or "let " in code or "=>" in code:
        if ": " in code and ("interface " in code or "type " in code):
            return Language.TYPESCRIPT
        return Language.JAVASCRIPT
    if "public class " in code or "private " in code:
        return Language.JAVA

    return Language.PYTHON  # Default fallback


def run_static_checks(code: str, language: Language) -> list[ReviewFinding]:
    """Run language-aware static checks. Fast, free, deterministic."""
    from src.core.language_rules import run_language_rules

    findings = []
    lines = code.split("\n")

    # Universal checks (all languages)
    findings.extend(_check_security(code, lines, language))
    findings.extend(_check_complexity(code, lines, language))
    findings.extend(_check_quality(code, lines, language))

    # Language-specific extended rules
    findings.extend(run_language_rules(code, lines, language))

    return findings


def _check_security(code: str, lines: list[str], lang: Language) -> list[ReviewFinding]:
    """Security-focused static checks."""
    findings = []

    # Hardcoded secrets
    secret_patterns = [
        (r'(?:api[_-]?key|secret|password|token)\s*=\s*["\'][^"\']{8,}["\']', "Possible hardcoded secret"),
        (r'(?:sk-[a-zA-Z0-9]{20,})', "Possible OpenAI API key"),
        (r'(?:ghp_[a-zA-Z0-9]{36})', "Possible GitHub token"),
        (r'(?:AKIA[0-9A-Z]{16})', "Possible AWS access key"),
    ]
    for pattern, msg in secret_patterns:
        for i, line in enumerate(lines):
            if re.search(pattern, line, re.IGNORECASE):
                findings.append(ReviewFinding(
                    severity=Severity.CRITICAL,
                    category="security",
                    line=i + 1,
                    title="Hardcoded Secret Detected",
                    description=f"{msg} found on line {i + 1}. Secrets must come from environment variables.",
                    suggestion="Move to .env file and use os.getenv() or equivalent.",
                    code_snippet=line.strip()[:80],
                ))

    # SQL injection patterns
    if lang in (Language.PYTHON, Language.JAVASCRIPT, Language.TYPESCRIPT, Language.JAVA):
        sql_patterns = [
            r'f["\'].*(?:SELECT|INSERT|UPDATE|DELETE).*\{',
            r'(?:SELECT|INSERT|UPDATE|DELETE).*\+\s*(?:request|req|user|input|params)',
            r'\.format\(.*(?:SELECT|INSERT|UPDATE|DELETE)',
            r'%s.*(?:SELECT|INSERT|UPDATE|DELETE)',
        ]
        for pattern in sql_patterns:
            for i, line in enumerate(lines):
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(ReviewFinding(
                        severity=Severity.CRITICAL,
                        category="security",
                        line=i + 1,
                        title="Potential SQL Injection",
                        description="String interpolation in SQL query. Use parameterized queries.",
                        suggestion="Use query parameters (?, %s) instead of string formatting.",
                        code_snippet=line.strip()[:80],
                    ))

    # eval/exec usage
    if lang == Language.PYTHON:
        for i, line in enumerate(lines):
            if re.search(r'\b(?:eval|exec)\s*\(', line):
                findings.append(ReviewFinding(
                    severity=Severity.CRITICAL,
                    category="security",
                    line=i + 1,
                    title="Dangerous eval/exec Usage",
                    description="eval() and exec() can execute arbitrary code. Avoid unless absolutely necessary.",
                    suggestion="Use ast.literal_eval() for safe parsing, or refactor to avoid dynamic code execution.",
                    code_snippet=line.strip()[:80],
                ))

    # Unsafe deserialization
    if lang == Language.PYTHON:
        for i, line in enumerate(lines):
            if re.search(r'pickle\.loads?\(|yaml\.load\([^)]*(?:Loader|$)', line):
                findings.append(ReviewFinding(
                    severity=Severity.HIGH,
                    category="security",
                    line=i + 1,
                    title="Unsafe Deserialization",
                    description="pickle/yaml.load can execute arbitrary code from untrusted data.",
                    suggestion="Use json for data interchange. If YAML needed, use yaml.safe_load().",
                    code_snippet=line.strip()[:80],
                ))

    return findings


def _check_complexity(code: str, lines: list[str], lang: Language) -> list[ReviewFinding]:
    """Complexity and performance checks."""
    findings = []

    # Long functions
    func_pattern = {
        Language.PYTHON: r'^(?:def |async def )\w+',
        Language.JAVASCRIPT: r'(?:function |const \w+ = (?:async )?\(|(?:async )?(?:\w+)\s*\()',
        Language.TYPESCRIPT: r'(?:function |const \w+ = (?:async )?\(|(?:async )?(?:\w+)\s*\()',
        Language.GO: r'^func ',
        Language.JAVA: r'(?:public|private|protected)\s+\w+\s+\w+\s*\(',
        Language.RUST: r'^(?:pub )?fn ',
    }.get(lang, r'^def ')

    current_func_start = None
    current_func_name = ""
    for i, line in enumerate(lines):
        if re.search(func_pattern, line.strip()):
            if current_func_start and (i - current_func_start) > 50:
                findings.append(ReviewFinding(
                    severity=Severity.MEDIUM,
                    category="maintainability",
                    line=current_func_start + 1,
                    title=f"Long Function: {current_func_name}",
                    description=f"Function is {i - current_func_start} lines. Functions over 50 lines are harder to test and maintain.",
                    suggestion="Break into smaller, focused functions. Each function should do one thing.",
                ))
            current_func_start = i
            current_func_name = line.strip()[:60]

    # Deeply nested code (>4 levels)
    for i, line in enumerate(lines):
        indent = len(line) - len(line.lstrip())
        indent_level = indent // 4 if lang != Language.GO else indent // 4
        if indent_level >= 5 and line.strip():
            findings.append(ReviewFinding(
                severity=Severity.MEDIUM,
                category="maintainability",
                line=i + 1,
                title="Deep Nesting",
                description=f"Code is nested {indent_level} levels deep. Hard to read and maintain.",
                suggestion="Use early returns, guard clauses, or extract helper functions.",
                code_snippet=line.rstrip()[:80],
            ))
            break  # Only flag once

    # TODO/FIXME/HACK comments
    for i, line in enumerate(lines):
        if re.search(r'\b(?:TODO|FIXME|HACK|XXX|BUG)\b', line):
            findings.append(ReviewFinding(
                severity=Severity.LOW,
                category="maintainability",
                line=i + 1,
                title="Unresolved TODO/FIXME",
                description="Code has unresolved markers that should be addressed before production.",
                suggestion="Resolve the issue or create a tracking ticket.",
                code_snippet=line.strip()[:80],
            ))

    return findings


def _check_quality(code: str, lines: list[str], lang: Language) -> list[ReviewFinding]:
    """Code quality checks."""
    findings = []

    # Empty catch/except blocks
    if lang == Language.PYTHON:
        for i, line in enumerate(lines):
            if re.search(r'except.*:', line.strip()):
                if i + 1 < len(lines) and re.search(r'^\s*pass\s*$', lines[i + 1]):
                    findings.append(ReviewFinding(
                        severity=Severity.HIGH,
                        category="logic",
                        line=i + 1,
                        title="Silent Exception Swallowing",
                        description="Empty except:pass hides errors. Bugs become invisible.",
                        suggestion="Log the exception, re-raise it, or handle it specifically.",
                        code_snippet=f"{line.strip()} → {lines[i+1].strip()}",
                    ))

    # Bare except
    if lang == Language.PYTHON:
        for i, line in enumerate(lines):
            if re.search(r'^\s*except\s*:', line):
                findings.append(ReviewFinding(
                    severity=Severity.MEDIUM,
                    category="logic",
                    line=i + 1,
                    title="Bare Except Clause",
                    description="Catches ALL exceptions including SystemExit and KeyboardInterrupt.",
                    suggestion="Catch specific exceptions: except ValueError, except HTTPError, etc.",
                    code_snippet=line.strip(),
                ))

    # Magic numbers
    for i, line in enumerate(lines):
        if re.search(r'(?<!=\s)(?<![<>!=])\b(?:if|while|for|return)\b.*\b\d{2,}\b', line):
            if not re.search(r'(?:#|//|/\*)', line):  # Skip commented lines
                findings.append(ReviewFinding(
                    severity=Severity.LOW,
                    category="maintainability",
                    line=i + 1,
                    title="Magic Number",
                    description="Unnamed numeric constants make code harder to understand and maintain.",
                    suggestion="Extract to a named constant with a descriptive name.",
                    code_snippet=line.strip()[:80],
                ))

    # Print statements in production code
    if lang == Language.PYTHON:
        for i, line in enumerate(lines):
            if re.search(r'^\s*print\(', line) and "test" not in (lines[0] if lines else "").lower():
                findings.append(ReviewFinding(
                    severity=Severity.LOW,
                    category="quality",
                    line=i + 1,
                    title="Print Statement in Production Code",
                    description="Use logging module instead of print() for production code.",
                    suggestion="Replace with logging.info(), logging.debug(), etc.",
                    code_snippet=line.strip()[:80],
                ))
                break  # Flag once

    return findings


def calculate_score(findings: list[ReviewFinding]) -> int:
    """Calculate a 0-100 quality score based on findings."""
    score = 100
    penalty = {
        Severity.CRITICAL: 25,
        Severity.HIGH: 15,
        Severity.MEDIUM: 8,
        Severity.LOW: 3,
        Severity.INFO: 0,
    }
    for f in findings:
        score -= penalty.get(f.severity, 0)
    return max(0, min(100, score))
