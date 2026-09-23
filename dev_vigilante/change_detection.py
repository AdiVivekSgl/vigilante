"""Change detection between two snapshots.

Pure and dependency-free. A snapshot is the dict produced by the engine; the relevant
part is ``snapshot["artifacts"]`` — a mapping of stable artifact ``key`` -> artifact
dict (which carries a ``content_hash``).
"""

from __future__ import annotations

from typing import Any

# Collector keys used to bucket highlights.
_SCRIPT_COLLECTORS = {"client_scripts", "server_scripts"}


def _artifacts(snapshot: dict | None) -> dict[str, dict]:
    if not snapshot:
        return {}
    return snapshot.get("artifacts") or {}


def _brief(artifact: dict) -> dict:
    return {
        "key": artifact.get("key"),
        "collector": artifact.get("collector"),
        "type": artifact.get("type"),
        "name": artifact.get("name"),
        "summary": artifact.get("summary"),
    }


def _changed_fields(prev: dict, cur: dict) -> list[str]:
    """Names of top-level structured fields that differ between two artifacts."""
    changed: list[str] = []
    prev_fields = prev.get("fields") or {}
    cur_fields = cur.get("fields") or {}
    for name in sorted(set(prev_fields) | set(cur_fields)):
        if prev_fields.get(name) != cur_fields.get(name):
            changed.append(name)

    if (prev.get("raw") or {}) != (cur.get("raw") or {}):
        changed.append("raw_source")
    if (prev.get("dependencies") or []) != (cur.get("dependencies") or []):
        changed.append("dependencies")
    return changed


def diff(previous: dict | None, current: dict | None) -> dict[str, Any]:
    prev = _artifacts(previous)
    cur = _artifacts(current)

    prev_keys = set(prev)
    cur_keys = set(cur)

    added = [_brief(cur[k]) for k in sorted(cur_keys - prev_keys)]
    removed = [_brief(prev[k]) for k in sorted(prev_keys - cur_keys)]

    modified = []
    for key in sorted(prev_keys & cur_keys):
        if prev[key].get("content_hash") != cur[key].get("content_hash"):
            entry = _brief(cur[key])
            entry["changed_fields"] = _changed_fields(prev[key], cur[key])
            modified.append(entry)

    result = {
        "summary": {
            "added": len(added),
            "removed": len(removed),
            "modified": len(modified),
        },
        "added": added,
        "removed": removed,
        "modified": modified,
        "highlights": _highlights(added, removed, modified),
    }
    return result


def _highlights(added, removed, modified) -> dict[str, list]:
    """Spec-mandated highlights: new fields, deleted reports, changed scripts,
    changed SQL, changed permissions."""
    highlights = {
        "new_fields": [a["name"] for a in added if a.get("collector") == "custom_fields"],
        "deleted_reports": [r["name"] for r in removed if r.get("collector") == "reports"],
        "changed_scripts": [
            m["name"] for m in modified if m.get("collector") in _SCRIPT_COLLECTORS
        ],
        "changed_sql": [
            m["name"]
            for m in modified
            if m.get("collector") == "reports" and "sql" in (m.get("changed_fields") or [])
        ],
        "changed_permissions": [
            m["name"]
            for m in modified
            if "permissions" in (m.get("changed_fields") or [])
        ],
    }
    return highlights


def is_empty(diff_result: dict) -> bool:
    s = diff_result.get("summary", {})
    return not (s.get("added") or s.get("removed") or s.get("modified"))
