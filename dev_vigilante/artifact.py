"""The Artifact — the single normalized unit every collector produces.

Kept dependency-free (no ``frappe`` import) so it can be constructed and unit
tested outside a bench.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field
from typing import Any


@dataclass
class Artifact:
    """A normalized description of one customization.

    Attributes:
        collector: Key of the collector that produced this (e.g. ``"custom_fields"``).
        type: Human-readable artifact type (e.g. ``"Custom Field"``).
        name: Display name, unique within the collector where possible.
        key: Stable unique key used for change detection and file naming. Must be
            deterministic for a given ERP state and must not embed volatile values
            (timestamps, modified-by, etc.).
        fields: Structured, documented attributes of the artifact.
        summary: Generated (heuristic or LLM) prose summary.
        raw: Bulky source blobs (script text, SQL, Jinja). May be omitted when the
            settings disable raw source.
        dependencies: List of ``{"type": ..., "name": ...}`` references this artifact
            points at (used to build the dependency graph).
        tags: Extra keywords for the search index.
        group: Optional grouping value (e.g. the DocType a field belongs to) used to
            lay out Markdown pages.
    """

    collector: str
    type: str
    name: str
    key: str
    fields: dict[str, Any] = field(default_factory=dict)
    summary: str = ""
    raw: dict[str, Any] = field(default_factory=dict)
    dependencies: list[dict[str, str]] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)
    group: str | None = None

    def content_for_hash(self) -> dict[str, Any]:
        """The substantive content used to detect modifications.

        Excludes the generated ``summary`` (derived, not a real customization) so a
        change in summarizer wording never registers as a modified artifact.
        """
        return {
            "type": self.type,
            "name": self.name,
            "fields": self.fields,
            "raw": self.raw,
            "dependencies": self.dependencies,
        }

    def content_hash(self) -> str:
        blob = json.dumps(self.content_for_hash(), sort_keys=True, default=str)
        return hashlib.sha256(blob.encode("utf-8")).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        data = {
            "collector": self.collector,
            "type": self.type,
            "name": self.name,
            "key": self.key,
            "fields": self.fields,
            "summary": self.summary,
            "raw": self.raw,
            "dependencies": self.dependencies,
            "tags": self.tags,
            "group": self.group,
        }
        data["content_hash"] = self.content_hash()
        return data
