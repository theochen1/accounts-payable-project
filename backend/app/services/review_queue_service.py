"""
Review Queue Service - Manages the review queue for human oversight.
Calculates priority, SLA deadlines, and manages queue items.
"""
import logging
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session
from uuid import UUID

from app.models.matching_result import MatchingResult
from app.models.review_queue import ReviewQueue
from app.schemas.matching_v2 import MatchingIssueV2, IssueCategory

logger = logging.getLogger(__name__)


class ReviewQueueService:
    """Service for managing review queue items"""
    
    def add_to_queue(self, matching_result: MatchingResult, db: Session) -> ReviewQueue:
        """
        Add needs_review result to queue with priority.
        
        Args:
            matching_result: MatchingResult that needs review
            db: Database session
            
        Returns:
            Created ReviewQueue item
        """
        if matching_result.match_status != "needs_review":
            raise ValueError(f"Cannot add matched result to review queue: {matching_result.match_status}")
        
        # Check if already in queue
        existing = db.query(ReviewQueue).filter(
            ReviewQueue.matching_result_id == matching_result.id,
            ReviewQueue.resolved_at.is_(None)
        ).first()
        
        if existing:
            logger.info(f"Matching result {matching_result.id} already in review queue")
            return existing
        
        # Calculate priority and get primary issue
        priority = self._calculate_priority(matching_result)
        primary_issue = self._get_primary_issue(matching_result.issues)
        sla_deadline = self._calculate_sla(priority)
        
        queue_item = ReviewQueue(
            matching_result_id=matching_result.id,
            priority=priority,
            issue_category=primary_issue.category.value if primary_issue else "unknown",
            sla_deadline=sla_deadline
        )
        
        db.add(queue_item)
        db.commit()
        db.refresh(queue_item)
        
        logger.info(f"Added matching result {matching_result.id} to review queue with priority: {priority}")
        
        return queue_item
    
    def _calculate_priority(self, result: MatchingResult) -> str:
        """
        Calculate priority based on issue types and severity.
        
        Priority levels:
        - critical: vendor mismatch, missing PO, duplicate invoice
        - high: total mismatch > 5%, quantity overage, calculation errors
        - medium: line item discrepancies, date anomalies
        - low: minor calculation differences, SKU mismatches
        """
        if not result.issues:
            return "low"
        
        issues = result.issues
        
        # Convert JSONB to list of dicts if needed
        if isinstance(issues, list) and issues:
            if isinstance(issues[0], dict):
                issue_categories = [IssueCategory(i.get("category")) for i in issues if i.get("category")]
                severities = [i.get("severity") for i in issues if i.get("severity")]
            else:
                # Already MatchingIssueV2 objects
                issue_categories = [i.category for i in issues]
                severities = [i.severity for i in issues]
        else:
            return "low"
        
        # Critical priority
        critical_categories = {
            IssueCategory.MISSING_REFERENCE,
            IssueCategory.DUPLICATE_INVOICE,
            IssueCategory.VENDOR_MISMATCH
        }
        
        if any(cat in critical_categories for cat in issue_categories):
            return "critical"
        
        if "critical" in severities:
            return "critical"
        
        # High priority
        high_categories = {
            IssueCategory.TOTAL_MISMATCH,
            IssueCategory.QUANTITY_OVERAGE,
            IssueCategory.CALCULATION_ERROR
        }
        
        # Check total mismatch percentage
        for issue in (issues if isinstance(issues[0], dict) else [i.dict() for i in issues]):
            if issue.get("category") == IssueCategory.TOTAL_MISMATCH.value:
                diff_percent = abs(issue.get("details", {}).get("difference_percent", 0))
                if diff_percent > 5:
                    return "high"
        
        if any(cat in high_categories for cat in issue_categories):
            return "high"
        
        if "high" in severities:
            return "high"
        
        # Medium priority
        medium_categories = {
            IssueCategory.LINE_ITEM_DISCREPANCY,
            IssueCategory.DATE_ANOMALY,
            IssueCategory.LINE_COUNT_MISMATCH
        }
        
        if any(cat in medium_categories for cat in issue_categories):
            return "medium"
        
        if "medium" in severities:
            return "medium"
        
        # Default to low
        return "low"
    
    def _get_primary_issue(self, issues: Optional[list]) -> Optional[MatchingIssueV2]:
        """
        Get the primary (most severe) issue.
        
        Returns:
            Primary MatchingIssueV2 or None
        """
        if not issues:
            return None
        
        # Convert JSONB to MatchingIssueV2 objects if needed
        issue_objects = []
        for issue in issues:
            if isinstance(issue, dict):
                try:
                    issue_objects.append(MatchingIssueV2(**issue))
                except Exception:
                    continue
            else:
                issue_objects.append(issue)
        
        if not issue_objects:
            return None
        
        # Sort by severity (critical > high > medium > low)
        severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        
        primary = min(issue_objects, key=lambda i: severity_order.get(i.severity, 99))
        
        return primary
    
    def _calculate_sla(self, priority: str) -> datetime:
        """
        Calculate SLA deadline based on priority.
        
        SLA rules:
        - critical: 2 hours
        - high: 8 hours
        - medium: 24 hours
        - low: 72 hours
        """
        sla_hours = {
            "critical": 2,
            "high": 8,
            "medium": 24,
            "low": 72
        }
        
        hours = sla_hours.get(priority, 72)
        deadline = datetime.now() + timedelta(hours=hours)
        
        return deadline


# Singleton instance
review_queue_service = ReviewQueueService()

