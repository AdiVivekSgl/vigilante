"""Whitelisted API + scheduler entry points for Dev Vigilante."""

from __future__ import annotations

import frappe
from frappe import _
from frappe.utils import add_to_date, cint, get_datetime, now, now_datetime

from dev_vigilante.exporters.markdown_exporter import MarkdownExporter
from dev_vigilante.exporters.zip_exporter import (
    build_all_files,
    build_zip_bytes,
    write_folder,
)
from dev_vigilante.snapshot import SnapshotEngine, get_previous_snapshot_data
from dev_vigilante.dev_vigilante.doctype.vigilante_settings.vigilante_settings import (
    get_settings,
)

# LLM summaries make one HTTP call per artifact, so large sites can take a while.
JOB_TIMEOUT = 60 * 60
# An "In Progress" snapshot older than this is assumed to belong to a dead worker.
STALE_AFTER_SECONDS = 2 * JOB_TIMEOUT

REALTIME_EVENT = "dev_vigilante_snapshot"


def _format_bytes(num: int) -> str:
    value = float(num or 0)
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.1f} {unit}" if unit != "B" else f"{int(value)} B"
        value /= 1024
    return f"{value:.1f} GB"


@frappe.whitelist()
def generate_snapshot(
    trigger_type: str = "Manual", export_format: str | None = None, run_now=0
):
    """Start a snapshot run and return its record name.

    The run itself happens on the ``long`` background queue (it can outlast a web
    request, especially with LLM summaries). Pass ``run_now=1`` to run inline, e.g.
    from ``bench execute``; the full result summary is then returned.
    """
    frappe.only_for("System Manager")
    _ensure_not_running()

    settings = get_settings()
    export_format = export_format or settings.default_export_format or "ZIP"

    doc = frappe.get_doc(
        {
            "doctype": "Vigilante Snapshot",
            "status": "In Progress",
            "trigger_type": trigger_type,
            "generated_on": now(),
            "triggered_by": frappe.session.user,
            "export_format": export_format,
        }
    ).insert(ignore_permissions=True)
    # The worker must be able to see the row before it starts.
    frappe.db.commit()

    if cint(run_now):
        return run_snapshot_job(doc.name)

    frappe.enqueue(
        "dev_vigilante.api.run_snapshot_job",
        queue="long",
        timeout=JOB_TIMEOUT,
        job_id=f"dev_vigilante::{doc.name}",
        snapshot_name=doc.name,
    )
    return {"name": doc.name, "status": "In Progress", "queued": True}


def _ensure_not_running() -> None:
    """Refuse to start a second concurrent run; expire runs whose worker died."""
    cutoff = add_to_date(now_datetime(), seconds=-STALE_AFTER_SECONDS)
    running = frappe.get_all(
        "Vigilante Snapshot",
        filters={"status": "In Progress"},
        fields=["name", "creation"],
    )
    for row in running:
        if get_datetime(row.creation) < cutoff:
            frappe.db.set_value(
                "Vigilante Snapshot",
                row.name,
                {"status": "Failed", "error_log": "Abandoned: the background job never finished."},
            )
        else:
            frappe.throw(_("Snapshot {0} is already in progress.").format(row.name))


def run_snapshot_job(snapshot_name: str) -> dict:
    """Background job: collect, export, attach, and record the run."""
    doc = frappe.get_doc("Vigilante Snapshot", snapshot_name)
    settings = get_settings()
    export_format = doc.export_format or "ZIP"

    try:
        previous = get_previous_snapshot_data(exclude_name=doc.name)
        result = SnapshotEngine(settings).run(previous_snapshot=previous)
        snapshot = result["snapshot"]
        snapshot["meta"]["snapshot_id"] = doc.name

        zip_bytes = build_zip_bytes(snapshot, export_format=export_format)
        file_url = _attach_export(doc, zip_bytes)

        if export_format == "Git-ready folder" and settings.output_directory:
            write_folder(build_all_files(snapshot, export_format), settings.output_directory)

        counts = result["counts"]
        changes = result["changes"]
        changes_summary = changes.get("summary", {})

        doc.db_set(
            {
                "status": "Completed",
                "total_artifacts": counts.get("total", 0),
                "custom_fields_count": counts.get("custom_fields", 0),
                "client_scripts_count": counts.get("client_scripts", 0),
                "server_scripts_count": counts.get("server_scripts", 0),
                "custom_doctypes_count": counts.get("custom_doctypes", 0),
                "generation_duration": result["duration"],
                "export_size_bytes": len(zip_bytes),
                "export_size": _format_bytes(len(zip_bytes)),
                "changes_added": changes_summary.get("added", 0),
                "changes_removed": changes_summary.get("removed", 0),
                "changes_modified": changes_summary.get("modified", 0),
                "previous_snapshot": _previous_snapshot_name(doc.name),
                "snapshot_json": frappe.as_json(snapshot),
                "changes_json": frappe.as_json(changes),
                "changes_markdown": MarkdownExporter()._render_changes(changes),
                "export_file": file_url,
                "title": f"Snapshot {doc.name} — {counts.get('total', 0)} artifacts",
            },
            commit=False,
        )
        _prune_snapshots(settings)
        frappe.db.commit()

        summary = {
            "name": doc.name,
            "status": "Completed",
            "counts": counts,
            "changes": changes_summary,
            "duration": result["duration"],
            "export_size": _format_bytes(len(zip_bytes)),
            "file_url": file_url,
            "errors": result["errors"],
        }
        _notify(doc, summary)
        return summary
    except Exception:
        frappe.db.rollback()
        tb = frappe.get_traceback()
        doc.db_set({"status": "Failed", "error_log": tb}, commit=True)
        frappe.log_error(title="Dev Vigilante snapshot", message=tb)
        _notify(doc, {"name": doc.name, "status": "Failed"})
        raise


