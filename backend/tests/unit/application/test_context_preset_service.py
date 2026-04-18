"""Unit tests for ContextPresetService — EP-10 admin context presets."""
from __future__ import annotations

from uuid import UUID, uuid4
from unittest.mock import AsyncMock, MagicMock

import pytest

from app.application.services.context_preset_service import (
    ContextPresetNotFoundError,
    ContextPresetService,
    DuplicatePresetNameError,
    PresetInUseError,
)
from app.domain.models.context_preset import ContextPreset, ContextSource
from app.domain.repositories.context_preset_repository import IContextPresetRepository

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class FakeContextPresetRepo(IContextPresetRepository):
    def __init__(self) -> None:
        self._by_id: dict[UUID, ContextPreset] = {}

    async def create(self, preset: ContextPreset) -> ContextPreset:
        self._by_id[preset.id] = preset
        return preset

    async def get_by_id(self, preset_id: UUID, workspace_id: UUID) -> ContextPreset | None:
        p = self._by_id.get(preset_id)
        if p and p.workspace_id == workspace_id and not p.is_deleted():
            return p
        return None

    async def list_for_workspace(self, workspace_id: UUID) -> list[ContextPreset]:
        return [p for p in self._by_id.values() if p.workspace_id == workspace_id and not p.is_deleted()]

    async def save(self, preset: ContextPreset) -> ContextPreset:
        self._by_id[preset.id] = preset
        return preset

    async def get_by_name(self, workspace_id: UUID, name: str) -> ContextPreset | None:
        return next(
            (p for p in self._by_id.values()
             if p.workspace_id == workspace_id and p.name == name.strip() and not p.is_deleted()),
            None,
        )


class FakeAudit:
    def __init__(self) -> None:
        self.events: list[dict] = []

    async def log_event(self, **kwargs: object) -> None:
        self.events.append(kwargs)


_WS_ID = uuid4()
_ACTOR_ID = uuid4()


def _make_service(repo: FakeContextPresetRepo | None = None) -> tuple[ContextPresetService, FakeAudit]:
    r = repo or FakeContextPresetRepo()
    audit = FakeAudit()
    session = AsyncMock()
    session.execute = AsyncMock(return_value=MagicMock(
        scalar_one_or_none=MagicMock(return_value=None)
    ))
    svc = ContextPresetService(repo=r, audit=audit, session=session)  # type: ignore[arg-type]
    return svc, audit


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestContextPresetService:
    @pytest.mark.asyncio
    async def test_create_success(self) -> None:
        repo = FakeContextPresetRepo()
        svc, audit = _make_service(repo)

        preset = await svc.create_preset(
            _WS_ID,
            name="My Preset",
            description="desc",
            sources=[{"label": "docs", "url": "https://docs.example.com"}],
            actor_id=_ACTOR_ID,
        )

        assert preset.name == "My Preset"
        assert len(preset.sources) == 1
        assert any(e["action"] == "context_preset_created" for e in audit.events)

    @pytest.mark.asyncio
    async def test_create_duplicate_name_raises_409(self) -> None:
        repo = FakeContextPresetRepo()
        svc, _ = _make_service(repo)

        await svc.create_preset(
            _WS_ID, name="Dupe", description=None, sources=[], actor_id=_ACTOR_ID
        )
        with pytest.raises(DuplicatePresetNameError):
            await svc.create_preset(
                _WS_ID, name="Dupe", description=None, sources=[], actor_id=_ACTOR_ID
            )

    @pytest.mark.asyncio
    async def test_list_returns_active_presets(self) -> None:
        repo = FakeContextPresetRepo()
        svc, _ = _make_service(repo)

        await svc.create_preset(_WS_ID, name="A", description=None, sources=[], actor_id=_ACTOR_ID)
        await svc.create_preset(_WS_ID, name="B", description=None, sources=[], actor_id=_ACTOR_ID)

        presets = await svc.list_presets(_WS_ID)
        assert len(presets) == 2

    @pytest.mark.asyncio
    async def test_update_name(self) -> None:
        repo = FakeContextPresetRepo()
        svc, _ = _make_service(repo)
        preset = await svc.create_preset(_WS_ID, name="Old", description=None, sources=[], actor_id=_ACTOR_ID)

        updated = await svc.update_preset(
            _WS_ID, preset.id, name="New", actor_id=_ACTOR_ID
        )
        assert updated.name == "New"

    @pytest.mark.asyncio
    async def test_update_not_found_raises_404(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ContextPresetNotFoundError):
            await svc.update_preset(_WS_ID, uuid4(), name="X", actor_id=_ACTOR_ID)

    @pytest.mark.asyncio
    async def test_delete_not_in_use_succeeds(self) -> None:
        repo = FakeContextPresetRepo()
        svc, audit = _make_service(repo)
        preset = await svc.create_preset(_WS_ID, name="ToDelete", description=None, sources=[], actor_id=_ACTOR_ID)

        await svc.delete_preset(_WS_ID, preset.id, _ACTOR_ID)
        assert repo._by_id[preset.id].is_deleted()
        assert any(e["action"] == "context_preset_deleted" for e in audit.events)

    @pytest.mark.asyncio
    async def test_delete_not_found_raises_404(self) -> None:
        svc, _ = _make_service()
        with pytest.raises(ContextPresetNotFoundError):
            await svc.delete_preset(_WS_ID, uuid4(), _ACTOR_ID)

    @pytest.mark.asyncio
    async def test_get_wrong_workspace_returns_not_found(self) -> None:
        repo = FakeContextPresetRepo()
        svc, _ = _make_service(repo)
        preset = await svc.create_preset(_WS_ID, name="P", description=None, sources=[], actor_id=_ACTOR_ID)

        with pytest.raises(ContextPresetNotFoundError):
            await svc.get_preset(uuid4(), preset.id)
