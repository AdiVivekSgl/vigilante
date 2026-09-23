"""Heuristic static-analysis helpers for scripts and SQL.

Pure, dependency-free (no ``frappe``) so it is unit-testable outside a bench. These
are deliberately best-effort regex heuristics — they document *likely* structure for
human/AI readers, not a real parser.
"""

from __future__ import annotations

import re

# --- JavaScript / Client Script -------------------------------------------------

_JS_FORM_ON = re.compile(r"frappe\.ui\.form\.on\(\s*['\"]([^'\"]+)['\"]", re.MULTILINE)
_JS_FORM_ON_CALL = re.compile(r"frappe\.ui\.form\.on\(")
# Top-level keys within a handler object, once nested content has been masked out.
_JS_TOP_KEY_COLON = re.compile(r"([A-Za-z_]\w*)\s*:", re.MULTILINE)
_JS_TOP_KEY_SHORTHAND = re.compile(r"(?:^|,)\s*([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_JS_NAMED_FN = re.compile(r"\bfunction\s+([A-Za-z_$][\w$]*)\s*\(", re.MULTILINE)
_JS_ASSIGNED_FN = re.compile(
    r"\b(?:const|let|var)\s+([A-Za-z_$][\w$]*)\s*=\s*(?:async\s*)?(?:function|\()",
    re.MULTILINE,
)
_JS_FRM_FIELDS = re.compile(
    r"(?:frm\.doc\.([A-Za-z_]\w*))"
    r"|(?:set_value\(\s*['\"]([A-Za-z_]\w*)['\"])"
    r"|(?:get_field\(\s*['\"]([A-Za-z_]\w*)['\"])"
    r"|(?:set_df_property\(\s*['\"]([A-Za-z_]\w*)['\"])"
    r"|(?:toggle_display\(\s*['\"]([A-Za-z_]\w*)['\"])"
    r"|(?:toggle_reqd\(\s*['\"]([A-Za-z_]\w*)['\"])",
    re.MULTILINE,
)
_JS_REPORTS = re.compile(
    r"(?:query_report|frappe\.query_report)[^;]*?['\"]([^'\"]+)['\"]"
    r"|frappe\.set_route\(\s*['\"]query-report['\"]\s*,\s*['\"]([^'\"]+)['\"]",
    re.MULTILINE,
)
_JS_DOCTYPE_CALLS = re.compile(r"['\"]doctype['\"]\s*:\s*['\"]([^'\"]+)['\"]", re.MULTILINE)


def _dedupe(items):
    seen = []
    for item in items:
        if item and item not in seen:
            seen.append(item)
    return seen


def _handler_object(script: str, call_end: int) -> str | None:
    """Return the source of the ``{ ... }`` handler object of a form.on(...) call.

    ``call_end`` is the index just past ``frappe.ui.form.on(``. Uses brace matching
    (regex can't balance nested braces) so nested function bodies don't truncate it.
    """
    start = script.find("{", call_end)
    if start == -1:
        return None
    depth = 0
    for j in range(start, len(script)):
        c = script[j]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return script[start + 1 : j]
    return None


def _mask_nested(text: str) -> str:
    """Replace everything inside nested (), [], {} with spaces, keeping the top-level
    delimiters visible so top-level keys can be matched with simple regexes."""
    out = []
    depth = 0
    for c in text:
        if c in "([{":
            out.append(c if depth == 0 else " ")
            depth += 1
        elif c in ")]}":
            depth = max(0, depth - 1)
            out.append(c if depth == 0 else " ")
        else:
            out.append(c if depth == 0 else " ")
    return "".join(out)


def extract_form_events(script: str) -> list[str]:
    """Field/lifecycle events wired inside ``frappe.ui.form.on(...)`` handlers."""
    script = script or ""
    events: list[str] = []
    for call in _JS_FORM_ON_CALL.finditer(script):
        obj = _handler_object(script, call.end())
        if obj is None:
            continue
        masked = _mask_nested(obj)
        events.extend(_JS_TOP_KEY_COLON.findall(masked))
        events.extend(_JS_TOP_KEY_SHORTHAND.findall(masked))
    return _dedupe(events)


def extract_js_functions(script: str) -> list[str]:
    named = _JS_NAMED_FN.findall(script or "")
    assigned = _JS_ASSIGNED_FN.findall(script or "")
    return _dedupe(named + assigned)


def extract_referenced_fields(script: str) -> list[str]:
    fields: list[str] = []
    for groups in _JS_FRM_FIELDS.findall(script or ""):
        for value in groups:
            if value:
                fields.append(value)
    return _dedupe(fields)


def extract_referenced_reports(script: str) -> list[str]:
    reports: list[str] = []
    for groups in _JS_REPORTS.findall(script or ""):
        for value in groups:
            if value:
                reports.append(value)
    return _dedupe(reports)


def extract_form_doctypes(script: str) -> list[str]:
    return _dedupe(_JS_FORM_ON.findall(script or ""))


# --- Python / Server Script -----------------------------------------------------

_PY_DEF = re.compile(r"^\s*def\s+([A-Za-z_]\w*)\s*\(", re.MULTILINE)
_PY_FRAPPE_CALLS = re.compile(r"frappe\.(get_doc|get_all|get_list|db\.\w+|new_doc|call|sendmail)")
_PY_DOCTYPE_STR = re.compile(r"(?:get_doc|get_all|get_list|new_doc)\(\s*['\"]([^'\"]+)['\"]")


def extract_py_functions(script: str) -> list[str]:
    return _dedupe(_PY_DEF.findall(script or ""))


def extract_py_referenced_doctypes(script: str) -> list[str]:
    return _dedupe(_PY_DOCTYPE_STR.findall(script or ""))


def extract_py_frappe_apis(script: str) -> list[str]:
    return _dedupe(_PY_FRAPPE_CALLS.findall(script or ""))


# --- SQL ------------------------------------------------------------------------

_SQL_TABLES = re.compile(r"\b(?:from|join)\s+`?tab([A-Za-z][\w ]*?)`?\b", re.IGNORECASE)
_SQL_FILTER_MARKERS = re.compile(r"%\(([A-Za-z_]\w*)\)s|\{([A-Za-z_]\w*)\}")


def extract_sql_doctypes(sql: str) -> list[str]:
    """DocTypes referenced via ``tabXYZ`` table names in a query."""
    return _dedupe(t.strip() for t in _SQL_TABLES.findall(sql or ""))


def extract_sql_filters(sql: str) -> list[str]:
    filters: list[str] = []
    for a, b in _SQL_FILTER_MARKERS.findall(sql or ""):
        filters.append(a or b)
    return _dedupe(filters)


def count_lines(text: str) -> int:
    if not text:
        return 0
    return len(text.splitlines())
