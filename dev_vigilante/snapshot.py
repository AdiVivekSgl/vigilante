"""Snapshot engine — orchestrates collectors, summaries, graph, diff and assembly.

The engine is read-only against ERP metadata. Persisting the result (creating the
``Vigilante Snapshot`` record and attaching the export) lives in :mod:`dev_vigilante.api`.
"""

from __future__ import annotations

import time

import frappe

import dev_vigilante
from dev_vigilante import change_detection, dependency, search_index
from dev_vigilante.collectors.base import CollectorContext
from dev_vigilante.collectors.registry import build_collectors
from dev_vigilante.dev_vigilante.doctype.vigilante_settings.vigilante_settings import (
    get_settings,
)
from dev_vigilante.summarizers.base import get_summarizer


class SnapshotEngine:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def _build_context(self) -> CollectorContext:
        scope = self.settings.get_scope()
        modules = frappe.get_all("Module Def", fields=["name", "app_name"])
        app_by_module = {m.name: m.app_name for m in modules}
        return CollectorContext(scope, app_by_module)

    def run(self, previous_snapshot: dict | None = None) -> dict:
        start = time.monotonic()
        context = self._build_context()
        summarizer = get_summarizer(self.settings.get_llm_config())
        collectors = build_collectors(context)

        artifacts: dict[str, dict] = {}
        collector_meta: list[dict] = []
        errors: list[dict] = []

        for collector in collectors:
            try:
                items = collector.collect()
            except Exception:
                tb = frappe.get_traceback()
                errors.append({"collector": collector.key, "error": tb})
                frappe.log_error(tb, f"Dev Vigilante collector: {collector.key}")
                continue

            for artifact in items:
                artifact.summary = summarizer.summarize(artifact)
                artifacts[artifact.key] = artifact.to_dict()

            collector_meta.append(
                {"key": collector.key, "label": collector.label, "count": len(items)}
            )

        counts = {m["key"]: m["count"] for m in collector_meta}
        counts["total"] = len(artifacts)

        graph = dependency.build_dependency_graph(artifacts)
        search = search_index.build_search_index(artifacts)
        changes = change_detection.diff(previous_snapshot, {"artifacts": artifacts})

        snapshot = {
            "meta": {
                "generator": "Dev Vigilante",
                "app_version": dev_vigilante.__version__,
                "generated_on": frappe.utils.now(),
                "site": getattr(frappe.local, "site", None),
                "counts": counts,
            },
            "collectors": collector_meta,
            "artifacts": artifacts,
            "dependency_graph": graph,
            "search_index": search,
            "changes": changes,
        }

        return {
            "snapshot": snapshot,
            "counts": counts,
            "changes": changes,
            "errors": errors,
            "duration": round(time.monotonic() - start, 3),
        }


def get_previous_snapshot_data(exclude_name: str | None = None) -> dict | None:
    """Return the parsed snapshot payload of the most recent completed snapshot."""
    filters = {"status": "Completed"}
    if exclude_name:
        filters["name"] = ["!=", exclude_name]
    rows = frappe.get_all(
        "Vigilante Snapshot",
        filters=filters,
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    if not rows:
        return None
    doc = frappe.get_doc("Vigilante Snapshot", rows[0].name)
    return doc.get_snapshot_data() or None
