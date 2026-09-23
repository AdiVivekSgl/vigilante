"""JSON exporter: machine-readable snapshot, per-collector files, search + graph."""

from __future__ import annotations

import json

from dev_vigilante.exporters.base import Exporter


def _dump(data) -> str:
    return json.dumps(data, sort_keys=True, indent=2, default=str) + "\n"


class JsonExporter(Exporter):
    name = "json"

    def build_files(self, snapshot: dict) -> dict:
        files: dict[str, str] = {}

        # Full snapshot.
        files["snapshot.json"] = _dump(snapshot)

        # Per-collector JSON for easy consumption / smaller diffs.
        by_collector: dict[str, list] = {}
        for key in sorted(snapshot.get("artifacts", {})):
            artifact = snapshot["artifacts"][key]
            by_collector.setdefault(artifact.get("collector"), []).append(artifact)

        for collector, items in sorted(by_collector.items()):
            files[f"json/{collector}.json"] = _dump(
                sorted(items, key=lambda a: a.get("key", ""))
            )

        # Search index.
        if snapshot.get("search_index") is not None:
            files["search.json"] = _dump(snapshot["search_index"])

        # Dependency graph.
        if snapshot.get("dependency_graph") is not None:
            files["dependency/dependency_graph.json"] = _dump(snapshot["dependency_graph"])

        # Changes.
        if snapshot.get("changes") is not None:
            files["changelog/changes.json"] = _dump(snapshot["changes"])

        return files
