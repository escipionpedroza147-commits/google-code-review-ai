"""Tests for language-specific analysis rules — Python, JavaScript, TypeScript."""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.core.language_rules import (
    run_language_rules,
    get_supported_languages,
    _python_rules,
    _javascript_rules,
    _typescript_rules,
)
from src.core.static_analyzer import run_static_checks
from src.models.schemas import Language, Severity


@pytest.fixture
def client():
    return TestClient(app)


# ── Python Rules ───────────────────────────────────────────────────

class TestPythonRules:
    def test_wildcard_import(self):
        code = "from os import *"
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        wildcards = [f for f in findings if "wildcard" in f.title.lower()]
        assert len(wildcards) >= 1
        assert wildcards[0].severity == Severity.MEDIUM

    def test_broad_type_ignore(self):
        code = "x: int = 'hello'  # type: ignore"
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        ignores = [f for f in findings if "type: ignore" in f.title.lower() or "type" in f.description.lower()]
        assert len(ignores) >= 1

    def test_specific_type_ignore_not_flagged(self):
        code = "x: int = 'hello'  # type: ignore[assignment]"
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        ignores = [f for f in findings if "type: ignore" in f.title.lower() or "broad" in f.title.lower()]
        assert len(ignores) == 0

    def test_assert_in_code(self):
        code = "assert user.is_authenticated"
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        asserts = [f for f in findings if "assert" in f.title.lower()]
        assert len(asserts) >= 1
        assert asserts[0].severity == Severity.MEDIUM

    def test_global_variable(self):
        code = "def update():\n    global counter\n    counter += 1"
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        globals_ = [f for f in findings if "global" in f.title.lower()]
        assert len(globals_) >= 1

    def test_clean_python_no_findings(self):
        code = 'def greet(name: str) -> str:\n    """Greet someone."""\n    return f"Hello, {name}"'
        lines = code.split("\n")
        findings = _python_rules(code, lines)
        # Clean code should produce minimal findings
        critical = [f for f in findings if f.severity == Severity.CRITICAL]
        assert len(critical) == 0


# ── JavaScript Rules ───────────────────────────────────────────────

class TestJavaScriptRules:
    def test_var_keyword(self):
        code = "var name = 'test';"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        vars_ = [f for f in findings if "var" in f.title.lower()]
        assert len(vars_) >= 1

    def test_loose_equality(self):
        code = "if (x == null) { return; }"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        eq = [f for f in findings if "equality" in f.title.lower()]
        assert len(eq) >= 1

    def test_strict_equality_not_flagged(self):
        code = "if (x === null) { return; }"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        eq = [f for f in findings if "equality" in f.title.lower()]
        assert len(eq) == 0

    def test_document_write(self):
        code = "document.write('<h1>Hello</h1>');"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        dw = [f for f in findings if "document.write" in f.title.lower()]
        assert len(dw) >= 1
        assert dw[0].severity == Severity.HIGH

    def test_innerhtml_xss(self):
        code = "element.innerHTML = userInput;"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        xss = [f for f in findings if "xss" in f.title.lower() or "innerhtml" in f.title.lower()]
        assert len(xss) >= 1

    def test_innerhtml_literal_not_flagged(self):
        code = "element.innerHTML = '<p>Hello</p>';"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        xss = [f for f in findings if "xss" in f.title.lower() or "innerhtml" in f.title.lower()]
        assert len(xss) == 0

    def test_settimeout_string(self):
        code = "setTimeout('alert(1)', 1000);"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        timer = [f for f in findings if "settimeout" in f.title.lower() or "setinterval" in f.title.lower() or "string" in f.title.lower()]
        assert len(timer) >= 1
        assert timer[0].severity == Severity.HIGH

    def test_setinterval_string(self):
        code = "setInterval('doStuff()', 500);"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        timer = [f for f in findings if "settimeout" in f.title.lower() or "setinterval" in f.title.lower() or "string" in f.title.lower()]
        assert len(timer) >= 1

    def test_clean_js_minimal_findings(self):
        code = "const add = (a, b) => a + b;\nexport default add;"
        lines = code.split("\n")
        findings = _javascript_rules(code, lines)
        high = [f for f in findings if f.severity in (Severity.CRITICAL, Severity.HIGH)]
        assert len(high) == 0


