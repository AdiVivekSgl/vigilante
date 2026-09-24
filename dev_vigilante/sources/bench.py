"""In-site source: reads metadata through the ``frappe`` API of the running site."""

from __future__ import annotations

import platform
import subprocess

import frappe

from dev_vigilante.redaction import redact
from dev_vigilante.sources.base import AccessDenied, NotAvailable, Source

_SAFE_SYSTEM_SETTINGS = [
    "country",
    "time_zone",
    "language",
    "date_format",
    "time_format",
    "number_format",
    "currency",
    "float_precision",
    "enable_scheduler",
    "disable_document_sharing",
    "allow_login_using_mobile_number",
    "session_expiry",
]


def _shell_version(args: list[str]) -> str | None:
    try:
        out = subprocess.run(args, capture_output=True, text=True, timeout=10, check=False)
        return (out.stdout or out.stderr or "").strip() or None
    except Exception:
        return None


class BenchSource(Source):
    kind = "bench"

    def site_name(self) -> str | None:
        return getattr(frappe.local, "site", None)

    def get_all(self, doctype, fields, filters=None, order_by=None):
        if not frappe.db.exists("DocType", doctype):
            raise NotAvailable(doctype)
        try:
            rows = frappe.get_all(
                doctype, fields=fields, filters=filters or {}, order_by=order_by
            )
        except frappe.PermissionError as exc:
            raise AccessDenied(doctype) from exc
        return [dict(row) for row in rows]

    def get_doc(self, doctype, name):
        try:
            return frappe.get_doc(doctype, name).as_dict()
        except frappe.DoesNotExistError as exc:
            raise NotAvailable(f"{doctype} {name}") from exc

    def system_info(self) -> dict:
        return {
            "versions": self._versions(),
            "installed_apps": sorted(frappe.get_installed_apps()),
            "app_versions": self._app_versions(),
            "site_config": redact(frappe.get_site_config() or {}),
            "system_settings": self._system_settings(),
            "database": self._database_info(),
            "platform": platform.platform(),
        }

    # --- helpers ----------------------------------------------------------------

    def _db_version(self) -> str | None:
        try:
            return frappe.db.sql("SELECT VERSION()")[0][0]
        except Exception:
            return None

    def _versions(self) -> dict:
        versions = {
            "frappe": getattr(frappe, "__version__", None),
            "python": platform.python_version(),
        }
        try:
            import erpnext  # noqa: WPS433

            versions["erpnext"] = getattr(erpnext, "__version__", None)
        except Exception:
            versions["erpnext"] = None
        versions["node"] = _shell_version(["node", "--version"])
        versions["bench"] = _shell_version(["bench", "--version"])
        versions["mariadb"] = self._db_version()
        return versions

    def _app_versions(self) -> dict:
        try:
            from frappe.utils.change_log import get_versions

            data = get_versions() or {}
            return {app: info.get("version") for app, info in sorted(data.items())}
        except Exception:
            return {}

    def _database_info(self) -> dict:
        return {"type": frappe.conf.get("db_type") or "mariadb", "version": self._db_version()}

    def _system_settings(self) -> dict:
        try:
            ss = frappe.get_single("System Settings")
        except Exception:
            return {}
        return {f: ss.get(f) for f in _SAFE_SYSTEM_SETTINGS if ss.get(f) is not None}
