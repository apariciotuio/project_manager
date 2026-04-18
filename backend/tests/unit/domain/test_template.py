"""Unit tests for Template domain entity. RED phase — EP-02 Phase 2."""

from __future__ import annotations

from datetime import UTC, datetime
from uuid import uuid4

import pytest


class TestTemplateInvariants:
    def test_system_template_with_workspace_id_raises(self) -> None:
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        with pytest.raises(ValueError, match="system template"):
            Template(
                id=uuid4(),
                workspace_id=uuid4(),  # must be None for system templates
                type=WorkItemType.BUG,
                name="Bug Report",
                content="## Summary",
                is_system=True,
                created_by=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_content_over_50000_chars_raises(self) -> None:
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        with pytest.raises(ValueError, match="content"):
            Template(
                id=uuid4(),
                workspace_id=uuid4(),
                type=WorkItemType.BUG,
                name="Bug Report",
                content="x" * 50001,
                is_system=False,
                created_by=None,
                created_at=datetime.now(UTC),
                updated_at=datetime.now(UTC),
            )

    def test_content_at_exactly_50000_chars_is_valid(self) -> None:
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        t = Template(
            id=uuid4(),
            workspace_id=uuid4(),
            type=WorkItemType.BUG,
            name="Bug Report",
            content="x" * 50000,
            is_system=False,
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert len(t.content) == 50000

    def test_system_template_without_workspace_id_is_valid(self) -> None:
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        t = Template(
            id=uuid4(),
            workspace_id=None,
            type=WorkItemType.BUG,
            name="Default Bug",
            content="## Summary\n\n## Steps to Reproduce",
            is_system=True,
            created_by=None,
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert t.is_system is True
        assert t.workspace_id is None

    def test_workspace_template_requires_workspace_id(self) -> None:
        """Non-system templates with no workspace_id are allowed (optional)."""
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        # workspace_id=None + is_system=False is valid (future flexibility)
        t = Template(
            id=uuid4(),
            workspace_id=None,
            type=WorkItemType.TASK,
            name="Generic Task",
            content="## Description",
            is_system=False,
            created_by=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert t.workspace_id is None
        assert t.is_system is False

    def test_type_is_work_item_type_enum(self) -> None:
        from app.domain.models.template import Template
        from app.domain.value_objects.work_item_type import WorkItemType

        t = Template(
            id=uuid4(),
            workspace_id=uuid4(),
            type=WorkItemType.ENHANCEMENT,
            name="Enhancement",
            content="## Goal",
            is_system=False,
            created_by=uuid4(),
            created_at=datetime.now(UTC),
            updated_at=datetime.now(UTC),
        )
        assert t.type == WorkItemType.ENHANCEMENT
