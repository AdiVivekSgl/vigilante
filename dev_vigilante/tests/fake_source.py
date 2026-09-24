"""In-memory :class:`Source` used to test collectors, the engine and the CLI."""

from __future__ import annotations

import copy

from dev_vigilante.sources.base import AccessDenied, NotAvailable, Source


class FakeSource(Source):
    kind = "fake"

    def __init__(self, tables=None, docs=None, denied=(), system=None):
        self.tables = copy.deepcopy(tables or {})
        self.docs = copy.deepcopy(docs or {})
        self.denied = set(denied)
        self.system = system or {"installed_apps": ["frappe", "erpnext", "acme"]}

    def site_name(self):
        return "erp.example.com"

    def get_all(self, doctype, fields, filters=None, order_by=None):
        if doctype in self.denied:
            raise AccessDenied(doctype)
        if doctype not in self.tables:
            raise NotAvailable(doctype)
        rows = self.tables[doctype]
        for key, value in (filters or {}).items():
            rows = [r for r in rows if r.get(key) == value]
        return [{f: r.get(f) for f in fields} for r in rows]

    def get_doc(self, doctype, name):
        if doctype in self.denied:
            raise AccessDenied(doctype)
        try:
            return copy.deepcopy(self.docs[(doctype, name)])
        except KeyError:
            raise NotAvailable(f"{doctype} {name}") from None

    def system_info(self):
        return dict(self.system)

    def logged_user(self):
        return "auditor@example.com"


def sample_site() -> FakeSource:
    """A small site: one custom app, GUI customizations on Sales Order."""
    tables = {
        "Module Def": [
            {"name": "Selling", "app_name": "erpnext"},
            {"name": "Core", "app_name": "frappe"},
            {"name": "Acme Logistics", "app_name": "acme"},
        ],
        "Custom Field": [
            {
                "name": "Sales Order-dispatch_priority",
                "dt": "Sales Order",
                "fieldname": "dispatch_priority",
                "label": "Dispatch Priority",
                "fieldtype": "Select",
                "options": "Low\nHigh",
                "insert_after": "delivery_date",
                "module": None,
            }
        ],
        "Property Setter": [
            {
                "name": "Sales Order-po_no-reqd",
                "doc_type": "Sales Order",
                "doctype_or_field": "DocField",
                "field_name": "po_no",
                "property": "reqd",
                "property_type": "Check",
                "value": "1",
                "module": None,
            },
            {
                "name": "Sales Order-main-default_print_format",
                "doc_type": "Sales Order",
                "doctype_or_field": "DocType",
                "field_name": None,
                "property": "default_print_format",
                "property_type": "Data",
                "value": "Acme SO",
                "module": None,
            },
        ],
        "Client Script": [
            {
                "name": "SO Dispatch",
                "dt": "Sales Order",
                "view": "Form",
                "enabled": 1,
                "script": "frappe.ui.form.on('Sales Order', {\n  refresh(frm) {\n    frm.set_value('dispatch_priority', 'High');\n  }\n});",
                "module": None,
            }
        ],
        "Server Script": [],
        "DocType": [
            {"name": "Sales Order", "module": "Selling", "custom": 0},
            {"name": "User", "module": "Core", "custom": 0},
            {"name": "Delivery Slot", "module": "Selling", "custom": 1},
            {"name": "Truck", "module": "Acme Logistics", "custom": 0},
        ],
        "Workflow": [{"name": "Truck Approval", "document_type": "Truck"}],
    }
    docs = {
        ("DocType", "Delivery Slot"): {
            "name": "Delivery Slot",
            "custom": 1,
            "autoname": "hash",
            "fields": [
                {"fieldname": "slot", "label": "Slot", "fieldtype": "Data", "reqd": 1},
                {"fieldname": "truck", "label": "Truck", "fieldtype": "Link", "options": "Truck"},
            ],
            "permissions": [{"role": "Stock User", "permlevel": 0, "read": 1, "write": 1}],
        },
        ("DocType", "Truck"): {
            "name": "Truck",
            "custom": 0,
            "fields": [{"fieldname": "plate", "label": "Plate", "fieldtype": "Data"}],
            "permissions": [],
        },
    }
    return FakeSource(tables, docs)
