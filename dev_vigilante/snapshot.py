"""In-site snapshot entry point: runs the shared engine against the bench source.

The engine itself (:mod:`dev_vigilante.engine`) is read-only against ERP metadata.
Persisting the result (creating the ``Vigilante Snapshot`` record and attaching the
export) lives in :mod:`dev_vigilante.api`.
"""

from __future__ import annotations

import frappe

from dev_vigilante import engine
from dev_vigilante.dev_vigilante.doctype.vigilante_settings.vigilante_settings import (
    get_settings,
)
from dev_vigilante.sources.bench import BenchSource


class SnapshotEngine:
    def __init__(self, settings=None):
        self.settings = settings or get_settings()

    def run(self, previous_snapshot: dict | None = None) -> dict:
        return engine.run(
            BenchSource(),
            self.settings.get_scope(),
            previous_snapshot=previous_snapshot,
            llm_config=self.settings.get_llm_config(),
            generated_on=frappe.utils.now(),
            log_error=lambda tb, title: frappe.log_error(title=title, message=tb),
        )


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