# ── TypeScript Rules ───────────────────────────────────────────────

class TestTypeScriptRules:
    def test_any_type(self):
        code = "const data: any = fetchData();"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        anys = [f for f in findings if "any" in f.title.lower()]
        assert len(anys) >= 1
        assert anys[0].severity == Severity.MEDIUM

    def test_as_any_cast(self):
        code = "const result = value as any;"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        anys = [f for f in findings if "any" in f.title.lower()]
        assert len(anys) >= 1

    def test_ts_ignore(self):
        code = "// @ts-ignore\nconst x: number = 'string';"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        ignores = [f for f in findings if "suppress" in f.title.lower() or "ts-ignore" in f.description.lower()]
        assert len(ignores) >= 1

    def test_ts_expect_error(self):
        code = "// @ts-expect-error\nconst x = bad();"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        ignores = [f for f in findings if "suppress" in f.title.lower()]
        assert len(ignores) >= 1

    def test_non_null_assertion(self):
        code = "const name = user!.name;"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        nonnull = [f for f in findings if "non-null" in f.title.lower() or "assertion" in f.title.lower()]
        assert len(nonnull) >= 1

    def test_ts_includes_js_rules(self):
        code = "var x = 5;"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        vars_ = [f for f in findings if "var" in f.title.lower()]
        assert len(vars_) >= 1  # Inherited from JS rules

    def test_proper_types_clean(self):
        code = "const name: string = 'hello';\nconst count: number = 42;"
        lines = code.split("\n")
        findings = _typescript_rules(code, lines)
        anys = [f for f in findings if "any" in f.title.lower()]
        assert len(anys) == 0


# ── Integration: Static Analyzer with Language Rules ───────────────

class TestIntegratedLanguageChecks:
    def test_python_full_pipeline(self):
        code = 'from os import *\napi_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"'
        findings = run_static_checks(code, Language.PYTHON)
        titles = [f.title.lower() for f in findings]
        assert any("wildcard" in t for t in titles)
        assert any("secret" in t or "hardcoded" in t for t in titles)

    def test_javascript_full_pipeline(self):
        code = 'var token = "ghp_ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghij";\ndocument.write(token);'
        findings = run_static_checks(code, Language.JAVASCRIPT)
        titles = [f.title.lower() for f in findings]
        # Should catch both secret + JS-specific issues
        assert any("secret" in t or "hardcoded" in t for t in titles)
        assert any("document.write" in t for t in titles)

    def test_typescript_full_pipeline(self):
        code = "const data: any = input;\nelement.innerHTML = data;"
        findings = run_static_checks(code, Language.TYPESCRIPT)
        titles = [f.title.lower() for f in findings]
        assert any("any" in t for t in titles)

    def test_unsupported_language_no_crash(self):
        code = "fn main() { println!(\"hello\"); }"
        findings = run_language_rules(code, code.split("\n"), Language.RUST)
        assert findings == []


# ── get_supported_languages ────────────────────────────────────────

class TestSupportedLanguages:
    def test_returns_list(self):
        langs = get_supported_languages()
        assert isinstance(langs, list)
        assert len(langs) >= 7

    def test_python_full_analysis(self):
        langs = get_supported_languages()
        python = next(l for l in langs if l["language"] == "python")
        assert python["analysis_level"] == "full"

    def test_javascript_full_analysis(self):
        langs = get_supported_languages()
        js = next(l for l in langs if l["language"] == "javascript")
        assert js["analysis_level"] == "full"
        assert ".js" in js["extensions"]

    def test_typescript_full_analysis(self):
        langs = get_supported_languages()
        ts = next(l for l in langs if l["language"] == "typescript")
        assert ts["analysis_level"] == "full"
        assert ".ts" in ts["extensions"]


# ── Languages API Endpoint ─────────────────────────────────────────

class TestLanguagesEndpoint:
    def test_languages_returns_ok(self, client):
        resp = client.get("/api/v1/languages")
        assert resp.status_code == 200
        data = resp.json()
        assert "languages" in data
        assert len(data["languages"]) >= 7

    def test_languages_have_required_fields(self, client):
        resp = client.get("/api/v1/languages")
        data = resp.json()
        for lang in data["languages"]:
            assert "language" in lang
            assert "extensions" in lang
            assert "analysis_level" in lang
            assert "description" in lang
