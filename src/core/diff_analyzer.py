"""Git diff analysis — parses unified diffs and reviews only changed lines.

Extracts added/modified code from unified diff format, determines
language per file, and runs targeted analysis on just the changes.
This focuses review effort on what actually changed, reducing noise
from existing code.
"""

import re
from dataclasses import dataclass, field
from typing import Optional

from src.core.static_analyzer import run_static_checks, detect_language, calculate_score
from src.models.schemas import Language, ReviewFinding, Severity


@dataclass
class DiffHunk:
    """A single hunk from a unified diff.

    Attributes:
        start_line: Starting line number in the new file.
        line_count: Number of lines in this hunk.
        lines: The actual diff lines (with +/- prefixes stripped).
        raw_lines: Original diff lines with prefixes.
    """
    start_line: int
    line_count: int
    lines: list[str] = field(default_factory=list)
    raw_lines: list[str] = field(default_factory=list)


@dataclass
class DiffFile:
    """A single file's changes extracted from a unified diff.

    Attributes:
        filename: Path of the changed file.
        language: Detected programming language.
        hunks: List of change hunks.
        additions: Lines added (prefixed with +).
        deletions: Lines removed (prefixed with -).
        added_code: Concatenated added lines as source code.
    """
    filename: str
    language: Language
    hunks: list[DiffHunk] = field(default_factory=list)
    additions: list[tuple[int, str]] = field(default_factory=list)
    deletions: list[tuple[int, str]] = field(default_factory=list)
    added_code: str = ""


@dataclass
class DiffAnalysisResult:
    """Complete result of analyzing a unified diff.

    Attributes:
        files: List of analyzed file diffs.
        findings: All findings from analyzing the changes.
        total_additions: Total lines added across all files.
        total_deletions: Total lines deleted across all files.
        files_changed: Number of files changed.
        score: Aggregate quality score for the changes.
        summary: Human-readable summary of the analysis.
    """
    files: list[DiffFile]
    findings: list[ReviewFinding]
    total_additions: int
    total_deletions: int
    files_changed: int
    score: int
    summary: str


def parse_unified_diff(diff_text: str) -> list[DiffFile]:
    """Parse a unified diff into structured file-level changes.

    Handles standard unified diff format with `diff --git`, `---`, `+++`,
    and `@@ ... @@` hunk headers. Extracts per-file additions and deletions
    with accurate line numbers.

    Args:
        diff_text: Raw unified diff as a string.

    Returns:
        List of DiffFile objects, one per changed file.
    """
    files: list[DiffFile] = []
    current_file: Optional[DiffFile] = None
    current_hunk: Optional[DiffHunk] = None
    new_line_num = 0

    for line in diff_text.split("\n"):
        # New file in diff
        if line.startswith("diff --git"):
            match = re.search(r' b/(.+)$', line)
            if match:
                filename = match.group(1)
                lang = detect_language("", filename)
                current_file = DiffFile(filename=filename, language=lang)
                files.append(current_file)
                current_hunk = None

        # Hunk header
        elif line.startswith("@@"):
            hunk_match = re.search(r'\+(\d+)(?:,(\d+))?', line)
            if hunk_match and current_file is not None:
                start = int(hunk_match.group(1))
                count = int(hunk_match.group(2)) if hunk_match.group(2) else 1
                current_hunk = DiffHunk(start_line=start, line_count=count)
                current_file.hunks.append(current_hunk)
                new_line_num = start

        # Skip diff metadata lines
        elif line.startswith("---") or line.startswith("+++"):
            continue

        # Added line
        elif line.startswith("+") and current_file is not None:
            content = line[1:]
            current_file.additions.append((new_line_num, content))
            if current_hunk is not None:
                current_hunk.lines.append(content)
                current_hunk.raw_lines.append(line)
            new_line_num += 1

        # Deleted line
        elif line.startswith("-") and current_file is not None:
            content = line[1:]
            current_file.deletions.append((0, content))  # Line 0 = deleted
            if current_hunk is not None:
                current_hunk.raw_lines.append(line)
            # Don't increment new_line_num for deletions

        # Context line
        elif current_file is not None and current_hunk is not None:
            if line.startswith(" ") or (not line.startswith("\\") and line.strip()):
                new_line_num += 1

    # Build added_code for each file
    for f in files:
        f.added_code = "\n".join(content for _, content in f.additions)

    return files


def analyze_diff(diff_text: str) -> DiffAnalysisResult:
    """Analyze a unified diff — focuses review on changed lines only.

    Parses the diff, extracts added code per file, runs language-specific
    static analysis on just the new code, and maps findings back to
    original diff line numbers.

    Args:
        diff_text: Raw unified diff string.

    Returns:
        DiffAnalysisResult with per-file findings, score, and summary.
    """
    files = parse_unified_diff(diff_text)
    all_findings: list[ReviewFinding] = []
    total_additions = 0
    total_deletions = 0

    for diff_file in files:
        total_additions += len(diff_file.additions)
        total_deletions += len(diff_file.deletions)

        if not diff_file.added_code.strip():
            continue

        # Run static checks on the added code
        findings = run_static_checks(diff_file.added_code, diff_file.language)

        # Map findings back to diff line numbers
        for finding in findings:
            finding.file = diff_file.filename
            if finding.line and diff_file.additions:
                # Map to actual file line number from the diff
                if finding.line <= len(diff_file.additions):
                    finding.line = diff_file.additions[finding.line - 1][0]

            all_findings.append(finding)

    # Score based on findings in changed code
    score = calculate_score(all_findings)

    # Build summary
    summary = _build_diff_summary(files, all_findings, score, total_additions, total_deletions)

    return DiffAnalysisResult(
        files=files,
        findings=all_findings,
        total_additions=total_additions,
        total_deletions=total_deletions,
        files_changed=len(files),
        score=score,
        summary=summary,
    )


def _build_diff_summary(
    files: list[DiffFile],
    findings: list[ReviewFinding],
    score: int,
    additions: int,
    deletions: int,
) -> str:
    """Build a human-readable summary of diff analysis.

    Args:
        files: Analyzed diff files.
        findings: All findings from analysis.
        score: Quality score.
        additions: Total added lines.
        deletions: Total deleted lines.

    Returns:
        Summary string describing the diff analysis results.
    """
    file_count = len(files)
    languages = set(f.language.value for f in files if f.language != Language.AUTO)
    critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    high = sum(1 for f in findings if f.severity == Severity.HIGH)

    parts = [
        f"Analyzed {file_count} changed file(s): +{additions}/-{deletions} lines.",
    ]

    if languages:
        parts.append(f"Languages: {', '.join(sorted(languages))}.")

    parts.append(f"Quality score: {score}/100.")
    parts.append(f"Found {len(findings)} issue(s) in changed code.")

    if critical:
        parts.append(f"⚠️ {critical} CRITICAL issue(s) need immediate attention.")
    if high:
        parts.append(f"🔴 {high} HIGH severity issue(s) found.")

    if score >= 90 and not critical:
        parts.append("Changes look good! ✅")
    elif score < 50:
        parts.append("Significant issues in the changes — review carefully.")

    return " ".join(parts)
