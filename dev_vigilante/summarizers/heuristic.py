"""Deterministic, offline heuristic summarizer.

Given an :class:`~dev_vigilante.artifact.Artifact`, produce a short human/AI readable
summary derived entirely from its structured fields. Pure and dependency-free so the
same ERP state always yields identical text (clean Git diffs) and it is unit-testable
without a bench.
"""

from __future__ import annotations

from dev_vigilante.artifact import Artifact


def _join(items, limit=6):
    items = [str(i) for i in items if i]
    if not items:
        return ""
    if len(items) > limit:
        shown = items[:limit]
        return ", ".join(shown) + f" (+{len(items) - limit} more)"
    return ", ".join(items)


def summarize(artifact: Artifact) -> str:
    handler = _HANDLERS.get(artifact.collector, _generic)
    try:
        return handler(artifact).strip()
    except Exception:
        return _generic(artifact).strip()


# --- per-collector handlers -----------------------------------------------------

def _custom_field(a: Artifact) -> str:
    f = a.fields
    label = f.get("label") or f.get("fieldname")
    parts = [
        f"Adds a {f.get('field_type') or 'custom'} field "
        f"“{label}” ({f.get('fieldname')}) to {f.get('doctype')}."
    ]
    flags = []
    if f.get("mandatory"):
        flags.append("mandatory")
    if f.get("read_only"):
        flags.append("read-only")
    if f.get("hidden"):
        flags.append("hidden")
    if flags:
        parts.append(f"It is {_join(flags)}.")
    if f.get("fetch_from"):
        parts.append(f"Its value is fetched from {f.get('fetch_from')}.")
    if f.get("depends_on"):
        parts.append(f"Displayed conditionally via depends-on ({f.get('depends_on')}).")
    if f.get("options") and f.get("field_type") in ("Link", "Select", "Table", "Dynamic Link"):
        opt = str(f.get("options")).splitlines()[0]
        parts.append(f"Options/target: {opt}.")
    return " ".join(parts)


def _client_script(a: Artifact) -> str:
    f = a.fields
    state = "enabled" if f.get("enabled") else "disabled"
    parts = [
        f"{state.capitalize()} client script for {f.get('applies_to')} "
        f"({f.get('view') or 'Form'} view)."
    ]
    if f.get("events_used"):
        parts.append(f"Reacts to events: {_join(f['events_used'])}.")
    if f.get("functions_detected"):
        parts.append(f"Defines {len(f['functions_detected'])} function(s): {_join(f['functions_detected'])}.")
    if f.get("referenced_fields"):
        parts.append(f"References fields: {_join(f['referenced_fields'])}.")
    if f.get("referenced_reports"):
        parts.append(f"Links to reports: {_join(f['referenced_reports'])}.")
    return " ".join(parts)


def _server_script(a: Artifact) -> str:
    f = a.fields
    trigger = f.get("trigger") or "Server"
    parts = []
    if f.get("is_scheduled"):
        parts.append(f"Scheduled server script running {f.get('event') or 'periodically'}.")
    elif f.get("is_api"):
        parts.append(
            f"API server script exposed at method “{f.get('api_method')}”"
            + (" (guest allowed)." if f.get("allow_guest") else ".")
        )
    elif f.get("is_permission_query"):
        parts.append(f"Permission-query script for {f.get('reference_doctype')}.")
    else:
        parts.append(
            f"{trigger} script on {f.get('reference_doctype')} "
            f"triggered on {f.get('event') or 'a document event'}."
        )
    if f.get("disabled"):
        parts.append("Currently disabled.")
    if f.get("referenced_doctypes"):
        parts.append(f"Touches DocTypes: {_join(f['referenced_doctypes'])}.")
    if f.get("frappe_apis_used"):
        parts.append(f"Uses APIs: {_join(f['frappe_apis_used'])}.")
    return " ".join(parts)


def _custom_doctype(a: Artifact) -> str:
    f = a.fields
    kind = "child table" if f.get("is_child_table") else (
        "single DocType" if f.get("is_single") else "DocType"
    )
    parts = [
        f"Custom {kind} “{a.name}” in the {f.get('module')} module "
        f"with {f.get('field_count', 0)} fields."
    ]
    if f.get("is_submittable"):
        parts.append("It is submittable.")
    roles = [p.get("role") for p in f.get("permissions", []) if p.get("role")]
    if roles:
        parts.append(f"Permissions defined for {len(set(roles))} role(s): {_join(sorted(set(roles)))}.")
    if f.get("child_tables"):
        parts.append(
            "Embeds child tables: "
            + _join([c.get("child_doctype") for c in f["child_tables"]])
            + "."
        )
    if f.get("links"):
        parts.append(
            "Links to: " + _join([l.get("target") for l in f["links"]]) + "."
        )
    if f.get("workflows"):
        parts.append(f"Governed by workflow(s): {_join(f['workflows'])}.")
    naming = (f.get("naming") or {}).get("autoname")
    if naming:
        parts.append(f"Named via {naming}.")
    return " ".join(parts)


def _system_info(a: Artifact) -> str:
    f = a.fields
    versions = f.get("versions", {})
    custom_apps = f.get("custom_apps", [])
    parts = [
        f"ERP instance running Frappe {versions.get('frappe') or '?'}"
    ]
    if versions.get("erpnext"):
        parts[0] += f" and ERPNext {versions['erpnext']}"
    parts[0] += "."
    parts.append(
        f"{len(f.get('installed_apps', []))} installed app(s); "
        f"{len(custom_apps)} custom app(s)"
        + (f": {_join(custom_apps)}." if custom_apps else ".")
    )
    parts.append(f"{len(f.get('modules', []))} module(s) defined.")
    return " ".join(parts)


def _generic(a: Artifact) -> str:
    return f"{a.type}: {a.name}."


_HANDLERS = {
    "custom_fields": _custom_field,
    "client_scripts": _client_script,
    "server_scripts": _server_script,
    "custom_doctypes": _custom_doctype,
    "system_info": _system_info,
}
