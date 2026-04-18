"""Completeness scoring — pure function, no external dependencies.

Scores a WorkItem from its field attributes alone (no DB access, no sections).
Used by WorkItemService to persist completeness_score and gate READY transitions.

Algorithm — additive, weights sum to 100:
  TITLE_POINTS        = 25  (title stripped length >= TITLE_MIN_LEN)
  DESCRIPTION_POINTS  = 35  (description length >= DESCRIPTION_MIN_LEN)
  PRIORITY_POINTS     = 15  (priority is not None)
  DUE_DATE_POINTS     = 10  (due_date is not None)
  OWNER_POINTS        = 15  (owner_id is not None and owner_suspended_flag is False)
"""
from __future__ import annotations

from app.domain.models.work_item import WorkItem

# Thresholds
TITLE_MIN_LEN: int = 10
DESCRIPTION_MIN_LEN: int = 50

# Weights
TITLE_POINTS: int = 25
DESCRIPTION_POINTS: int = 35
PRIORITY_POINTS: int = 15
DUE_DATE_POINTS: int = 10
OWNER_POINTS: int = 15


def compute_completeness(item: WorkItem) -> int:
    """Return a 0-100 integer completeness score based on WorkItem field values."""
    score = 0

    if item.title and len(item.title.strip()) >= TITLE_MIN_LEN:
        score += TITLE_POINTS

    if item.description and len(item.description) >= DESCRIPTION_MIN_LEN:
        score += DESCRIPTION_POINTS

    if item.priority is not None:
        score += PRIORITY_POINTS

    if item.due_date is not None:
        score += DUE_DATE_POINTS

    if item.owner_id is not None and not item.owner_suspended_flag:
        score += OWNER_POINTS

    return score
