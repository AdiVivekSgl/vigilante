"""Exporter base + shared rendering helpers.

Exporters implement ``build_files(snapshot) -> {relpath: content}`` (pure) so the same
output can be written to a Git-ready folder or streamed into a ZIP, and so rendering is
unit-testable without a filesystem.
"""

from __future__ import annotations

import re

_SLUG_UNSAFE = re.compile(r"[^A-Za-z0-9._-]+")


def safe_filename(name: str) -> str:
    """Deterministic, path-safe file stem for an artifact name."""
    name = (name or "unnamed").strip()
    name = name.replace("/", "-").replace("\\", "-")
    name = _SLUG_UNSAFE.sub("-", name)
    name = re.sub(r"-{2,}", "-", name).strip("-.")
    return name or "unnamed"


def md_escape(value) -> str:
    if value is None:
        return ""
    return str(value).replace("|", "\\|").replace("\n", " ")


def md_table(headers: list[str], rows: list[list]) -> str:
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(md_escape(c) for c in row) + " |")
    return "\n".join(lines)


def yesno(value) -> str:
    return "Yes" if value else "No"


class Exporter:
    #: subclasses override
    name = "exporter"

    def build_files(self, snapshot: dict) -> dict:  # pragma: no cover - interface
        raise NotImplementedError
