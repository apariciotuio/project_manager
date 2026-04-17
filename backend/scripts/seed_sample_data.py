"""Seed sample work items, sections, tasks, tags, and a team for manual QA.

Usage:
    cd backend && PYTHONPATH=. python scripts/seed_sample_data.py

Idempotent — checks for existing rows by title before inserting.
Requires: workspace 'tuio' and at least one user (run seed_dev.py first).
"""
from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime
from uuid import uuid4

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.config.settings import get_settings
from app.infrastructure.persistence.database import get_session_factory
from app.infrastructure.persistence.models.orm import (
    TagORM,
    TaskNodeORM,
    TeamMembershipORM,
    TeamORM,
    UserORM,
    WorkItemORM,
    WorkItemSectionORM,
    WorkItemTagORM,
    WorkspaceORM,
)

WORKSPACE_SLUG = "tuio"

SAMPLE_ITEMS = [
    {
        "title": "Corregir error de validación en formulario de cotización",
        "type": "bug",
        "state": "draft",
        "description": "El formulario de cotización acepta valores negativos en el campo de suma asegurada. Debería validar que el monto sea positivo y mostrar un mensaje de error claro.",
        "priority": "high",
        "completeness_score": 35,
    },
    {
        "title": "Implementar notificaciones de renovación automática",
        "type": "enhancement",
        "state": "in_clarification",
        "description": "Enviar recordatorio 30 días antes del vencimiento de la póliza. Incluir enlace directo a la cotización de renovación.",
        "priority": "medium",
        "completeness_score": 60,
    },
    {
        "title": "Rediseñar flujo de onboarding para nuevos asegurados",
        "type": "initiative",
        "state": "in_review",
        "description": "El flujo actual tiene 12 pasos y un 40% de abandono. Objetivo: reducir a 5 pasos manteniendo compliance con DGSFP.",
        "priority": "critical",
        "completeness_score": 85,
    },
    {
        "title": "Spike: evaluar Stripe como pasarela de pago alternativa",
        "type": "spike",
        "state": "draft",
        "description": "Evaluar si Stripe cumple los requisitos regulatorios de DGSFP para cobro de primas. Hipótesis: Stripe + SCA reduce la tasa de fallo de pago en un 20%.",
        "priority": "low",
        "completeness_score": 15,
    },
    {
        "title": "Migración de datos de pólizas legacy al nuevo modelo",
        "type": "task",
        "state": "draft",
        "description": "Migrar 50K pólizas del sistema legacy (Oracle) al nuevo Postgres. Incluir validación de integridad post-migración.",
        "priority": "high",
        "completeness_score": 0,
    },
    {
        "title": "Portal de autogestión para tomadores",
        "type": "requirement",
        "state": "in_clarification",
        "description": "Los tomadores necesitan poder consultar sus pólizas, descargar recibos y actualizar datos personales sin llamar al call center.",
        "priority": "medium",
        "completeness_score": 45,
    },
    {
        "title": "Automatizar cálculo de prima para seguros de hogar",
        "type": "business_change",
        "state": "ready",
        "description": "Actualmente el cálculo de prima de hogar es manual. Automatizar usando la tarifa vigente + factores de riesgo por zona geográfica.",
        "priority": "critical",
        "completeness_score": 95,
    },
    {
        "title": "Explorar integración con catastro para valoración automática",
        "type": "idea",
        "state": "draft",
        "description": "Usar datos del catastro para pre-rellenar el valor del inmueble en cotizaciones de hogar. Reduciría fricción y errores de declaración.",
        "priority": "low",
        "completeness_score": 10,
    },
]

SAMPLE_TAGS = [
    {"name": "compliance", "color": "#ef4444"},
    {"name": "ux", "color": "#3b82f6"},
    {"name": "backend", "color": "#10b981"},
    {"name": "urgente", "color": "#f59e0b"},
    {"name": "tech-debt", "color": "#6b7280"},
]

SECTIONS_FOR_BUG = [
    ("summary", "Resumen del bug", 1, True),
    ("steps_to_reproduce", "Pasos para reproducir", 2, True),
    ("expected_behavior", "Comportamiento esperado", 3, True),
    ("actual_behavior", "Comportamiento actual", 4, True),
    ("acceptance_criteria", "- El campo rechaza valores negativos\n- Se muestra mensaje de error en rojo\n- El botón de enviar se deshabilita", 7, True),
]


