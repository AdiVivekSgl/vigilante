"""Small artifact factories shared across the pure-function tests."""

from __future__ import annotations

from dev_vigilante.artifact import Artifact


def custom_field(dt="Sales Order", fieldname="dispatch_priority", **overrides):
    fields = {
        "doctype": dt,
        "fieldname": fieldname,
        "label": "Dispatch Priority",
        "field_type": "Select",
        "options": "Low\nHigh",
        "depends_on": None,
        "mandatory": False,
        "read_only": False,
        "hidden": False,
        "insert_after": "delivery_date",
        "fetch_from": None,
        "default": None,
        "description": None,
    }
    fields.update(overrides)
    return Artifact(
        collector="custom_fields",
        type="Custom Field",
        name=f"{dt} / {fieldname}",
        key=f"custom-field::{dt}::{fieldname}",
        fields=fields,
        dependencies=[{"type": "DocType", "name": dt}],
        group=dt,
        tags=[dt, fieldname, fields.get("label")],
    )


def client_script(name="SO Dispatch", dt="Sales Order", **overrides):
    fields = {
        "applies_to": dt,
        "view": "Form",
        "enabled": True,
        "events_used": ["delivery_date", "refresh"],
        "functions_detected": ["set_priority"],
        "referenced_fields": ["dispatch_priority", "delivery_date"],
        "referenced_reports": [],
        "lines_of_code": 12,
    }
    fields.update(overrides)
    return Artifact(
        collector="client_scripts",
        type="Client Script",
        name=name,
        key=f"client-script::{name}",
        fields=fields,
        raw={"script": "frappe.ui.form.on('Sales Order', {});"},
        dependencies=[{"type": "DocType", "name": dt}],
        group=dt,
        tags=[dt],
    )
