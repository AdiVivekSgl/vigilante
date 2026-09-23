import frappe
from frappe.model.document import Document


class VigilanteSnapshot(Document):
    def get_snapshot_data(self):
        """Parsed snapshot payload as a dict (empty dict when absent)."""
        if not self.snapshot_json:
            return {}
        try:
            return frappe.parse_json(self.snapshot_json)
        except Exception:
            return {}

    def get_changes_data(self):
        if not self.changes_json:
            return {}
        try:
            return frappe.parse_json(self.changes_json)
        except Exception:
            return {}

    def on_trash(self):
        # Clean up the attached export file so we don't leave orphaned files behind.
        if self.export_file:
            try:
                file_name = frappe.db.get_value(
                    "File", {"file_url": self.export_file}, "name"
                )
                if file_name:
                    frappe.delete_doc("File", file_name, ignore_permissions=True, force=True)
            except Exception:
                # Deleting the snapshot must not fail because of a missing file.
                frappe.log_error(frappe.get_traceback(), "Vigilante Snapshot file cleanup")
