"""Versioned 170-Protocol Registry loader and contextual activation engine.

Preserves canonical protocol IDs (1..170), layer ranges (A..P), and dispositions.
Activates only relevant protocols contextually rather than presenting 170 questions.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from prodstud.domain.enums import MediaType, ProtocolDisposition, TaskMode
from prodstud.domain.models import ProtocolActivationRecord, ProtocolEntry


class ProtocolRegistry:
    """Loads, validates, and contextually queries the 170-Protocol Registry."""

    def __init__(self, protocols_path: Path):
        self.protocols_path = protocols_path
        raw = json.loads(protocols_path.read_text(encoding="utf-8"))
        self.version: str = raw["registry_version"]
        self.source_integrity_note: str = raw["source_integrity_note"]
        self.entries: list[ProtocolEntry] = [ProtocolEntry.model_validate(item) for item in raw["protocols"]]
        if len(self.entries) != 170:
            raise ValueError(f"Protocol registry must contain exactly 170 entries, found {len(self.entries)}")
        self._by_id: dict[int, ProtocolEntry] = {p.protocol_id: p for p in self.entries}
        self._by_code: dict[str, ProtocolEntry] = {p.protocol_code: p for p in self.entries}

    def get(self, protocol_id: int) -> ProtocolEntry:
        return self._by_id[protocol_id]

    def summary(self) -> dict[str, Any]:
        counts: dict[str, int] = {d.value: 0 for d in ProtocolDisposition}
        layers: dict[str, int] = {}
        for p in self.entries:
            counts[p.disposition.value] += 1
            layers[p.source_layer] = layers.get(p.source_layer, 0) + 1
        return {
            "registry_version": self.version,
            "total_protocols": len(self.entries),
            "dispositions": counts,
            "layers": layers,
            "source_integrity_note": self.source_integrity_note,
        }

    def activate_contextually(
        self,
        *,
        media_type: MediaType,
        task_mode: TaskMode,
        has_references: bool,
        multi_reference: bool,
        is_revision: bool,
        has_human_subject: bool,
        is_product: bool,
        is_interior_or_night: bool,
        is_multi_shot: bool,
        has_feasibility_warning: bool,
        high_resolution: bool,
        prompt_lower: str,
    ) -> list[ProtocolActivationRecord]:
        """Select a focused, explainable set of relevant protocols (typically 12-26) rather than all 170."""
        active_tags: set[str] = set()
        if media_type == MediaType.VIDEO:
            active_tags.update({"video", "async_job"})
        if is_multi_shot:
            active_tags.add("multi_shot")
        if has_references:
            active_tags.add("has_references")
        if multi_reference:
            active_tags.add("multi_reference")
        if is_revision:
            active_tags.update({"revision", "variation"})
        if has_human_subject or task_mode in {TaskMode.PORTRAIT, TaskMode.FASHION_EDITORIAL}:
            active_tags.update({"human_subject", "portrait"})
        if task_mode == TaskMode.FASHION_EDITORIAL:
            active_tags.update({"fashion", "editorial"})
        if is_product or task_mode == TaskMode.PRODUCT_IMAGE:
            active_tags.update({"product", "commercial", "studio"})
        if task_mode in {TaskMode.STRICT_PRESERVATION_EDIT, TaskMode.SELECTIVE_EDIT}:
            active_tags.update({"preservation", "edit_mode"})
        if task_mode == TaskMode.CINEMATIC_STILL or "cinematic" in prompt_lower or "film" in prompt_lower:
            active_tags.update({"cinematic", "narrative"})
        if is_interior_or_night:
            active_tags.update({"interior", "night", "low_key"})
        if has_feasibility_warning:
            active_tags.add("feasibility_warning")
        if high_resolution:
            active_tags.add("high_res")
        if any(k in prompt_lower for k in ("logo", "text", "label", "poster", "packaging")):
            active_tags.add("text_overlay")
        if any(k in prompt_lower for k in ("architect", "building", "room", "street", "studio")):
            active_tags.add("architecture")

        # Always include concise high-impact foundational protocol IDs plus context-triggered ones.
        base_core_ids = {1, 2, 4, 9, 11, 17, 18, 20, 31, 32, 37, 38, 41, 51, 56, 59, 67, 70, 72, 74, 81, 82, 94, 95, 98, 101, 103, 108, 113, 121, 123, 130, 157}
        selected: list[ProtocolActivationRecord] = []

        for entry in self.entries:
            if entry.disposition == ProtocolDisposition.DEFERRED:
                continue

            matched_triggers = [t for t in entry.activation_conditions if t in active_tags]
            is_base = entry.protocol_id in base_core_ids

            # Exclude video-only protocols for pure still images
            if media_type == MediaType.IMAGE and entry.protocol_id in {33, 65, 104, 105, 106, 107, 126, 131, 139, 144, 147}:
                continue

            if is_base or matched_triggers:
                reason = (
                    f"Triggered by brief context ({', '.join(matched_triggers)})"
                    if matched_triggers
                    else "Foundational production planning rule"
                )
                selected.append(
                    ProtocolActivationRecord(
                        protocol_id=entry.protocol_id,
                        protocol_code=entry.protocol_code,
                        canonical_title=entry.canonical_title,
                        source_layer=entry.source_layer,
                        disposition=entry.disposition,
                        reason=reason,
                        affected_fields=entry.decision_fields,
                    )
                )

        # Keep concise & high signal: sort by protocol_id and cap around 28 most consequential entries
        selected.sort(key=lambda r: (0 if r.protocol_id in base_core_ids else 1, r.protocol_id))
        trimmed = sorted(selected[:28], key=lambda r: r.protocol_id)
        return trimmed
