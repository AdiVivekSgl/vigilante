"""Client Scripts collector."""

from __future__ import annotations

import frappe

from dev_vigilante import analysis
from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import BaseCollector


class ClientScriptsCollector(BaseCollector):
    key = "client_scripts"
    label = "Client Scripts"
    order = 20

    def collect(self) -> list[Artifact]:
        rows = frappe.get_all(
            "Client Script",
            fields=["name", "dt", "view", "enabled", "script", "module"],
            order_by="dt asc, name asc",
        )
        artifacts: list[Artifact] = []
        for row in rows:
            if not self.in_scope(row.get("module")):
                continue

            script = row.get("script") or ""
            dt = row.get("dt")

            events = analysis.extract_form_events(script)
            functions = analysis.extract_js_functions(script)
            ref_fields = analysis.extract_referenced_fields(script)
            ref_reports = analysis.extract_referenced_reports(script)

            fields = {
                "applies_to": dt,
                "view": row.get("view"),
                "enabled": bool(row.get("enabled")),
                "module": row.get("module"),
                "events_used": events,
                "functions_detected": functions,
                "referenced_fields": ref_fields,
                "referenced_reports": ref_reports,
                "lines_of_code": analysis.count_lines(script),
            }

            dependencies = []
            if dt:
                dependencies.append({"type": "DocType", "name": dt})
            for fieldname in ref_fields:
                dependencies.append({"type": "Field", "name": f"{dt}.{fieldname}"})
            for report in ref_reports:
                dependencies.append({"type": "Report", "name": report})

            raw = {"script": script} if self.context.include_raw_source else {}

            artifacts.append(
                Artifact(
                    collector=self.key,
                    type="Client Script",
                    name=row.get("name"),
                    key=f"client-script::{row.get('name')}",
                    fields=fields,
                    raw=raw,
                    dependencies=dependencies,
                    group=dt,
                    tags=[t for t in [dt, row.get("view")] if t] + events + functions,
                )
            )
        return artifacts
