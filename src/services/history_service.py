"""Review history and analytics — tracks reviews and provides insights.

In-memory store for review history with analytics endpoints.
Logs every review performed and computes statistics about
common issues, languages, and trends.
"""

import time
from collections import Counter
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from src.models.schemas import Severity


class ReviewRecord(BaseModel):
    """A single review record stored in history.

    Attributes:
        id: Unique identifier for the review.
        review_type: Type of review (code, diff, inline, static).
        language: Language that was reviewed.
        score: Quality score from 0-100.
        finding_count: Number of issues found.
        findings_by_severity: Count of findings per severity level.
        categories: List of issue categories found.
        lines_reviewed: Number of lines analyzed.
        timestamp: When the review was performed.
        filename: Optional filename of the reviewed code.
    """
    id: str
    review_type: str  # code, diff, inline, static
    language: str
    score: int = Field(ge=0, le=100)
    finding_count: int = Field(ge=0)
    findings_by_severity: dict[str, int] = Field(default_factory=dict)
    categories: list[str] = Field(default_factory=list)
    lines_reviewed: int = Field(ge=0)
    timestamp: datetime
    filename: Optional[str] = None


class ReviewAnalytics(BaseModel):
    """Computed analytics from review history.

    Attributes:
        total_reviews: Total number of reviews performed.
        reviews_by_type: Count per review type.
        reviews_by_language: Count per language.
        avg_score: Average quality score across all code reviews.
        avg_findings_per_review: Average number of findings per review.
        most_common_issues: Top issue categories.
        severity_distribution: Total findings per severity level.
        total_lines_reviewed: Total lines of code reviewed.
        recent_reviews: The N most recent reviews.
    """
    total_reviews: int
    reviews_by_type: dict[str, int]
    reviews_by_language: dict[str, int]
    avg_score: float
    avg_findings_per_review: float
    most_common_issues: list[dict]
    severity_distribution: dict[str, int]
    total_lines_reviewed: int
    recent_reviews: list[ReviewRecord]


class ReviewHistoryStore:
    """In-memory review history store with analytics.

    Provides methods to log reviews, retrieve history, and compute
    analytics over the stored review data.
    """

    def __init__(self) -> None:
        """Initialize the history store with an empty record list."""
        self._records: list[ReviewRecord] = []
        self._counter: int = 0

    def log_review(
        self,
        review_type: str,
        language: str,
        score: int,
        finding_count: int,
        findings_by_severity: dict[str, int],
        categories: list[str],
        lines_reviewed: int,
        filename: Optional[str] = None,
    ) -> ReviewRecord:
        """Log a completed review to history.

        Args:
            review_type: Type of review performed.
            language: Language of the reviewed code.
            score: Quality score (0-100).
            finding_count: Number of issues found.
            findings_by_severity: Findings count per severity.
            categories: Issue categories found.
            lines_reviewed: Lines of code analyzed.
            filename: Optional filename.

        Returns:
            The created ReviewRecord.
        """
        self._counter += 1
        record = ReviewRecord(
            id=f"rev-{self._counter:06d}",
            review_type=review_type,
            language=language,
            score=score,
            finding_count=finding_count,
            findings_by_severity=findings_by_severity,
            categories=categories,
            lines_reviewed=lines_reviewed,
            timestamp=datetime.now(),
            filename=filename,
        )
        self._records.append(record)
        return record

    def get_history(
        self,
        limit: int = 50,
        offset: int = 0,
        review_type: Optional[str] = None,
        language: Optional[str] = None,
    ) -> list[ReviewRecord]:
        """Retrieve review history with optional filters.

        Args:
            limit: Maximum records to return.
            offset: Number of records to skip.
            review_type: Filter by review type.
            language: Filter by language.

        Returns:
            Filtered and paginated list of ReviewRecords.
        """
        records = self._records

        if review_type:
            records = [r for r in records if r.review_type == review_type]
        if language:
            records = [r for r in records if r.language == language]

        # Most recent first
        records = list(reversed(records))
        return records[offset: offset + limit]

    def get_analytics(self) -> ReviewAnalytics:
        """Compute analytics from all stored reviews.

        Returns:
            ReviewAnalytics with aggregated statistics.
        """
        if not self._records:
            return ReviewAnalytics(
                total_reviews=0,
                reviews_by_type={},
                reviews_by_language={},
                avg_score=0.0,
                avg_findings_per_review=0.0,
                most_common_issues=[],
                severity_distribution={},
                total_lines_reviewed=0,
                recent_reviews=[],
            )

        type_counter: Counter = Counter()
        lang_counter: Counter = Counter()
        category_counter: Counter = Counter()
        severity_counter: Counter = Counter()
        total_score = 0
        total_findings = 0
        total_lines = 0
        code_review_count = 0

        for record in self._records:
            type_counter[record.review_type] += 1
            lang_counter[record.language] += 1
            total_findings += record.finding_count
            total_lines += record.lines_reviewed

            for cat in record.categories:
                category_counter[cat] += 1
            for sev, count in record.findings_by_severity.items():
                severity_counter[sev] += count

            if record.review_type in ("code", "inline"):
                total_score += record.score
                code_review_count += 1

        avg_score = round(total_score / code_review_count, 1) if code_review_count > 0 else 0.0
        avg_findings = round(total_findings / len(self._records), 1)

        most_common = [
            {"category": cat, "count": count}
            for cat, count in category_counter.most_common(10)
        ]

        recent = list(reversed(self._records[-10:]))

        return ReviewAnalytics(
            total_reviews=len(self._records),
            reviews_by_type=dict(type_counter),
            reviews_by_language=dict(lang_counter),
            avg_score=avg_score,
            avg_findings_per_review=avg_findings,
            most_common_issues=most_common,
            severity_distribution=dict(severity_counter),
            total_lines_reviewed=total_lines,
            recent_reviews=recent,
        )

    def clear(self) -> int:
        """Clear all history records.

        Returns:
            Number of records that were cleared.
        """
        count = len(self._records)
        self._records.clear()
        self._counter = 0
        return count

    @property
    def count(self) -> int:
        """Get total number of records in history.

        Returns:
            Number of stored records.
        """
        return len(self._records)


# Singleton instance
history_store = ReviewHistoryStore()
