"""API routes — all endpoints for code review."""

import hashlib
import hmac
import logging
import time
from datetime import datetime

from fastapi import APIRouter, HTTPException, Header, Request

from config import settings
from src.core.static_analyzer import run_static_checks, detect_language, calculate_score
from src.core.inline_comments import generate_inline_comments, summarize_inline_comments
from src.core.language_rules import get_supported_languages
from src.models.schemas import (
    CodeReviewRequest,
    CodeReviewResponse,
    DiffReviewRequest,
    DiffReviewResponse,
    HealthResponse,
    InlineCommentModel,
    InlineReviewRequest,
    InlineReviewResponse,
    Language,
    ReviewFinding,
    Severity,
)
from src.services.review_service import review_code, review_diff

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1")

# In-memory stats tracking
_stats = {
    "total_reviews": 0,
    "code_reviews": 0,
    "diff_reviews": 0,
    "static_analyses": 0,
    "webhook_events": 0,
    "total_score": 0,
    "started_at": datetime.now().isoformat(),
}


@router.get("/health", response_model=HealthResponse)
async def health_check():
    """Health check endpoint."""
    return HealthResponse(
        status="ok",
        version="1.0.0",
        provider=settings.default_provider,
    )


@router.get("/stats")
async def get_stats():
    """Return review statistics."""
    avg_score = (
        round(_stats["total_score"] / _stats["code_reviews"])
        if _stats["code_reviews"] > 0
        else 0
    )
    return {
        "total_reviews": _stats["total_reviews"],
        "code_reviews": _stats["code_reviews"],
        "diff_reviews": _stats["diff_reviews"],
        "static_analyses": _stats["static_analyses"],
        "webhook_events": _stats["webhook_events"],
        "average_score": avg_score,
        "started_at": _stats["started_at"],
    }


@router.post("/review/code", response_model=CodeReviewResponse)
async def review_code_endpoint(request: CodeReviewRequest):
    """Full code review — static analysis + AI."""
    try:
        result = await review_code(request)
        _stats["total_reviews"] += 1
        _stats["code_reviews"] += 1
        _stats["total_score"] += result.score
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Review failed: {e}")
        raise HTTPException(status_code=500, detail="Review failed — check server logs.")


@router.post("/review/diff", response_model=DiffReviewResponse)
async def review_diff_endpoint(request: DiffReviewRequest):
    """Review a git diff / PR."""
    try:
        result = await review_diff(request)
        _stats["total_reviews"] += 1
        _stats["diff_reviews"] += 1
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Diff review failed: {e}")
        raise HTTPException(status_code=500, detail="Diff review failed — check server logs.")


@router.post("/analyze/static")
async def static_analysis_endpoint(request: CodeReviewRequest):
    """Static analysis only — free, no AI cost."""
    lang = request.language
    if lang == Language.AUTO:
        lang = detect_language(request.code, request.filename)

    findings = run_static_checks(request.code, lang)
    score = calculate_score(findings)

    _stats["static_analyses"] += 1

    return {
        "findings": [f.model_dump() for f in findings],
        "score": score,
        "language_detected": lang.value,
        "lines_analyzed": len(request.code.split("\n")),
        "finding_count": len(findings),
    }


@router.get("/languages")
async def supported_languages():
    """List supported languages and their analysis depth."""
    return {"languages": get_supported_languages()}


@router.post("/review/inline", response_model=InlineReviewResponse)
async def inline_review_endpoint(request: InlineReviewRequest):
    """Generate inline code review comments with line numbers and suggestions."""
    try:
        comments = generate_inline_comments(
            code=request.code,
            language=request.language,
            filename=request.filename,
        )
        summary = summarize_inline_comments(comments)

        # Detect language for response
        lang = request.language
        if lang == Language.AUTO:
            lang = detect_language(request.code, request.filename)

        # Convert to response models
        comment_models = [
            InlineCommentModel(
                line=c.line,
                end_line=c.end_line,
                severity=c.severity,
                category=c.category,
                message=c.message,
                suggestion=c.suggestion,
                fix=c.fix,
            )
            for c in comments
        ]

        lines_reviewed = len(request.code.split("\n"))
        findings_for_score = [
            ReviewFinding(
                severity=c.severity,
                category=c.category,
                title=c.message[:80],
                description=c.message,
                suggestion=c.suggestion or "",
            )
            for c in comments
            if c.severity in (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM)
        ]
        score = calculate_score(findings_for_score)

        _stats["total_reviews"] += 1

        return InlineReviewResponse(
            comments=comment_models,
            summary=summary,
            score=score,
            language_detected=lang.value,
            lines_reviewed=lines_reviewed,
            total_comments=len(comments),
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Inline review failed: {e}")
        raise HTTPException(status_code=500, detail="Inline review failed — check server logs.")


@router.post("/webhook/github")
async def github_webhook(
    request: Request,
    x_hub_signature_256: str = Header(None, alias="X-Hub-Signature-256"),
    x_github_event: str = Header(None, alias="X-GitHub-Event"),
):
    """GitHub webhook endpoint for auto-review on PR events."""
    if not settings.github_webhook_secret:
        raise HTTPException(status_code=500, detail="GitHub webhook secret not configured")

    body = await request.body()

    # Verify webhook signature
    if x_hub_signature_256:
        expected = "sha256=" + hmac.new(
            settings.github_webhook_secret.encode(),
            body,
            hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, x_hub_signature_256):
            raise HTTPException(status_code=401, detail="Invalid webhook signature")
    else:
        raise HTTPException(status_code=401, detail="Missing webhook signature")

    payload = await request.json()
    _stats["webhook_events"] += 1

    # Handle PR events
    if x_github_event == "pull_request":
        action = payload.get("action", "")
        if action in ("opened", "synchronize"):
            pr = payload.get("pull_request", {})
            pr_number = pr.get("number")
            pr_title = pr.get("title", "")
            logger.info(f"Received PR #{pr_number}: {pr_title}")
            return {
                "status": "accepted",
                "event": x_github_event,
                "action": action,
                "pr_number": pr_number,
            }

    return {
        "status": "ignored",
        "event": x_github_event,
        "reason": "Only pull_request opened/synchronize events are processed",
    }
