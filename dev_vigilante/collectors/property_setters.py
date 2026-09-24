"""Property Setters collector.

Property Setters hold every change made through Customize Form to a *standard* field or
DocType (labels, hidden/mandatory flags, options, default print format, naming series,
...), so they are often the largest share of a site's GUI customizations.
"""

from __future__ import annotations

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector

_FIELDS = [
    "name",
    "doc_type",
    "doctype_or_field",
    "field_name",
    "row_name",
    "property",
    "property_type",
    "value",
    "module",
    "is_system_generated",
]


class PropertySettersCollector(BaseCollector):
    key = "property_setters"
    label = "Property Setters"
    order = 15

    def collect(self) -> list[Artifact]:
        rows = self.source.get_all(
            "Property Setter",
            _FIELDS,
            order_by="doc_type asc, field_name asc, property asc, name asc",
        )
        artifacts: list[Artifact] = []
        for row in rows:
            module = row.get("module")
            if not self.in_scope(module):
                continue

            dt = row.get("doc_type")
            applies_to = row.get("doctype_or_field") or "DocField"
            # DocType-level setters have no field; child-row setters (e.g. DocType Link)
            # are addressed by row_name.
            target = row.get("field_name") or row.get("row_name") or None
            prop = row.get("property")

            fields = {
                "doctype": dt,
                "applies_to": applies_to,
                "target": target,
                "property": prop,
                "property_type": row.get("property_type"),
                "value": row.get("value"),
                "module": module,
                "system_generated": bool(row.get("is_system_generated")),
            }

            dependencies = [{"type": "DocType", "name": dt}] if dt else []
            if dt and row.get("field_name"):
                dependencies.append({"type": "Field", "name": f"{dt}.{row.get('field_name')}"})

            target_label = target or "(DocType)"
            artifacts.append(
                Artifact(
                    collector=self.key,
                    type="Property Setter",
                    name=f"{dt} / {target_label} / {prop}",
                    # The record name is Frappe's own "<dt>-<field>-<property>" key and
                    # is unique; keep it so renamed labels do not look like new records.
                    key=f"property-setter::{row.get('name')}",
                    fields=fields,
                    dependencies=dependencies,
                    group=dt,
                    tags=[t for t in [dt, target, prop] if t],
                )
            )
        return artifacts
