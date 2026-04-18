"""EP-04 Phase 5 — CompletenessService + GapService unit tests.

Uses in-memory fakes for all I/O boundaries.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from typing import Any
from uuid import UUID, uuid4

import pytest

from app.domain.quality.dimension_result import DimensionResult
from app.domain.quality.score_calculator import compute as score_compute

# ---------------------------------------------------------------------------
# ScoreCalculator unit tests
# ---------------------------------------------------------------------------


def _dim(name: str, *, applicable: bool, filled: bool, weight: float = 0.10) -> DimensionResult:
    return DimensionResult(
        dimension=name,
        weight=weight,
        applicable=applicable,
        filled=filled,
        score=1.0 if filled else 0.0,
        message=None if filled or not applicable else f"{name} gap",
    )


class TestScoreCalculator:
    def test_all_inapplicable_returns_zero_no_crash(self) -> None:
        dims = [_dim("x", applicable=False, filled=False)]
        result = score_compute(dims)
        assert result.score == 0
        assert result.level == "low"

    def test_all_filled_applicable_gives_100(self) -> None:
        dims = [
            _dim("a", applicable=True, filled=True, weight=0.5),
            _dim("b", applicable=True, filled=True, weight=0.5),
        ]
        result = score_compute(dims)
        assert result.score == 100
        assert result.level == "ready"

    def test_all_unfilled_applicable_gives_0(self) -> None:
        dims = [
            _dim("a", applicable=True, filled=False, weight=0.5),
            _dim("b", applicable=True, filled=False, weight=0.5),
        ]
        result = score_compute(dims)
        assert result.score == 0
        assert result.level == "low"

    def test_half_filled_gives_50(self) -> None:
        dims = [
            _dim("a", applicable=True, filled=True, weight=0.5),
            _dim("b", applicable=True, filled=False, weight=0.5),
        ]
        result = score_compute(dims)
        assert result.score == 50
        assert result.level == "medium"

    def test_inapplicable_dimensions_excluded_weights_renormalized(self) -> None:
        # Only "a" is applicable — weight renormalizes to 1.0
        dims = [
            _dim("a", applicable=True, filled=True, weight=0.5),
            _dim("b", applicable=False, filled=False, weight=0.5),
        ]
        result = score_compute(dims)
        assert result.score == 100
        renorm_applicable = [d for d in result.dimensions if d.applicable]
        assert abs(sum(d.weight for d in renorm_applicable) - 1.0) < 1e-9

    def test_band_low(self) -> None:
        dims = [_dim("a", applicable=True, filled=False, weight=1.0)]
        assert score_compute(dims).level == "low"

    def test_band_medium(self) -> None:
        # 50% fills → score 50 → medium
        dims = [
            _dim("a", applicable=True, filled=True, weight=0.5),
            _dim("b", applicable=True, filled=False, weight=0.5),
        ]
        assert score_compute(dims).level == "medium"

    def test_band_high(self) -> None:
        # 75% → 75 → high
        dims = [
            _dim("a", applicable=True, filled=True, weight=0.25),
            _dim("b", applicable=True, filled=True, weight=0.25),
            _dim("c", applicable=True, filled=True, weight=0.25),
            _dim("d", applicable=True, filled=False, weight=0.25),
        ]
        result = score_compute(dims)
        assert result.score == 75
        assert result.level == "high"

    def test_band_ready(self) -> None:
        dims = [_dim("a", applicable=True, filled=True, weight=1.0)]
        assert score_compute(dims).level == "ready"

    def test_result_includes_inapplicable_dimensions(self) -> None:
        dims = [
            _dim("a", applicable=True, filled=True, weight=1.0),
            _dim("b", applicable=False, filled=False, weight=0.0),
        ]
        result = score_compute(dims)
        names = {d.dimension for d in result.dimensions}
        assert "b" in names

    def test_cached_flag_false_by_default(self) -> None:
        dims = [_dim("a", applicable=True, filled=True, weight=1.0)]
        result = score_compute(dims)
        assert result.cached is False


# ---------------------------------------------------------------------------
# CompletenessService unit tests with fakes
# ---------------------------------------------------------------------------


class _FakeSection:
    def __init__(self) -> None:
        self.id = uuid4()


class _FakeWorkItem:
    def __init__(self) -> None:
        self.type = "bug"
        self.owner_id = uuid4()
        self.owner_suspended_flag = False


class _FakeWorkItemRepo:
    def __init__(self, item: Any = None) -> None:
        self._item = item
        self.called = False

    async def get(self, work_item_id: UUID, workspace_id: UUID) -> Any:
        self.called = True
        return self._item


class _FakeSectionRepo:
    def __init__(self, sections: list[Any] | None = None) -> None:
        self._sections = sections or []
        self.called = False

    async def get_by_work_item(self, work_item_id: UUID) -> list[Any]:
        self.called = True
        return self._sections


class _FakeValidatorRepo:
    def __init__(self) -> None:
        self.called = False

    async def get_by_work_item(self, work_item_id: UUID) -> list[Any]:
        self.called = True
        return []


class _FakeCache:
    def __init__(self) -> None:
        self._store: dict[str, str] = {}

    async def get(self, key: str) -> str | None:
        return self._store.get(key)

    async def set(self, key: str, value: str, *, ttl_seconds: int = 60) -> None:
        self._store[key] = value

    async def delete(self, key: str) -> None:
        self._store.pop(key, None)


@pytest.fixture()
def fake_work_item() -> _FakeWorkItem:
    return _FakeWorkItem()


@pytest.fixture()
def fake_cache() -> _FakeCache:
    return _FakeCache()


class TestCompletenessService:
    @pytest.mark.asyncio
    async def test_cache_hit_skips_db_calls(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService

        # Pre-warm cache with a serialised result
        dims = [_dim("x", applicable=True, filled=True, weight=1.0)]
        cached_payload = json.dumps(
            {"score": 100, "level": "ready", "dimensions": [asdict(d) for d in dims]}
        )
        work_item_id = uuid4()
        workspace_id = uuid4()
        await fake_cache.set(f"completeness:{work_item_id}", cached_payload)

        wi_repo = _FakeWorkItemRepo(fake_work_item)
        sec_repo = _FakeSectionRepo()
        val_repo = _FakeValidatorRepo()

        svc = CompletenessService(
            work_item_repo=wi_repo,  # type: ignore[arg-type]
            section_repo=sec_repo,  # type: ignore[arg-type]
            validator_repo=val_repo,  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        result = await svc.compute(work_item_id, workspace_id)

        assert result.cached is True
        assert wi_repo.called is False
        assert sec_repo.called is False
        assert val_repo.called is False

    @pytest.mark.asyncio
    async def test_cache_miss_calls_repos_and_populates_cache(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService

        work_item_id = uuid4()
        workspace_id = uuid4()

        wi_repo = _FakeWorkItemRepo(fake_work_item)
        sec_repo = _FakeSectionRepo()
        val_repo = _FakeValidatorRepo()

        svc = CompletenessService(
            work_item_repo=wi_repo,  # type: ignore[arg-type]
            section_repo=sec_repo,  # type: ignore[arg-type]
            validator_repo=val_repo,  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        result = await svc.compute(work_item_id, workspace_id)

        assert result.cached is False
        assert wi_repo.called is True
        assert sec_repo.called is True
        # Cache was populated
        assert await fake_cache.get(f"completeness:{work_item_id}") is not None

    @pytest.mark.asyncio
    async def test_not_found_raises_lookup_error(self, fake_cache: _FakeCache) -> None:
        from app.application.services.completeness_service import CompletenessService

        wi_repo = _FakeWorkItemRepo(None)  # returns None → not found
        sec_repo = _FakeSectionRepo()
        val_repo = _FakeValidatorRepo()

        svc = CompletenessService(
            work_item_repo=wi_repo,  # type: ignore[arg-type]
            section_repo=sec_repo,  # type: ignore[arg-type]
            validator_repo=val_repo,  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        with pytest.raises(LookupError):
            await svc.compute(uuid4(), uuid4())

    @pytest.mark.asyncio
    async def test_invalidate_removes_cache_key(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService

        work_item_id = uuid4()
        await fake_cache.set(
            f"completeness:{work_item_id}", '{"score":100,"level":"ready","dimensions":[]}'
        )

        svc = CompletenessService(
            work_item_repo=_FakeWorkItemRepo(fake_work_item),  # type: ignore[arg-type]
            section_repo=_FakeSectionRepo(),  # type: ignore[arg-type]
            validator_repo=_FakeValidatorRepo(),  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        await svc.invalidate(work_item_id)
        assert await fake_cache.get(f"completeness:{work_item_id}") is None


# ---------------------------------------------------------------------------
# GapService unit tests
# ---------------------------------------------------------------------------


class TestGapService:
    @pytest.mark.asyncio
    async def test_returns_only_unfilled_applicable_dimensions(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService, GapService

        work_item_id = uuid4()
        # Inject a cache result with one filled + one unfilled applicable dim
        dims = [
            DimensionResult(
                "acceptance_criteria",
                weight=0.22,
                applicable=True,
                filled=False,
                score=0.0,
                message="fill ac",
            ),
            DimensionResult(
                "ownership", weight=0.10, applicable=True, filled=True, score=1.0, message=None
            ),
        ]
        payload = json.dumps({"score": 30, "level": "low", "dimensions": [asdict(d) for d in dims]})
        await fake_cache.set(f"completeness:{work_item_id}", payload)

        completeness = CompletenessService(
            work_item_repo=_FakeWorkItemRepo(fake_work_item),  # type: ignore[arg-type]
            section_repo=_FakeSectionRepo(),  # type: ignore[arg-type]
            validator_repo=_FakeValidatorRepo(),  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        gap_svc = GapService(completeness)
        gaps = await gap_svc.list(work_item_id, uuid4())

        assert len(gaps) == 1
        assert gaps[0]["dimension"] == "acceptance_criteria"

    @pytest.mark.asyncio
    async def test_empty_when_all_filled(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService, GapService

        work_item_id = uuid4()
        dims = [
            DimensionResult(
                "ownership", weight=1.0, applicable=True, filled=True, score=1.0, message=None
            )
        ]
        payload = json.dumps(
            {"score": 100, "level": "ready", "dimensions": [asdict(d) for d in dims]}
        )
        await fake_cache.set(f"completeness:{work_item_id}", payload)

        completeness = CompletenessService(
            work_item_repo=_FakeWorkItemRepo(fake_work_item),  # type: ignore[arg-type]
            section_repo=_FakeSectionRepo(),  # type: ignore[arg-type]
            validator_repo=_FakeValidatorRepo(),  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        gap_svc = GapService(completeness)
        gaps = await gap_svc.list(work_item_id, uuid4())
        assert gaps == []

    @pytest.mark.asyncio
    async def test_blocking_gap_has_severity(
        self, fake_work_item: _FakeWorkItem, fake_cache: _FakeCache
    ) -> None:
        from app.application.services.completeness_service import CompletenessService, GapService

        work_item_id = uuid4()
        # acceptance_criteria weight >= 0.12 → blocking
        dims = [
            DimensionResult(
                "acceptance_criteria",
                weight=0.22,
                applicable=True,
                filled=False,
                score=0.0,
                message="fill ac",
            ),
        ]
        payload = json.dumps({"score": 0, "level": "low", "dimensions": [asdict(d) for d in dims]})
        await fake_cache.set(f"completeness:{work_item_id}", payload)

        completeness = CompletenessService(
            work_item_repo=_FakeWorkItemRepo(fake_work_item),  # type: ignore[arg-type]
            section_repo=_FakeSectionRepo(),  # type: ignore[arg-type]
            validator_repo=_FakeValidatorRepo(),  # type: ignore[arg-type]
            cache=fake_cache,  # type: ignore[arg-type]
        )
        gap_svc = GapService(completeness)
        gaps = await gap_svc.list(work_item_id, uuid4())
        assert gaps[0]["severity"] == "blocking"
