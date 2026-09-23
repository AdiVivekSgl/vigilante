"""Central registry of collectors.

Adding a new artifact type to the snapshot is a two-line change: implement a
``BaseCollector`` subclass in its own module and append it to ``COLLECTOR_CLASSES``.
The engine iterates this list in ``order`` — no engine changes required.
"""

from __future__ import annotations

from dev_vigilante.collectors.base import BaseCollector, CollectorContext
from dev_vigilante.collectors.client_scripts import ClientScriptsCollector
from dev_vigilante.collectors.custom_doctypes import CustomDocTypesCollector
from dev_vigilante.collectors.custom_fields import CustomFieldsCollector
from dev_vigilante.collectors.server_scripts import ServerScriptsCollector
from dev_vigilante.collectors.system_info import SystemInfoCollector

# Order here is the fallback; each collector's ``order`` attribute is authoritative.
COLLECTOR_CLASSES: list[type[BaseCollector]] = [
    SystemInfoCollector,
    CustomFieldsCollector,
    ClientScriptsCollector,
    ServerScriptsCollector,
    CustomDocTypesCollector,
]


def build_collectors(context: CollectorContext) -> list[BaseCollector]:
    collectors = [cls(context) for cls in COLLECTOR_CLASSES]
    collectors.sort(key=lambda c: (c.order, c.key))
    return collectors
