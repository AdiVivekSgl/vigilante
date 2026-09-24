"""Custom DocTypes collector."""

from __future__ import annotations

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector
from dev_vigilante.sources.base import SourceError

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
        rows = self.source.get_all("DocType", ["name", "module", "custom"], order_by="name asc")
        in_scope = [
            row
            for row in rows
            if self.context.is_doctype_in_scope(row.get("module"), bool(row.get("custom")))
        ]
        if not in_scope:
            return []

        workflows_by_doctype = self._workflows_by_doctype()
        artifacts: list[Artifact] = []
        for row in in_scope:
            try:
                doc = self.source.get_doc("DocType", row.get("name"))
            except SourceError:
                continue
            workflows = workflows_by_doctype.get(row.get("name"), [])
            artifacts.append(self._build(doc, row.get("module"), workflows))
        return artifacts

    def _workflows_by_doctype(self) -> dict[str, list[str]]:
        """One request for all workflows instead of one per DocType."""
        try:
            rows = self.source.get_all(
                "Workflow", ["name", "document_type"], order_by="name asc"
            )
        except SourceError:
            return {}
        out: dict[str, list[str]] = {}
        for row in rows:
            out.setdefault(row.get("document_type"), []).append(row.get("name"))
        return {dt: sorted(names) for dt, names in out.items()}

    def _build(self, doc: dict, module, workflows: list[str]) -> Artifact:
        doc_fields = doc.get("fields") or []
        fields = [self._field_dict(f) for f in doc_fields]
        child_tables = [
            {"fieldname": f.get("fieldname"), "child_doctype": f.get("options")}
            for f in doc_fields
            if f.get("fieldtype") in _CHILD_TABLE_TYPES and f.get("options")
        ]
        link_fields = [
            {"fieldname": f.get("fieldname"), "fieldtype": f.get("fieldtype"), "target": f.get("options")}
            for f in doc_fields
            if f.get("fieldtype") in _LINK_TYPES and f.get("options")
        ]
        permissions = [self._perm_dict(p) for p in doc.get("permissions") or []]
        connections = [
            {
                "link_doctype": link.get("link_doctype"),
                "link_fieldname": link.get("link_fieldname"),
                "group": link.get("group"),
            }
            for link in (doc.get("links") or [])
        ]

        info = {
            "module": module,
            "custom": bool(doc.get("custom")),
            "is_child_table": bool(doc.get("istable")),
            "is_single": bool(doc.get("issingle")),
            "is_submittable": bool(doc.get("is_submittable")),
            "is_tree": bool(doc.get("is_tree")),
            "track_changes": bool(doc.get("track_changes")),
            "quick_entry": bool(doc.get("quick_entry")),
            "naming": {
                "autoname": doc.get("autoname"),
                "naming_rule": doc.get("naming_rule"),
                "title_field": doc.get("title_field"),
            },
            "field_count": len(fields),
            "fields": fields,
            "permissions": permissions,
            "child_tables": child_tables,
            "links": link_fields,
            "connections": connections,
            "workflows": workflows,
            "has_web_view": bool(doc.get("has_web_view")),
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
            name=doc.get("name"),
            key=f"doctype::{doc.get('name')}",
            fields=info,
            dependencies=seen,
            group=module,
            tags=[doc.get("name"), module]
            + [f["fieldname"] for f in fields if f.get("fieldname")]
            + [p["role"] for p in permissions if p.get("role")],
        )

    def _field_dict(self, f: dict) -> dict:
        return {attr: f.get(attr) for attr in _FIELD_ATTRS}

    def _perm_dict(self, p: dict) -> dict:
        out = {}
        for attr in _PERM_ATTRS:
            value = p.get(attr)
            if attr in ("role", "permlevel"):
                out[attr] = value
            else:
                out[attr] = bool(value)
        return out
