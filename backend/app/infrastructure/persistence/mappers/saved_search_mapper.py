"""Mapper for SavedSearch — EP-09."""
from __future__ import annotations

from app.domain.models.saved_search import SavedSearch
from app.infrastructure.persistence.models.orm import SavedSearchORM


def saved_search_to_domain(row: SavedSearchORM) -> SavedSearch:
    return SavedSearch(
        id=row.id,
        user_id=row.user_id,
        workspace_id=row.workspace_id,
        name=row.name,
        query_params=dict(row.query_params),
        is_shared=row.is_shared,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def saved_search_to_orm(entity: SavedSearch) -> SavedSearchORM:
    row = SavedSearchORM()
    row.id = entity.id
    row.user_id = entity.user_id
    row.workspace_id = entity.workspace_id
    row.name = entity.name
    row.query_params = entity.query_params
    row.is_shared = entity.is_shared
    row.created_at = entity.created_at
    row.updated_at = entity.updated_at
    return row
