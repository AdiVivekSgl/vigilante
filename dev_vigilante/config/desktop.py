from frappe import _


def get_data():
    return [
        {
            "module_name": "Dev Vigilante",
            "category": "Modules",
            "label": _("Dev Vigilante"),
            "color": "#1f6feb",
            "icon": "octicon octicon-telescope",
            "type": "module",
            "description": _(
                "Developer Intelligence & Context Snapshot — inventory and export ERP customizations."
            ),
        }
    ]
