"""Schemas for code review requests and responses."""

from pydantic import BaseModel, Field
from typing import Optional
from datetime import datetime
from enum import Enum


class Severity(str, Enum):
    CRITICAL = "critical"  # Security vulnerabilities, data loss risks
    HIGH = "high"          # Bugs, logic errors, performance issues
    MEDIUM = "medium"      # Code smells, maintainability concerns
    LOW = "low"            # Style, naming, minor improvements
    INFO = "info"          # Suggestions, best practices


class Language(str, Enum):
    PYTHON = "python"
    JAVASCRIPT = "javascript"
    TYPESCRIPT = "typescript"
    GO = "go"
    JAVA = "java"
    RUST = "rust"
    CPP = "cpp"
    AUTO = "auto"


class ReviewFinding(BaseModel):
    """Single issue found during review."""
    severity: Severity
    category: str  # security, performance, logic, style, maintainability
    file: Optional[str] = None
    line: Optional[int] = None
    title: str
    description: str
    suggestion: str
    code_snippet: Optional[str] = None
    fixed_code: Optional[str] = None


class CodeReviewRequest(BaseModel):
    """Submit code for AI review."""
    code: str = Field(..., min_length=1, max_length=500000)
    language: Language = Language.AUTO
    filename: Optional[str] = None
    context: Optional[str] = None  # What does this code do?
    focus_areas: Optional[list[str]] = None  # security, performance, etc.


class CodeReviewResponse(BaseModel):
    """Complete review with findings and metrics."""
    findings: list[ReviewFinding]
    summary: str
    score: int = Field(..., ge=0, le=100)  # 0-100 quality score
    metrics: dict
    reviewed_at: datetime
    language_detected: str
    lines_reviewed: int


class DiffReviewRequest(BaseModel):
    """Review a git diff / PR."""
    diff: str = Field(..., min_length=1, max_length=1000000)
    base_branch: Optional[str] = "main"
    pr_title: Optional[str] = None
    pr_description: Optional[str] = None


class DiffReviewResponse(BaseModel):
    """PR-focused review with approval recommendation."""
    findings: list[ReviewFinding]
    summary: str
    approve: bool
    approval_reason: str
    risk_level: Severity
    files_reviewed: int
    additions_reviewed: int
    deletions_reviewed: int


class InlineCommentModel(BaseModel):
    """Inline code review comment anchored to a specific line."""
    line: int = Field(..., ge=1, description="1-indexed line number")
    end_line: int = Field(..., ge=1, description="End line (same as line for single-line)")
    severity: Severity
    category: str
    message: str
    suggestion: Optional[str] = None
    fix: Optional[str] = None


class InlineReviewRequest(BaseModel):
    """Submit code for inline review comments."""
    code: str = Field(..., min_length=1, max_length=500000)
    language: Language = Language.AUTO
    filename: Optional[str] = None


class InlineReviewResponse(BaseModel):
    """Response with inline comments, summary, and score."""
    comments: list[InlineCommentModel]
    summary: dict
    score: int = Field(..., ge=0, le=100)
    language_detected: str
    lines_reviewed: int
    total_comments: int


class HealthResponse(BaseModel):
    status: str = "ok"
    version: str = "1.0.0"
    provider: str = ""
