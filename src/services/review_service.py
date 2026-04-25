"""Review service — orchestrates static analysis + AI for comprehensive reviews.

Dual-provider: supports both Google Gemini and OpenAI.
Static analysis runs first (free), AI fills the gaps.
"""

import json
import logging
import re
from datetime import datetime
from typing import Optional

from config import settings
from src.core.static_analyzer import run_static_checks, detect_language, calculate_score
from src.core.prompts import SYSTEM_PROMPT, CODE_REVIEW_PROMPT, DIFF_REVIEW_PROMPT
from src.models.schemas import (
    CodeReviewRequest, CodeReviewResponse,
    DiffReviewRequest, DiffReviewResponse,
    ReviewFinding, Severity, Language,
)

logger = logging.getLogger(__name__)


async def review_code(request: CodeReviewRequest) -> CodeReviewResponse:
    """Full code review: static analysis + AI."""
    # Detect language
    lang = request.language
    if lang == Language.AUTO:
        lang = detect_language(request.code, request.filename)

    lines = request.code.split("\n")

    # Static analysis first (free, instant)
    static_findings = run_static_checks(request.code, lang)

    # AI review for deeper issues
    ai_findings = await _ai_review(
        code=request.code,
        language=lang.value,
        static_findings=static_findings,
        context=request.context,
        focus_areas=request.focus_areas,
    )

    all_findings = static_findings + ai_findings
    # Sort by severity
    severity_order = {Severity.CRITICAL: 0, Severity.HIGH: 1, Severity.MEDIUM: 2, Severity.LOW: 3, Severity.INFO: 4}
    all_findings.sort(key=lambda f: severity_order.get(f.severity, 5))

    score = calculate_score(all_findings)

    # Metrics
    metrics = {
        "static_findings": len(static_findings),
        "ai_findings": len(ai_findings),
        "total_findings": len(all_findings),
        "critical_count": sum(1 for f in all_findings if f.severity == Severity.CRITICAL),
        "high_count": sum(1 for f in all_findings if f.severity == Severity.HIGH),
        "medium_count": sum(1 for f in all_findings if f.severity == Severity.MEDIUM),
        "low_count": sum(1 for f in all_findings if f.severity == Severity.LOW),
        "language": lang.value,
    }

    summary = _generate_summary(all_findings, score, lang.value, len(lines))

    return CodeReviewResponse(
        findings=all_findings,
        summary=summary,
        score=score,
        metrics=metrics,
        reviewed_at=datetime.now(),
        language_detected=lang.value,
        lines_reviewed=len(lines),
    )


async def review_diff(request: DiffReviewRequest) -> DiffReviewResponse:
    """Review a git diff / PR."""
    # Count changed files and lines
    files = set()
    additions = 0
    deletions = 0
    for line in request.diff.split("\n"):
        if line.startswith("diff --git"):
            parts = line.split(" b/")
            if len(parts) > 1:
                files.add(parts[1])
        elif line.startswith("+") and not line.startswith("+++"):
            additions += 1
        elif line.startswith("-") and not line.startswith("---"):
            deletions += 1

    ai_findings = await _ai_diff_review(
        diff=request.diff,
        pr_title=request.pr_title,
        pr_description=request.pr_description,
    )

    has_critical = any(f.severity == Severity.CRITICAL for f in ai_findings)
    has_high = any(f.severity == Severity.HIGH for f in ai_findings)

    if has_critical:
        approve = False
        reason = "Critical issues found — must be fixed before merging."
        risk = Severity.CRITICAL
    elif has_high:
        approve = False
        reason = "High-severity issues found — recommend fixes before merging."
        risk = Severity.HIGH
    elif len(ai_findings) > 5:
        approve = False
        reason = "Multiple issues found — consider addressing before merge."
        risk = Severity.MEDIUM
    else:
        approve = True
        reason = "No blocking issues found. Minor suggestions provided."
        risk = Severity.LOW

    summary = f"Reviewed {len(files)} file(s), {additions} additions, {deletions} deletions. " \
              f"Found {len(ai_findings)} issue(s)."

    return DiffReviewResponse(
        findings=ai_findings,
        summary=summary,
        approve=approve,
        approval_reason=reason,
        risk_level=risk,
        files_reviewed=len(files),
        additions_reviewed=additions,
        deletions_reviewed=deletions,
    )


