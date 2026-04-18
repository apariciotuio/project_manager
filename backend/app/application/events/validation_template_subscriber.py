"""EP-10 — Subscriber: seed validation_requirements from templates on work item creation."""

from __future__ import annotations

import logging

from app.application.events.event_bus import EventBus
from app.application.events.events import WorkItemCreatedEvent

logger = logging.getLogger(__name__)


def register_validation_template_subscribers(bus: EventBus) -> None:
    """Wire WorkItemCreatedEvent → seed validation requirements from matching templates.

    For each active ValidationRuleTemplate matching (workspace_id, work_item_type),
    we upsert a validation_requirements row so the work item has seeded requirements
    at creation time.
    """

    async def _on_work_item_created(event: WorkItemCreatedEvent) -> None:
        from app.infrastructure.persistence.database import get_session_factory
        from app.infrastructure.persistence.models.orm import ValidationRequirementORM
        from app.infrastructure.persistence.validation_rule_template_repository_impl import (
            ValidationRuleTemplateRepositoryImpl,
        )

        factory = get_session_factory()
        async with factory() as session:
            try:
                template_repo = ValidationRuleTemplateRepositoryImpl(session)

                work_item_type_str = (
                    event.type.value if hasattr(event.type, "value") else str(event.type)
                )

                templates = await template_repo.list_matching(
                    workspace_id=event.workspace_id,
                    work_item_type=work_item_type_str,
                )

                for tmpl in templates:
                    rule_id = f"vrt:{tmpl.id}:wi:{event.work_item_id}"
                    existing = await session.get(ValidationRequirementORM, rule_id)
                    if existing is None:
                        row = ValidationRequirementORM()
                        row.rule_id = rule_id
                        row.label = tmpl.name
                        row.required = tmpl.is_mandatory
                        row.applies_to = work_item_type_str
                        row.workspace_id = event.workspace_id
                        row.description = tmpl.default_description
                        row.is_active = True
                        session.add(row)

                await session.commit()
                logger.info(
                    "validation_template_subscriber: seeded %d requirements for work_item=%s",
                    len(templates),
                    event.work_item_id,
                )
            except Exception:
                await session.rollback()
                logger.exception(
                    "validation_template_subscriber: failed to seed for work_item=%s",
                    event.work_item_id,
                )

    bus.subscribe(WorkItemCreatedEvent, _on_work_item_created)