def _notify(doc, payload: dict) -> None:
    if doc.triggered_by:
        frappe.publish_realtime(REALTIME_EVENT, payload, user=doc.triggered_by)


def _attach_export(doc, content: bytes) -> str:
    from frappe.utils.file_manager import save_file

    filename = f"{doc.name}.zip"
    file_doc = save_file(
        filename,
        content,
        doc.doctype,
        doc.name,
        is_private=1,
    )
    return file_doc.file_url


def _previous_snapshot_name(exclude_name: str) -> str | None:
    rows = frappe.get_all(
        "Vigilante Snapshot",
        filters={"status": "Completed", "name": ["!=", exclude_name]},
        fields=["name"],
        order_by="creation desc",
        limit=1,
    )
    return rows[0].name if rows else None


def _prune_snapshots(settings) -> None:
    retain = int(settings.retain_snapshots or 0)
    if retain <= 0:
        return
    rows = frappe.get_all(
        "Vigilante Snapshot",
        fields=["name"],
        order_by="creation desc",
    )
    for row in rows[retain:]:
        frappe.delete_doc("Vigilante Snapshot", row.name, ignore_permissions=True, force=True)


@frappe.whitelist()
def get_dashboard_data():
    """Metrics for the dashboard page."""
    frappe.only_for("System Manager")

    latest = frappe.get_all(
        "Vigilante Snapshot",
        filters={"status": "Completed"},
        fields=[
            "name",
            "generated_on",
            "total_artifacts",
            "custom_fields_count",
            "client_scripts_count",
            "server_scripts_count",
            "custom_doctypes_count",
            "generation_duration",
            "export_size",
            "changes_added",
            "changes_removed",
            "changes_modified",
        ],
        order_by="creation desc",
        limit=1,
    )
    history = frappe.get_all(
        "Vigilante Snapshot",
        fields=[
            "name",
            "status",
            "generated_on",
            "trigger_type",
            "total_artifacts",
            "changes_added",
            "changes_removed",
            "changes_modified",
        ],
        order_by="creation desc",
        limit=10,
    )
    return {
        "latest": latest[0] if latest else None,
        "history": history,
        "total_snapshots": frappe.db.count("Vigilante Snapshot"),
    }


@frappe.whitelist()
def download_snapshot(name: str):
    """Return the export file URL for a snapshot."""
    frappe.only_for("System Manager")
    file_url = frappe.db.get_value("Vigilante Snapshot", name, "export_file")
    if not file_url:
        frappe.throw(f"No export attached to snapshot {name}.")
    return {"file_url": file_url}


# --- scheduler entry points -----------------------------------------------------

def run_weekly_snapshot():
    _run_scheduled_if_due("Weekly")


def run_monthly_snapshot():
    _run_scheduled_if_due("Monthly")


def run_scheduled_snapshot():
    """Generic entry (used by legacy hook / on-demand); runs if scheduling enabled."""
    settings = get_settings()
    if settings.enable_scheduled_snapshots:
        _generate_as_system("Scheduled")


def _run_scheduled_if_due(frequency: str):
    settings = get_settings()
    if settings.enable_scheduled_snapshots and (settings.schedule_frequency == frequency):
        _generate_as_system("Scheduled")


def _generate_as_system(trigger_type: str):
    # Scheduler runs as Administrator; only_for("System Manager") passes for Administrator.
    try:
        generate_snapshot(trigger_type=trigger_type)
    except Exception:
        frappe.log_error(title="Dev Vigilante scheduled snapshot", message=frappe.get_traceback())
