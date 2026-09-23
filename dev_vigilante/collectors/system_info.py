"""System Information collector: versions, apps, modules, sanitized config."""

from __future__ import annotations

import platform
import subprocess

import frappe

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import STANDARD_APPS, BaseCollector
from dev_vigilante.redaction import redact


def _shell_version(args: list[str]) -> str | None:
    try:
        out = subprocess.run(
            args, capture_output=True, text=True, timeout=10, check=False
        )
        return (out.stdout or out.stderr or "").strip() or None
    except Exception:
        return None


class SystemInfoCollector(BaseCollector):
    key = "system_info"
    label = "System Information"
    order = 0

    def collect(self) -> list[Artifact]:
        versions = self._versions()
        installed = frappe.get_installed_apps()
        custom_apps = [app for app in installed if app not in STANDARD_APPS]

        modules = frappe.get_all(
            "Module Def",
            fields=["name", "module_name", "app_name", "custom"],
            order_by="name asc",
        )

        fields = {
            "versions": versions,
            "installed_apps": sorted(installed),
            "custom_apps": sorted(custom_apps),
            "app_versions": self._app_versions(),
            "modules": modules,
            "site_config": redact(frappe.get_site_config() or {}),
            "system_settings": self._system_settings(),
            "database": self._database_info(),
            "platform": platform.platform(),
        }

        artifact = Artifact(
            collector=self.key,
            type="System Information",
            name="System Information",
            key="system-information",
            fields=fields,
            tags=["system", "versions", "apps", "modules"] + sorted(custom_apps),
        )
        return [artifact]

    # --- helpers ----------------------------------------------------------------

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
        try:
            versions["mariadb"] = frappe.db.sql("SELECT VERSION()")[0][0]
        except Exception:
            versions["mariadb"] = None
        return versions

    def _app_versions(self) -> dict:
        try:
            from frappe.utils.change_log import get_versions

            data = get_versions() or {}
            return {
                app: info.get("version")
                for app, info in sorted(data.items())
            }
        except Exception:
            return {}

    def _database_info(self) -> dict:
        info = {"type": frappe.conf.get("db_type") or "mariadb"}
        try:
            info["version"] = frappe.db.sql("SELECT VERSION()")[0][0]
        except Exception:
            info["version"] = None
        return info

    def _system_settings(self) -> dict:
        try:
            ss = frappe.get_single("System Settings")
        except Exception:
            return {}
        safe_fields = [
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
        return {f: ss.get(f) for f in safe_fields if ss.get(f) is not None}