async def _ai_review(
    code: str,
    language: str,
    static_findings: list[ReviewFinding],
    context: Optional[str] = None,
    focus_areas: Optional[list[str]] = None,
) -> list[ReviewFinding]:
    """Get AI-powered findings beyond static analysis."""
    static_text = "\n".join(
        f"- [{f.severity.value}] Line {f.line}: {f.title}" for f in static_findings
    ) if static_findings else "None detected."

    context_section = f"Context: {context}" if context else ""
    focus = ", ".join(focus_areas) if focus_areas else "security, correctness, performance, maintainability"

    prompt = CODE_REVIEW_PROMPT.format(
        language=language,
        code=code[:10000],  # Cap to avoid token blowup
        context_section=context_section,
        static_findings=static_text,
        focus_areas=focus,
    )

    try:
        response_text = await _call_ai(prompt)
        return _parse_ai_findings(response_text)
    except Exception as e:
        logger.error(f"AI review failed: {e}")
        return []


async def _ai_diff_review(
    diff: str,
    pr_title: Optional[str] = None,
    pr_description: Optional[str] = None,
) -> list[ReviewFinding]:
    """AI review of a diff."""
    desc_section = f"PR Description: {pr_description}" if pr_description else ""

    prompt = DIFF_REVIEW_PROMPT.format(
        pr_title=pr_title or "Untitled PR",
        pr_description_section=desc_section,
        diff=diff[:15000],
    )

    try:
        response_text = await _call_ai(prompt)
        return _parse_ai_findings(response_text)
    except Exception as e:
        logger.error(f"AI diff review failed: {e}")
        return []


async def _call_ai(prompt: str) -> str:
    """Call the configured AI provider."""
    if settings.default_provider == "gemini" and settings.gemini_api_key:
        return await _call_gemini(prompt)
    elif settings.openai_api_key:
        return await _call_openai(prompt)
    else:
        raise ValueError("No AI provider configured — set GEMINI_API_KEY or OPENAI_API_KEY")


async def _call_gemini(prompt: str) -> str:
    """Call Google Gemini API."""
    import google.generativeai as genai
    genai.configure(api_key=settings.gemini_api_key)
    model = genai.GenerativeModel("gemini-2.5-flash")
    response = await model.generate_content_async(
        [SYSTEM_PROMPT, prompt],
        generation_config={"temperature": 0.2, "max_output_tokens": 4000},
    )
    return response.text


async def _call_openai(prompt: str) -> str:
    """Call OpenAI API."""
    from openai import AsyncOpenAI
    client = AsyncOpenAI(api_key=settings.openai_api_key)
    response = await client.chat.completions.create(
        model="gpt-5-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
        max_tokens=4000,
    )
    return response.choices[0].message.content


def _parse_ai_findings(text: str) -> list[ReviewFinding]:
    """Parse AI response into structured findings."""
    findings = []

    # Look for severity markers in the response
    severity_map = {
        "critical": Severity.CRITICAL,
        "high": Severity.HIGH,
        "medium": Severity.MEDIUM,
        "low": Severity.LOW,
        "info": Severity.INFO,
    }

    # Split on common finding patterns
    sections = re.split(r'\n(?=\d+\.|#{1,3}\s|\*\*(?:Finding|Issue))', text)

    for section in sections:
        if len(section.strip()) < 20:
            continue

        # Detect severity
        severity = Severity.MEDIUM
        for key, sev in severity_map.items():
            if key in section.lower()[:100]:
                severity = sev
                break

        # Detect category
        category = "general"
        for cat in ["security", "performance", "logic", "maintainability", "style"]:
            if cat in section.lower():
                category = cat
                break

        # Detect line number
        line_match = re.search(r'[Ll]ine\s*(\d+)', section)
        line_num = int(line_match.group(1)) if line_match else None

        # Extract first sentence as title
        first_line = section.strip().split("\n")[0]
        title = re.sub(r'^[\d.#*\-\s]+', '', first_line)[:100]

        if title and len(title) > 5:
            findings.append(ReviewFinding(
                severity=severity,
                category=category,
                line=line_num,
                title=title.strip(),
                description=section.strip()[:500],
                suggestion="See description for recommended fix.",
            ))

    return findings[:20]  # Cap at 20 AI findings


def _generate_summary(findings: list[ReviewFinding], score: int, language: str, lines: int) -> str:
    """Generate a human-readable summary."""
    critical = sum(1 for f in findings if f.severity == Severity.CRITICAL)
    high = sum(1 for f in findings if f.severity == Severity.HIGH)

    if score >= 90:
        verdict = "Excellent code quality."
    elif score >= 70:
        verdict = "Good code with some issues to address."
    elif score >= 50:
        verdict = "Significant issues found — needs attention before production."
    else:
        verdict = "Major issues detected — not production-ready."

    parts = [
        f"Reviewed {lines} lines of {language}. Quality score: {score}/100. {verdict}",
        f"Found {len(findings)} total issue(s)",
    ]
    if critical:
        parts.append(f"including {critical} CRITICAL")
    if high:
        parts.append(f"and {high} HIGH severity")

    return ". ".join(parts) + "."
