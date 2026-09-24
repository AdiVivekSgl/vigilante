"""System Information collector: versions, apps, modules, sanitized config.

How much is visible depends on the source: inside a site everything is available; over
REST only app versions and (with Read on Module Def) the module list.
"""

from __future__ import annotations

from dev_vigilante.artifact import Artifact
from dev_vigilante.collectors.base import STANDARD_APPS, BaseCollector
from dev_vigilante.sources.base import SourceError


class SystemInfoCollector(BaseCollector):
    key = "system_info"
    label = "System Information"
    order = 0

    def collect(self) -> list[Artifact]:
        info = self.source.system_info() or {}
        installed = info.get("installed_apps") or []
        custom_apps = [app for app in installed if app not in STANDARD_APPS]

        try:
            modules = self.source.get_all(
                "Module Def",
                ["name", "module_name", "app_name", "custom"],
                order_by="name asc",
            )
        except SourceError:
            modules = []

        fields = {
            "versions": info.get("versions") or {},
            "installed_apps": sorted(installed),
            "custom_apps": sorted(custom_apps),
            "app_versions": info.get("app_versions") or {},
            "modules": modules,
            "site_config": info.get("site_config") or {},
            "system_settings": info.get("system_settings") or {},
            "database": info.get("database") or {},
            "platform": info.get("platform"),
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