async def run() -> int:
    factory = get_session_factory()
    async with factory() as session:
        async with session.begin():
            # Get workspace
            ws = (
                await session.execute(
                    select(WorkspaceORM).where(WorkspaceORM.slug == WORKSPACE_SLUG)
                )
            ).scalar_one_or_none()
            if ws is None:
                print(f"[seed-data] workspace '{WORKSPACE_SLUG}' not found. Run seed_dev.py first.")
                return 1

            # Get first user
            user = (
                await session.execute(
                    select(UserORM).limit(1)
                )
            ).scalar_one_or_none()
            if user is None:
                print("[seed-data] no users in DB. Login once first.")
                return 1

            # Set workspace context for RLS (asyncpg doesn't support params in SET)
            ws_id_str = str(ws.id)
            await session.execute(
                text(f"SET LOCAL app.current_workspace = '{ws_id_str}'")
            )

            # Check if already seeded
            existing = (
                await session.execute(
                    select(WorkItemORM).where(WorkItemORM.title == SAMPLE_ITEMS[0]["title"])
                )
            ).scalar_one_or_none()
            if existing:
                print("[seed-data] sample data already exists. Skipping.")
                return 0

            now = datetime.now(UTC)
            project_id = uuid4()

            # Create tags
            tag_ids: dict[str, object] = {}
            for tag_data in SAMPLE_TAGS:
                tag = TagORM(
                    id=uuid4(),
                    workspace_id=ws.id,
                    name=tag_data["name"],
                    color=tag_data["color"],
                    created_at=now,
                    created_by=user.id,
                )
                session.add(tag)
                tag_ids[tag_data["name"]] = tag.id
            await session.flush()
            print(f"[seed-data] created {len(SAMPLE_TAGS)} tags")

            # Create team
            team = TeamORM(
                id=uuid4(),
                workspace_id=ws.id,
                name="Equipo de Producto",
                description="Equipo principal de desarrollo de producto",
                can_receive_reviews=True,
                created_at=now,
                updated_at=now,
                created_by=user.id,
            )
            session.add(team)
            await session.flush()

            # Add user to team
            session.add(
                TeamMembershipORM(
                    id=uuid4(),
                    team_id=team.id,
                    user_id=user.id,
                    role="lead",
                    joined_at=now,
                )
            )
            await session.flush()
            print(f"[seed-data] created team 'Equipo de Producto' with 1 member")

            # Create work items
            work_item_ids: list[object] = []
            for item_data in SAMPLE_ITEMS:
                wi = WorkItemORM(
                    id=uuid4(),
                    workspace_id=ws.id,
                    project_id=project_id,
                    title=item_data["title"],
                    type=item_data["type"],
                    state=item_data["state"],
                    owner_id=user.id,
                    creator_id=user.id,
                    description=item_data["description"],
                    priority=item_data["priority"],
                    completeness_score=item_data["completeness_score"],
                    materialized_path="",
                    attachment_count=0,
                    has_override=False,
                    owner_suspended_flag=False,
                    tags=[],
                    created_at=now,
                    updated_at=now,
                )
                session.add(wi)
                work_item_ids.append(wi.id)
            await session.flush()
            print(f"[seed-data] created {len(SAMPLE_ITEMS)} work items")

            # Add sections to first work item (bug)
            bug_id = work_item_ids[0]
            for sect_type, content, order, required in SECTIONS_FOR_BUG:
                session.add(
                    WorkItemSectionORM(
                        id=uuid4(),
                        work_item_id=bug_id,
                        section_type=sect_type,
                        content=content,
                        display_order=order,
                        is_required=required,
                        generation_source="manual",
                        version=1,
                        created_at=now,
                        updated_at=now,
                        created_by=user.id,
                        updated_by=user.id,
                    )
                )
            await session.flush()
            print(f"[seed-data] added {len(SECTIONS_FOR_BUG)} sections to bug work item")

            # Add task nodes to initiative
            initiative_id = work_item_ids[2]
            for i, task_title in enumerate([
                "Auditar flujo actual y mapear puntos de abandono",
                "Diseñar wireframes del nuevo flujo (5 pasos)",
                "Validar compliance DGSFP con legal",
                "Implementar prototipo clickeable",
                "Test A/B con 100 usuarios",
            ]):
                session.add(
                    TaskNodeORM(
                        id=uuid4(),
                        work_item_id=initiative_id,
                        title=task_title,
                        display_order=i + 1,
                        status="done" if i < 2 else ("in_progress" if i == 2 else "draft"),
                        generation_source="manual",
                        materialized_path="",
                        created_at=now,
                        updated_at=now,
                        created_by=user.id,
                        updated_by=user.id,
                    )
                )
            await session.flush()
            print("[seed-data] added 5 task nodes to initiative")

            # Tag some items
            tag_assignments = [
                (work_item_ids[0], "compliance"),
                (work_item_ids[0], "urgente"),
                (work_item_ids[1], "ux"),
                (work_item_ids[2], "ux"),
                (work_item_ids[2], "compliance"),
                (work_item_ids[4], "backend"),
                (work_item_ids[4], "tech-debt"),
                (work_item_ids[6], "backend"),
            ]
            for wi_id, tag_name in tag_assignments:
                session.add(
                    WorkItemTagORM(
                        id=uuid4(),
                        work_item_id=wi_id,
                        tag_id=tag_ids[tag_name],
                        created_at=now,
                        created_by=user.id,
                    )
                )
            await session.flush()
            print(f"[seed-data] tagged {len(tag_assignments)} work items")

    print("[seed-data] done. Refresh your browser.")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
