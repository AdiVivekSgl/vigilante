"""Snapshot engine core — collectors, summaries, graph, diff and assembly.

Frappe-free: it reads only through a :class:`~dev_vigilante.sources.base.Source`, so it
serves both the in-site app (:mod:`dev_vigilante.snapshot`) and the REST CLI
(:mod:`dev_vigilante.cli`).
"""

from __future__ import annotations

import time
import traceback

import dev_vigilante
from dev_vigilante import change_detection, dependency, search_index
from dev_vigilante.collectors.base import CollectorContext
from dev_vigilante.collectors.registry import build_collectors
from dev_vigilante.sources.base import (
    AccessDenied,
    AuthenticationFailed,
    NotAvailable,
    SourceError,
)
from dev_vigilante.summarizers.base import get_summarizer


def build_context(source, scope: dict) -> tuple[CollectorContext, list[dict]]:
    """Collector context plus any warnings raised while building it."""
    warnings: list[dict] = []
    try:
        modules = source.get_all("Module Def", ["name", "app_name"])
    except SourceError as exc:
        modules = []
        warnings.append(
            {
                "collector": "context",
                "reason": f"Module Def not readable ({type(exc).__name__}); only "
                "UI-created DocTypes can be captured and module scoping is disabled.",
            }
        )
    app_by_module = {m.get("name"): m.get("app_name") for m in modules}
    return CollectorContext(scope, app_by_module), warnings


def run(
    source,
    scope: dict,
    previous_snapshot: dict | None = None,
    llm_config: dict | None = None,
    generated_on: str | None = None,
    log_error=None,
) -> dict:
    """Collect everything and assemble a snapshot.

    Collectors whose DocType is unreadable or missing are recorded under ``skipped``;
    other failures are recorded under ``errors`` (and passed to ``log_error``) —
    neither aborts the run. Authentication failures do.

    A collector that did not complete carries the previous snapshot's artifacts forward
    unchanged, so a transient failure never shows up as "everything was removed".
    """
    start = time.monotonic()
    context, skipped = build_context(source, scope)
    summarizer = get_summarizer(llm_config)

    artifacts: dict[str, dict] = {}
    collector_meta: list[dict] = []
    errors: list[dict] = []

    for collector in build_collectors(context, source):
        try:
            items = collector.collect()
        except AuthenticationFailed:
            raise
        except (AccessDenied, NotAvailable) as exc:
            skipped.append(
                {"collector": collector.key, "reason": f"{type(exc).__name__}: {exc}"}
            )
            _carry_forward(collector, previous_snapshot, artifacts, skipped[-1], collector_meta)
            continue
        except Exception:
            tb = traceback.format_exc()
            errors.append({"collector": collector.key, "error": tb})
            if log_error:
                log_error(tb, f"Dev Vigilante collector: {collector.key}")
            _carry_forward(collector, previous_snapshot, artifacts, errors[-1], collector_meta)
            continue

        for artifact in items:
            artifact.summary = summarizer.summarize(artifact)
            artifacts[artifact.key] = artifact.to_dict()

        collector_meta.append(
            {"key": collector.key, "label": collector.label, "count": len(items)}
        )

    counts = {m["key"]: m["count"] for m in collector_meta}
    counts["total"] = len(artifacts)

    snapshot = {
        "meta": {
            "generator": "Dev Vigilante",
            "app_version": dev_vigilante.__version__,
            "generated_on": generated_on,
            "source": getattr(source, "kind", None),
            "site": source.site_name(),
            "counts": counts,
            "skipped": skipped,
        },
        "collectors": collector_meta,
        "artifacts": artifacts,
        "dependency_graph": dependency.build_dependency_graph(artifacts),
        "search_index": search_index.build_search_index(artifacts),
        "changes": change_detection.diff(previous_snapshot, {"artifacts": artifacts}),
    }

    return {
        "snapshot": snapshot,
        "counts": counts,
        "changes": snapshot["changes"],
        "skipped": skipped,
        "errors": errors,
        "duration": round(time.monotonic() - start, 3),
    }


def _carry_forward(collector, previous_snapshot, artifacts, record, collector_meta) -> None:
    previous = (previous_snapshot or {}).get("artifacts") or {}
    kept = {k: a for k, a in previous.items() if a.get("collector") == collector.key}
    artifacts.update(kept)
    record["carried_forward"] = len(kept)
    if kept:
        collector_meta.append(
            {
                "key": collector.key,
                "label": collector.label,
                "count": len(kept),
                "carried_forward": True,
            }
        )
