"""Custom Fields collector."""

from __future__ import annotations

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector

_FIELDS = [
    "name",
    "dt",
    "fieldname",
    "label",
    "fieldtype",
    "options",
    "depends_on",
    "mandatory_depends_on",
    "read_only_depends_on",
    "reqd",
    "read_only",
    "hidden",
    "insert_after",
    "fetch_from",
    "default",
    "description",
    "module",
    "in_list_view",
    "bold",
    "translatable",
    "precision",
    "permlevel",
    "is_system_generated",
]


class CustomFieldsCollector(BaseCollector):
    key = "custom_fields"
    label = "Custom Fields"
    order = 10

    def collect(self) -> list[Artifact]:
        rows = self.source.get_all(
            "Custom Field", _FIELDS, order_by="dt asc, idx asc, fieldname asc"
        )
        artifacts: list[Artifact] = []
        for row in rows:
            module = row.get("module")
            if not self.in_scope(module):
                continue

            dt = row.get("dt")
            fieldname = row.get("fieldname")

            fields = {
                "doctype": dt,
                "fieldname": fieldname,
                "label": row.get("label"),
                "field_type": row.get("fieldtype"),
                "options": row.get("options"),
                "depends_on": row.get("depends_on"),
                "mandatory_depends_on": row.get("mandatory_depends_on"),
                "read_only_depends_on": row.get("read_only_depends_on"),
                "mandatory": bool(row.get("reqd")),
                "read_only": bool(row.get("read_only")),
                "hidden": bool(row.get("hidden")),
                "insert_after": row.get("insert_after"),
                "fetch_from": row.get("fetch_from"),
                "default": row.get("default"),
                "description": row.get("description"),
                "in_list_view": bool(row.get("in_list_view")),
                "permlevel": row.get("permlevel"),
                "module": module,
                "system_generated": bool(row.get("is_system_generated")),
            }

            dependencies = [{"type": "DocType", "name": dt}] if dt else []
            fetch_from = row.get("fetch_from") or ""
            if "." in fetch_from:
                source_field = fetch_from.split(".", 1)[0]
                dependencies.append(
                    {"type": "Field", "name": f"{dt}.{source_field}"}
                )

            artifacts.append(
                Artifact(
                    collector=self.key,
                    type="Custom Field",
                    name=f"{dt} / {fieldname}",
                    key=f"custom-field::{dt}::{fieldname}",
                    fields=fields,
                    dependencies=dependencies,
                    group=dt,
                    tags=[
                        t
                        for t in [dt, fieldname, row.get("label"), row.get("fieldtype")]
                        if t
                    ],
                )
            )
        return artifacts
