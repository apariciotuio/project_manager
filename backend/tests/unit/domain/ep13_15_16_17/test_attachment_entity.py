"""Unit tests for Attachment domain model — EP-16."""
from __future__ import annotations

from uuid import uuid4

import pytest

from app.domain.models.attachment import Attachment


class TestAttachmentCreate:
    def test_create_sets_fields(self) -> None:
        a = Attachment.create(
            workspace_id=uuid4(),
            uploaded_by=uuid4(),
            filename="report.pdf",
            content_type="application/pdf",
            size_bytes=1024,
            storage_key="uploads/abc.pdf",
            work_item_id=uuid4(),
        )
        assert a.filename == "report.pdf"
        assert a.size_bytes == 1024
        assert not a.is_deleted

    def test_create_strips_filename(self) -> None:
        a = Attachment.create(
            workspace_id=uuid4(),
            uploaded_by=uuid4(),
            filename="  doc.txt  ",
            content_type="text/plain",
            size_bytes=10,
            storage_key="k",
        )
        assert a.filename == "doc.txt"

    def test_create_empty_filename_raises(self) -> None:
        with pytest.raises(ValueError, match="Filename"):
            Attachment.create(
                workspace_id=uuid4(),
                uploaded_by=uuid4(),
                filename="  ",
                content_type="text/plain",
                size_bytes=10,
                storage_key="k",
            )

    def test_create_negative_size_raises(self) -> None:
        with pytest.raises(ValueError, match="size_bytes"):
            Attachment.create(
                workspace_id=uuid4(),
                uploaded_by=uuid4(),
                filename="f.txt",
                content_type="text/plain",
                size_bytes=-1,
                storage_key="k",
            )

    def test_create_zero_size_ok(self) -> None:
        a = Attachment.create(
            workspace_id=uuid4(),
            uploaded_by=uuid4(),
            filename="empty.txt",
            content_type="text/plain",
            size_bytes=0,
            storage_key="k",
        )
        assert a.size_bytes == 0


class TestAttachmentSoftDelete:
    def test_soft_delete_sets_deleted_at(self) -> None:
        a = Attachment.create(
            workspace_id=uuid4(),
            uploaded_by=uuid4(),
            filename="f.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="k",
        )
        a.soft_delete()
        assert a.is_deleted
        assert a.deleted_at is not None

    def test_soft_delete_idempotent(self) -> None:
        a = Attachment.create(
            workspace_id=uuid4(),
            uploaded_by=uuid4(),
            filename="f.txt",
            content_type="text/plain",
            size_bytes=1,
            storage_key="k",
        )
        a.soft_delete()
        first = a.deleted_at
        a.soft_delete()
        assert a.deleted_at == first
