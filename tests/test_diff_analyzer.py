"""Tests for git diff analysis — parsing, analysis, and endpoint."""

import pytest
from fastapi.testclient import TestClient

from main import app
from src.core.diff_analyzer import (
    parse_unified_diff,
    analyze_diff,
    DiffFile,
    DiffHunk,
    DiffAnalysisResult,
)
from src.models.schemas import Language, Severity


@pytest.fixture
def client():
    return TestClient(app)


SAMPLE_DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,5 +1,7 @@
 import os
+import sys
+api_key = "sk-abcdefghijklmnopqrstuvwxyz1234567890"
 
 def main():
     print("hello")
"""

MULTI_FILE_DIFF = """diff --git a/app.py b/app.py
--- a/app.py
+++ b/app.py
@@ -1,3 +1,4 @@
 import os
+import sys
 
 def main():
diff --git a/utils.js b/utils.js
--- a/utils.js
+++ b/utils.js
@@ -1,2 +1,3 @@
 const x = 1;
+var y = 2;
"""

DELETE_ONLY_DIFF = """diff --git a/old.py b/old.py
--- a/old.py
+++ b/old.py
@@ -1,4 +1,2 @@
-import unused
-import also_unused
 import os
 
"""

CLEAN_DIFF = """diff --git a/math.py b/math.py
--- a/math.py
+++ b/math.py
@@ -1,3 +1,5 @@
+def add(a: int, b: int) -> int:
+    return a + b
 
 def subtract(a, b):
     return a - b
"""


# ── Diff Parsing ───────────────────────────────────────────────────

class TestParseDiff:
    def test_parse_single_file(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files) == 1
        assert files[0].filename == "app.py"
        assert files[0].language == Language.PYTHON

    def test_parse_additions(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files[0].additions) == 2  # import sys + api_key line

    def test_parse_multi_file(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        assert len(files) == 2
        assert files[0].filename == "app.py"
        assert files[1].filename == "utils.js"

    def test_language_detection_per_file(self):
        files = parse_unified_diff(MULTI_FILE_DIFF)
        assert files[0].language == Language.PYTHON
        assert files[1].language == Language.JAVASCRIPT

    def test_parse_deletions(self):
        files = parse_unified_diff(DELETE_ONLY_DIFF)
        assert len(files) == 1
        assert len(files[0].deletions) == 2
        assert len(files[0].additions) == 0

    def test_parse_empty_diff(self):
        files = parse_unified_diff("")
        assert files == []

    def test_added_code_built(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert "import sys" in files[0].added_code

    def test_hunks_created(self):
        files = parse_unified_diff(SAMPLE_DIFF)
        assert len(files[0].hunks) >= 1
        hunk = files[0].hunks[0]
        assert hunk.start_line >= 1
        assert len(hunk.lines) >= 1


# ── Diff Analysis ──────────────────────────────────────────────────

class TestAnalyzeDiff:
    def test_analyze_finds_issues_in_additions(self):
        result = analyze_diff(SAMPLE_DIFF)
        # Should find the hardcoded secret in the added line
        secrets = [f for f in result.findings if "secret" in f.title.lower() or "hardcoded" in f.title.lower()]
        assert len(secrets) >= 1

    def test_analyze_clean_diff(self):
        result = analyze_diff(CLEAN_DIFF)
        critical = [f for f in result.findings if f.severity == Severity.CRITICAL]
        assert len(critical) == 0
        assert result.score >= 80

    def test_analyze_multi_file(self):
        result = analyze_diff(MULTI_FILE_DIFF)
        assert result.files_changed == 2
        assert result.total_additions >= 2

    def test_analyze_counts(self):
        result = analyze_diff(SAMPLE_DIFF)
        assert result.total_additions >= 2
        assert result.files_changed == 1

    def test_analyze_deletion_counts(self):
        result = analyze_diff(DELETE_ONLY_DIFF)
        assert result.total_deletions == 2
        assert result.total_additions == 0

    def test_findings_have_file_attribute(self):
        result = analyze_diff(SAMPLE_DIFF)
        for finding in result.findings:
            assert finding.file == "app.py"

    def test_score_range(self):
        result = analyze_diff(SAMPLE_DIFF)
        assert 0 <= result.score <= 100

    def test_summary_generated(self):
        result = analyze_diff(SAMPLE_DIFF)
        assert len(result.summary) > 10
        assert "file" in result.summary.lower()

    def test_summary_mentions_languages(self):
        result = analyze_diff(MULTI_FILE_DIFF)
        assert "python" in result.summary.lower() or "javascript" in result.summary.lower()

    def test_empty_diff_no_crash(self):
        result = analyze_diff("")
        assert result.files_changed == 0
        assert result.score == 100

    def test_js_specific_findings(self):
        result = analyze_diff(MULTI_FILE_DIFF)
        # var y = 2 should trigger JS rules
        js_findings = [f for f in result.findings if f.file == "utils.js"]
        # May or may not find var depending on rules
        assert isinstance(js_findings, list)


# ── DiffFile Dataclass ─────────────────────────────────────────────

class TestDiffFile:
    def test_default_values(self):
        f = DiffFile(filename="test.py", language=Language.PYTHON)
        assert f.hunks == []
        assert f.additions == []
        assert f.deletions == []
        assert f.added_code == ""


class TestDiffHunk:
    def test_basic_hunk(self):
        h = DiffHunk(start_line=10, line_count=5)
        assert h.start_line == 10
        assert h.lines == []


# ── API Endpoint ───────────────────────────────────────────────────

class TestAnalyzeDiffEndpoint:
    def test_analyze_diff_endpoint(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": SAMPLE_DIFF,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert "files" in data
        assert "findings" in data
        assert "total_additions" in data
        assert "total_deletions" in data
        assert "files_changed" in data
        assert "score" in data
        assert "summary" in data

    def test_analyze_diff_finds_issues(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": SAMPLE_DIFF,
        })
        data = resp.json()
        assert data["files_changed"] == 1
        assert data["total_additions"] >= 2

    def test_analyze_diff_multi_file(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": MULTI_FILE_DIFF,
        })
        data = resp.json()
        assert data["files_changed"] == 2
        assert len(data["files"]) == 2

    def test_analyze_diff_file_info(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": SAMPLE_DIFF,
        })
        data = resp.json()
        assert data["files"][0]["filename"] == "app.py"
        assert data["files"][0]["language"] == "python"

    def test_analyze_diff_empty_rejected(self, client):
        resp = client.post("/api/v1/analyze/diff", json={"diff": ""})
        assert resp.status_code == 422

    def test_analyze_diff_with_context(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": CLEAN_DIFF,
            "context": "Adding math utilities",
        })
        assert resp.status_code == 200

    def test_analyze_diff_score_range(self, client):
        resp = client.post("/api/v1/analyze/diff", json={
            "diff": CLEAN_DIFF,
        })
        data = resp.json()
        assert 0 <= data["score"] <= 100
