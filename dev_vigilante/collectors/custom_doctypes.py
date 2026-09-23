"""Custom DocTypes collector."""

from __future__ import annotations

import frappe

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector

_CHILD_TABLE_TYPES = {"Table", "Table MultiSelect"}
_LINK_TYPES = {"Link", "Dynamic Link"}

_FIELD_ATTRS = [
    "fieldname",
    "label",
    "fieldtype",
    "options",
    "reqd",
    "unique",
    "in_list_view",
    "read_only",
    "hidden",
    "depends_on",
    "default",
    "description",
]

_PERM_ATTRS = [
    "role",
    "permlevel",
    "read",
    "write",
    "create",
    "delete",
    "submit",
    "cancel",
    "amend",
    "report",
    "export",
    "import",
    "share",
    "print",
    "email",
]


class CustomDocTypesCollector(BaseCollector):
    key = "custom_doctypes"
    label = "Custom DocTypes"
    order = 40

    def collect(self) -> list[Artifact]:
        rows = frappe.get_all(
            "DocType",
            fields=["name", "module", "custom"],
            order_by="name asc",
        )
        artifacts: list[Artifact] = []
        for row in rows:
            module = row.get("module")
            if not self.context.is_doctype_in_scope(module, bool(row.get("custom"))):
                continue

            try:
                doc = frappe.get_doc("DocType", row.get("name"))
            except Exception:
                continue

            artifacts.append(self._build(doc, module))
        return artifacts

    def _build(self, doc, module) -> Artifact:
        fields = [self._field_dict(f) for f in doc.fields]
        child_tables = [
            {"fieldname": f.fieldname, "child_doctype": f.options}
            for f in doc.fields
            if f.fieldtype in _CHILD_TABLE_TYPES and f.options
        ]
        link_fields = [
            {"fieldname": f.fieldname, "fieldtype": f.fieldtype, "target": f.options}
            for f in doc.fields
            if f.fieldtype in _LINK_TYPES and f.options
        ]
        permissions = [self._perm_dict(p) for p in doc.permissions]
        connections = [
            {
                "link_doctype": link.link_doctype,
                "link_fieldname": link.link_fieldname,
                "group": getattr(link, "group", None),
            }
            for link in (doc.get("links") or [])
        ]
        workflows = frappe.get_all(
            "Workflow",
            filters={"document_type": doc.name},
            pluck="name",
            order_by="name asc",
        )

        info = {
            "module": module,
            "custom": bool(doc.custom),
            "is_child_table": bool(doc.istable),
            "is_single": bool(doc.issingle),
            "is_submittable": bool(doc.is_submittable),
            "is_tree": bool(getattr(doc, "is_tree", 0)),
            "track_changes": bool(doc.track_changes),
            "quick_entry": bool(getattr(doc, "quick_entry", 0)),
            "naming": {
                "autoname": doc.autoname,
                "naming_rule": getattr(doc, "naming_rule", None),
                "title_field": doc.title_field,
            },
            "field_count": len(fields),
            "fields": fields,
            "permissions": permissions,
            "child_tables": child_tables,
            "links": link_fields,
            "connections": connections,
            "workflows": workflows,
            "has_web_view": bool(getattr(doc, "has_web_view", 0)),
        }

        dependencies = []
        for link in link_fields:
            dependencies.append({"type": "DocType", "name": link["target"]})
        for child in child_tables:
            dependencies.append({"type": "DocType", "name": child["child_doctype"]})
        for wf in workflows:
            dependencies.append({"type": "Workflow", "name": wf})

        # de-dup dependencies deterministically
        seen = []
        for dep in dependencies:
            if dep not in seen:
                seen.append(dep)

        return Artifact(
            collector=self.key,
            type="Custom DocType",
            name=doc.name,
            key=f"doctype::{doc.name}",
            fields=info,
            dependencies=seen,
            group=module,
            tags=[doc.name, module]
            + [f["fieldname"] for f in fields]
            + [p["role"] for p in permissions if p.get("role")],
        )

    def _field_dict(self, f) -> dict:
        return {attr: getattr(f, attr, None) for attr in _FIELD_ATTRS}

    def _perm_dict(self, p) -> dict:
        out = {}
        for attr in _PERM_ATTRS:
            value = getattr(p, attr, None)
            if attr in ("role", "permlevel"):
                out[attr] = value
            else:
                out[attr] = bool(value)
        return out
