"""Unit tests for Tag and WorkItemTag domain models — EP-15."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.tag import Tag, TagArchivedError, WorkItemTag


class TestTagCreate:
    def test_create_sets_name(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="backend", created_by=uuid4())
        assert tag.name == "backend"

    def test_create_strips_whitespace(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="  api  ", created_by=uuid4())
        assert tag.name == "api"

    def test_create_empty_name_raises(self) -> None:
        with pytest.raises(ValueError, match="empty"):
            Tag.create(workspace_id=uuid4(), name="   ", created_by=uuid4())

    def test_create_not_archived(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="x", created_by=uuid4())
        assert not tag.is_archived
        assert tag.archived_at is None

    def test_create_with_color(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="x", created_by=uuid4(), color="#ff0000")
        assert tag.color == "#ff0000"


class TestTagArchive:
    def test_archive_sets_archived_at(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="x", created_by=uuid4())
        tag.archive()
        assert tag.is_archived
        assert tag.archived_at is not None

    def test_archive_idempotent(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="x", created_by=uuid4())
        tag.archive()
        first = tag.archived_at
        tag.archive()
        assert tag.archived_at == first


class TestTagRename:
    def test_rename_updates_name(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="old", created_by=uuid4())
        tag.rename("new")
        assert tag.name == "new"

    def test_rename_strips_whitespace(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="old", created_by=uuid4())
        tag.rename("  new  ")
        assert tag.name == "new"

    def test_rename_empty_raises(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="old", created_by=uuid4())
        with pytest.raises(ValueError):
            tag.rename("   ")

    def test_rename_archived_raises(self) -> None:
        tag = Tag.create(workspace_id=uuid4(), name="old", created_by=uuid4())
        tag.archive()
        with pytest.raises(TagArchivedError):
            tag.rename("new")


class TestWorkItemTag:
    def test_create_work_item_tag(self) -> None:
        wit = WorkItemTag.create(
            work_item_id=uuid4(),
            tag_id=uuid4(),
            created_by=uuid4(),
        )
        assert wit.id is not None
        assert wit.created_at is not None
