"""Server Scripts collector."""

from __future__ import annotations

from dev_vigilante import analysis
from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector

_FIELDS = [
    "name",
    "script_type",
    "reference_doctype",
    "doctype_event",
    "event_frequency",
    "cron_format",
    "api_method",
    "allow_guest",
    "disabled",
    "script",
    "module",
]


class ServerScriptsCollector(BaseCollector):
    key = "server_scripts"
    label = "Server Scripts"
    order = 30

    def collect(self) -> list[Artifact]:
        rows = self.source.get_all(
            "Server Script", _FIELDS, order_by="script_type asc, name asc"
        )
        artifacts: list[Artifact] = []
        for row in rows:
            if not self.in_scope(row.get("module")):
                continue

            script = row.get("script") or ""
            script_type = row.get("script_type")
            reference_doctype = row.get("reference_doctype")

            event = None
            if script_type == "DocType Event":
                event = row.get("doctype_event")
            elif script_type == "Scheduler Event":
                event = row.get("event_frequency") or row.get("cron_format")

            fields = {
                "trigger": script_type,
                "event": event,
                "reference_doctype": reference_doctype,
                "api_method": row.get("api_method"),
                "allow_guest": bool(row.get("allow_guest")),
                "is_scheduled": script_type == "Scheduler Event",
                "is_api": script_type == "API",
                "is_permission_query": script_type == "Permission Query",
                "disabled": bool(row.get("disabled")),
                "module": row.get("module"),
                "functions_detected": analysis.extract_py_functions(script),
                "frappe_apis_used": analysis.extract_py_frappe_apis(script),
                "referenced_doctypes": analysis.extract_py_referenced_doctypes(script),
                "lines_of_code": analysis.count_lines(script),
            }

            dependencies = []
            if reference_doctype:
                dependencies.append({"type": "DocType", "name": reference_doctype})
            for dt in fields["referenced_doctypes"]:
                dependencies.append({"type": "DocType", "name": dt})

            raw = {"script": script} if self.context.include_raw_source else {}

            artifacts.append(
                Artifact(
                    collector=self.key,
                    type="Server Script",
                    name=row.get("name"),
                    key=f"server-script::{row.get('name')}",
                    fields=fields,
                    raw=raw,
                    dependencies=dependencies,
                    group=script_type,
                    tags=[t for t in [script_type, reference_doctype, event] if t],
                )
            )
        return artifacts
