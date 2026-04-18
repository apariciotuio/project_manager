"""EP-18 — Unit tests for get_work_item_completeness MCP tool handler.

Tests exercise the handler in isolation using a FakeCompletenessService.
No DB, no MCP SDK required.

Scenarios:
- Happy path: returns {overall_score, sections} with correct types
- sections list contains {id, title, score} entries
- LookupError from service maps to {error: "not_found"}
- cross-workspace: service raises LookupError for wrong workspace → not_found
- invalid UUID raises ValueError
- missing work_item_id raises KeyError
"""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from app.domain.quality.dimension_result import CompletenessResult, DimensionResult
from apps.mcp_server.tools.get_work_item_completeness import handle_get_work_item_completeness

WORKSPACE_ID = uuid4()

_EXPECTED_KEYS = {"overall_score", "sections"}

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_result(
    score: int = 72,
    dimensions: list[DimensionResult] | None = None,
) -> CompletenessResult:
    if dimensions is None:
        dimensions = [
            DimensionResult(
                dimension="summary",
                weight=0.2,
                applicable=True,
                filled=True,
                score=1.0,
                message=None,
            ),
            DimensionResult(
                dimension="acceptance_criteria",
                weight=0.2,
                applicable=True,
                filled=False,
                score=0.0,
                message="Missing acceptance criteria",
            ),
        ]
    return CompletenessResult(score=score, level="medium", dimensions=dimensions)


class FakeCompletenessService:
    """Minimal fake — only covers compute."""

    def __init__(self, result: CompletenessResult | Exception) -> None:
        self._result = result
        self.calls: list[tuple[UUID, UUID]] = []

    async def compute(self, work_item_id: UUID, workspace_id: UUID) -> CompletenessResult:
        self.calls.append((work_item_id, workspace_id))
        if isinstance(self._result, Exception):
            raise self._result
        return self._result


# ---------------------------------------------------------------------------
# Schema shape tests
# ---------------------------------------------------------------------------


class TestGetWorkItemCompletenessShape:
    @pytest.mark.asyncio
    async def test_happy_path_returns_expected_keys(self) -> None:
        svc = FakeCompletenessService(_make_result())
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert set(result.keys()) == _EXPECTED_KEYS

    @pytest.mark.asyncio
    async def test_overall_score_matches_service_result(self) -> None:
        svc = FakeCompletenessService(_make_result(score=55))
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert result["overall_score"] == 55

    @pytest.mark.asyncio
    async def test_sections_is_list(self) -> None:
        svc = FakeCompletenessService(_make_result())
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert isinstance(result["sections"], list)

    @pytest.mark.asyncio
    async def test_sections_contain_expected_keys(self) -> None:
        svc = FakeCompletenessService(_make_result())
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert len(result["sections"]) > 0
        for section in result["sections"]:
            assert "id" in section
            assert "title" in section
            assert "score" in section

    @pytest.mark.asyncio
    async def test_unfilled_section_includes_missing_fields(self) -> None:
        dims = [
            DimensionResult(
                dimension="acceptance_criteria",
                weight=0.2,
                applicable=True,
                filled=False,
                score=0.0,
                message="Missing acceptance criteria",
            ),
        ]
        svc = FakeCompletenessService(_make_result(dimensions=dims))
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        unfilled = [s for s in result["sections"] if not s.get("filled", True)]
        assert len(unfilled) > 0
        assert "missing_fields" in unfilled[0]


# ---------------------------------------------------------------------------
# Not-found and cross-workspace tests
# ---------------------------------------------------------------------------


class TestGetWorkItemCompletenessNotFound:
    @pytest.mark.asyncio
    async def test_lookup_error_returns_not_found(self) -> None:
        svc = FakeCompletenessService(LookupError("work item not found"))
        work_item_id = uuid4()

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_cross_workspace_returns_not_found(self) -> None:
        svc = FakeCompletenessService(LookupError("wrong workspace"))

        result = await handle_get_work_item_completeness(
            arguments={"work_item_id": str(uuid4())},
            workspace_id=uuid4(),
            service=svc,
        )

        assert result == {"error": "not_found"}

    @pytest.mark.asyncio
    async def test_service_called_with_correct_ids(self) -> None:
        svc = FakeCompletenessService(_make_result())
        work_item_id = uuid4()

        await handle_get_work_item_completeness(
            arguments={"work_item_id": str(work_item_id)},
            workspace_id=WORKSPACE_ID,
            service=svc,
        )

        assert len(svc.calls) == 1
        assert svc.calls[0] == (work_item_id, WORKSPACE_ID)


# ---------------------------------------------------------------------------
# Validation tests
# ---------------------------------------------------------------------------


class TestGetWorkItemCompletenessValidation:
    @pytest.mark.asyncio
    async def test_invalid_uuid_raises_value_error(self) -> None:
        svc = FakeCompletenessService(_make_result())

        with pytest.raises(ValueError):
            await handle_get_work_item_completeness(
                arguments={"work_item_id": "not-a-uuid"},
                workspace_id=WORKSPACE_ID,
                service=svc,
            )

    @pytest.mark.asyncio
    async def test_missing_work_item_id_raises(self) -> None:
        svc = FakeCompletenessService(_make_result())

        with pytest.raises((KeyError, ValueError)):
            await handle_get_work_item_completeness(
                arguments={},
                workspace_id=WORKSPACE_ID,
                service=svc,
            )
