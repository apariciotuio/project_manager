"""EP-07 — DiffService (pure, no persistence).

Two-pass diff:
1. Structural (section-level): match by section_type, classify change
2. Content-level: unified_diff on modified sections

difflib only — no external libraries.
Performance target: < 2s for 100KB combined content.
"""
from __future__ import annotations

import difflib
from typing import Any


class SectionChangeType(str):
    ADDED = "added"
    REMOVED = "removed"
    MODIFIED = "modified"
    UNCHANGED = "unchanged"
    REORDERED = "reordered"


class DiffService:
    def validate_version_order(self, *, from_version: int, to_version: int) -> None:
        if from_version > to_version:
            raise ValueError(
                f"from_version ({from_version}) must be <= to_version ({to_version})"
            )

    def compute_version_diff(
        self, snapshot_a: dict[str, Any], snapshot_b: dict[str, Any]
    ) -> dict[str, Any]:
        """Compute structural + content diff between two v1 snapshots.

        Returns:
            {
                "metadata_diff": {"title": {before, after} | None, "state": ...},
                "sections": [
                    {
                        "section_type": str,
                        "change_type": SectionChangeType,
                        "hunks": [...]   # only for modified sections
                    }
                ]
            }
        """
        wi_a: dict[str, Any] = snapshot_a.get("work_item", {})
        wi_b: dict[str, Any] = snapshot_b.get("work_item", {})
        metadata_diff = self._compute_metadata_diff(wi_a, wi_b)

        sections_a: list[dict[str, Any]] = snapshot_a.get("sections", [])
        sections_b: list[dict[str, Any]] = snapshot_b.get("sections", [])
        section_results = self._compute_section_diff_structural(sections_a, sections_b)

        return {
            "metadata_diff": metadata_diff,
            "sections": section_results,
        }

    def compute_section_diff(self, text_a: str, text_b: str) -> list[dict[str, Any]]:
        """Line-level diff. Returns list of hunks.

        Each hunk: {"lines": [{"type": "context|added|removed", "text": str}]}
        """
        lines_a = text_a.splitlines(keepends=True)
        lines_b = text_b.splitlines(keepends=True)

        # Use SequenceMatcher directly for better hunk grouping
        matcher = difflib.SequenceMatcher(None, lines_a, lines_b, autojunk=False)
        hunks: list[dict[str, Any]] = []
        current_hunk_lines: list[dict[str, Any]] = []

        for tag, i1, i2, j1, j2 in matcher.get_opcodes():
            if tag == "equal":
                # context lines
                for line in lines_a[i1:i2]:
                    current_hunk_lines.append({"type": "context", "text": line.rstrip("\n")})
            elif tag == "insert":
                for line in lines_b[j1:j2]:
                    current_hunk_lines.append({"type": "added", "text": line.rstrip("\n")})
            elif tag == "delete":
                for line in lines_a[i1:i2]:
                    current_hunk_lines.append({"type": "removed", "text": line.rstrip("\n")})
            elif tag == "replace":
                for line in lines_a[i1:i2]:
                    current_hunk_lines.append({"type": "removed", "text": line.rstrip("\n")})
                for line in lines_b[j1:j2]:
                    current_hunk_lines.append({"type": "added", "text": line.rstrip("\n")})

        if current_hunk_lines:
            hunks.append({"lines": current_hunk_lines})

        return hunks

    # -----------------------------------------------------------------------
    # Private helpers
    # -----------------------------------------------------------------------

    def _compute_metadata_diff(
        self, wi_a: dict[str, Any], wi_b: dict[str, Any]
    ) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for field in ("title", "state", "owner_id", "description"):
            val_a = wi_a.get(field)
            val_b = wi_b.get(field)
            if val_a != val_b:
                result[field] = {"before": val_a, "after": val_b}
            else:
                result[field] = None
        return result

    def _compute_section_diff_structural(
        self,
        sections_a: list[dict[str, Any]],
        sections_b: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        # Index by section_type (primary match key per design)
        idx_a = {s["section_type"]: s for s in sections_a}
        idx_b = {s["section_type"]: s for s in sections_b}

        all_types = list(dict.fromkeys(
            list(idx_a.keys()) + list(idx_b.keys())
        ))

        results: list[dict[str, Any]] = []
        for stype in all_types:
            in_a = stype in idx_a
            in_b = stype in idx_b

            if in_a and not in_b:
                results.append({
                    "section_type": stype,
                    "change_type": SectionChangeType.REMOVED,
                    "hunks": [],
                })
            elif in_b and not in_a:
                content_b = idx_b[stype].get("content", "")
                hunks = self.compute_section_diff("", content_b)
                results.append({
                    "section_type": stype,
                    "change_type": SectionChangeType.ADDED,
                    "hunks": hunks,
                })
            else:
                # Both present
                sa = idx_a[stype]
                sb = idx_b[stype]
                content_a = sa.get("content", "")
                content_b = sb.get("content", "")
                order_a = sa.get("order", 0)
                order_b = sb.get("order", 0)

                if content_a == content_b and order_a != order_b:
                    results.append({
                        "section_type": stype,
                        "change_type": SectionChangeType.REORDERED,
                        "hunks": [],
                    })
                elif content_a == content_b:
                    results.append({
                        "section_type": stype,
                        "change_type": SectionChangeType.UNCHANGED,
                        "hunks": [],
                    })
                else:
                    hunks = self.compute_section_diff(content_a, content_b)
                    results.append({
                        "section_type": stype,
                        "change_type": SectionChangeType.MODIFIED,
                        "hunks": hunks,
                    })

        return results
