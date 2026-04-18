"""Unit tests for ExportService — EP-11.

Verifies that after a successful Jira export:
  - external_jira_key is populated (canonical column, migration 0118)
  - export_reference is also populated (backward-compat dual-write)
  - exported_at is set
  - save() is called once with the updated work item
"""
from __future__ import annotations

from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock
from uuid import uuid4

import pytest

from app.application.services.export_service import ExportService, WorkItemNotFoundError
from app.domain.models.work_item import WorkItem
from app.domain.value_objects.work_item_state import WorkItemState
from app.domain.value_objects.work_item_type import WorkItemType
from app.infrastructure.adapters.jira_adapter import JiraIssue


def _make_work_item() -> WorkItem:
    return WorkItem.create(
        title="Fix the login bug",
        type=WorkItemType.STORY,
        owner_id=uuid4(),
        creator_id=uuid4(),
        project_id=uuid4(),
    )


def _make_service(
    work_item: WorkItem | None = None,
    jira_key: str = "PROJ-42",
) -> tuple[ExportService, AsyncMock, AsyncMock]:
    repo = AsyncMock()
    repo.get.return_value = work_item
    repo.save = AsyncMock()

    jira_client = AsyncMock()
    jira_client.create_issue.return_value = JiraIssue(
        key=jira_key,
        self_url="https://example.atlassian.net/rest/api/3/issue/42",
        id="42",
    )

    service = ExportService(
        work_item_repo=repo,
        jira_client=jira_client,
        audit_service=None,
    )
    return service, repo, jira_client


@pytest.mark.asyncio
async def test_export_sets_external_jira_key() -> None:
    item = _make_work_item()
    service, repo, _ = _make_service(work_item=item, jira_key="MYPROJ-7")

    await service.export_work_item_to_jira(
        work_item_id=item.id,
        workspace_id=uuid4(),
        user_id=uuid4(),
        project_key="MYPROJ",
    )

    assert item.external_jira_key == "MYPROJ-7"


@pytest.mark.asyncio
async def test_export_dual_writes_export_reference_for_compat() -> None:
    item = _make_work_item()
    service, repo, _ = _make_service(work_item=item, jira_key="BACK-1")

    await service.export_work_item_to_jira(
        work_item_id=item.id,
        workspace_id=uuid4(),
        user_id=uuid4(),
        project_key="BACK",
    )

    assert item.export_reference == "BACK-1"


@pytest.mark.asyncio
async def test_export_sets_exported_at() -> None:
    item = _make_work_item()
    assert item.exported_at is None
    service, repo, _ = _make_service(work_item=item)

    await service.export_work_item_to_jira(
        work_item_id=item.id,
        workspace_id=uuid4(),
        user_id=uuid4(),
        project_key="PROJ",
    )

    assert item.exported_at is not None


@pytest.mark.asyncio
async def test_export_saves_work_item() -> None:
    item = _make_work_item()
    workspace_id = uuid4()
    service, repo, _ = _make_service(work_item=item)

    await service.export_work_item_to_jira(
        work_item_id=item.id,
        workspace_id=workspace_id,
        user_id=uuid4(),
        project_key="PROJ",
    )

    repo.save.assert_awaited_once_with(item, workspace_id)


@pytest.mark.asyncio
async def test_export_raises_not_found_when_item_missing() -> None:
    service, _, _ = _make_service(work_item=None)

    with pytest.raises(WorkItemNotFoundError):
        await service.export_work_item_to_jira(
            work_item_id=uuid4(),
            workspace_id=uuid4(),
            user_id=uuid4(),
            project_key="PROJ",
        )
