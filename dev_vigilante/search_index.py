"""Build the full-text search index (``search.json``) from a snapshot.

Pure and dependency-free. Produces deterministic, sorted output.
"""

from __future__ import annotations

import re

_TOKEN = re.compile(r"[A-Za-z0-9_]+")


def _doctype_of(artifact: dict) -> str | None:
    f = artifact.get("fields") or {}
    return (
        artifact.get("group")
        or f.get("doctype")
        or f.get("applies_to")
        or f.get("reference_doctype")
    )


def _keywords(artifact: dict) -> list[str]:
    tokens: set[str] = set()
    for tag in artifact.get("tags") or []:
        for tok in _TOKEN.findall(str(tag).lower()):
            tokens.add(tok)
    for tok in _TOKEN.findall(str(artifact.get("name", "")).lower()):
        tokens.add(tok)
    dt = _doctype_of(artifact)
    if dt:
        for tok in _TOKEN.findall(str(dt).lower()):
            tokens.add(tok)
    return sorted(tokens)


def build_search_index(artifacts: dict[str, dict]) -> dict:
    entries = []
    for key in sorted(artifacts):
        artifact = artifacts[key]
        entries.append(
            {
                "key": key,
                "collector": artifact.get("collector"),
                "type": artifact.get("type"),
                "name": artifact.get("name"),
                "doctype": _doctype_of(artifact),
                "purpose": artifact.get("summary"),
                "dependencies": [
                    d.get("name") for d in artifact.get("dependencies") or []
                ],
                "keywords": _keywords(artifact),
            }
        )
    return {"count": len(entries), "entries": entries}
