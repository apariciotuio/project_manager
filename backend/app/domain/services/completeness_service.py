"""Completeness scoring — pure function, no external dependencies.

EP-04 will implement the real scoring algorithm. For EP-01 this is a stub that
always returns 0 so the service layer can call it without exploding.
"""
from __future__ import annotations

from app.domain.models.work_item import WorkItem


def compute_completeness(item: WorkItem) -> int:  # noqa: ARG001
    # TODO(EP-04): implement scoring based on title, description, type-relevant fields,
    # mandatory validations, next-step computability, etc.
    return 0
