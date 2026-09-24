"""``vigilante`` command line: snapshot a remote ERPNext site over the REST API.

    vigilante check                      test the connection and permissions
    vigilante refresh --output DIR       write DIR/developer_snapshot (only when changed)

Credentials come from environment variables, usually via a ``.env`` file in the current
directory (``FRAPPE_URL``, ``FRAPPE_API_KEY``, ``FRAPPE_API_SECRET``; optional
``VIGILANTE_OUTPUT``). Everything is read-only: the REST client can only send GET.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

from dev_vigilante import change_detection, engine
from dev_vigilante.exporters.zip_exporter import ROOT_FOLDER, build_all_files, write_folder
from dev_vigilante.sources.base import AccessDenied, AuthenticationFailed, NotAvailable, SourceError
from dev_vigilante.sources.rest import RestClient, RestSource

# What each collector needs Read access to, in the order `check` reports it.
REQUIRED_DOCTYPES = [
    ("Module Def", "app ownership of modules (needed to find custom-app DocTypes)"),
    ("Custom Field", "Custom Fields"),
    ("Property Setter", "Property Setters"),
    ("Client Script", "Client Scripts"),
    ("Server Script", "Server Scripts"),
    ("DocType", "Custom DocTypes"),
    ("Workflow", "workflows linked from DocTypes"),
]

# Roles that make the API user able to change the site: the auditor should have none.
_POWERFUL_ROLES = {"Administrator", "System Manager"}

# This repository is public; snapshots must never be written inside it.
_TOOL_REPO = Path(__file__).resolve().parents[1]


class CliError(Exception):
    """A user-facing error: printed without a traceback."""


# --- environment ------------------------------------------------------------------


def load_env_file(path: Path) -> None:
    """Load KEY=VALUE lines into ``os.environ`` without overriding existing variables."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if key.startswith("export "):
            key = key[len("export "):].strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
            value = value[1:-1]
        os.environ.setdefault(key, value)


def make_source() -> RestSource:
    missing = [k for k in ("FRAPPE_URL", "FRAPPE_API_KEY", "FRAPPE_API_SECRET") if not os.environ.get(k)]
    if missing:
        raise CliError(
            "Missing " + ", ".join(missing) + ". Put them in a .env file in this folder "
            "(see .env.example) or pass --env PATH."
        )
    try:
        client = RestClient(
            os.environ["FRAPPE_URL"], os.environ["FRAPPE_API_KEY"], os.environ["FRAPPE_API_SECRET"]
        )
    except ValueError as exc:
        raise CliError(str(exc)) from exc
    return RestSource(client)


# --- check ------------------------------------------------------------------------


def connect(source) -> str:
    """Fail fast, with one clear message, when the site is unreachable or rejects us."""
    try:
        user = source.logged_user()
    except AuthenticationFailed as exc:
        raise CliError(f"{exc} Regenerate the keys for the API user and update .env.") from exc
    except SourceError as exc:
        raise CliError(str(exc)) from exc
    if not user or user == "Guest":
        raise CliError("The site treated the request as Guest; check the API key and secret.")
    return user


def cmd_check(args, source: RestSource, out=print) -> int:
    user = connect(source)
    out(f"Connected to {source.client.base_url} as {user}")

    ok = True
    for warning in _role_warnings(source, user):
        out(f"  [WARN] {warning}")

    out("")
    out("Read access:")
    for doctype, purpose in REQUIRED_DOCTYPES:
        try:
            source.client.list(doctype, ["name"], limit=1)
            status = "[ok]     "
        except AccessDenied:
            status = "[BLOCKED]"
            ok = False
        except NotAvailable:
            status = "[missing]"
        except SourceError as exc:
            status = f"[error: {exc}]"
            ok = False
        out(f"  {status} {doctype:<16} {purpose}")

    out("")
    if ok:
        out("All set. Run: vigilante refresh --output <folder outside this repo>")
        return 0
    out(
        "Some DocTypes are blocked. In ERPNext open Role Permissions Manager, pick each "
        "blocked DocType and give your auditor role Read (only Read). Blocked collectors are "
        "skipped, not fatal."
    )
    return 1


def _role_warnings(source: RestSource, user: str) -> list[str]:
    if user == "Administrator":
        return ["Connected as Administrator. Use a dedicated read-only API user instead."]
    try:
        doc = source.client.doc("User", user)
    except SourceError:
        return []
    roles = {r.get("role") for r in doc.get("roles") or []}
    powerful = sorted(roles & _POWERFUL_ROLES)
    if powerful:
        return [
            f"API user has {', '.join(powerful)}, which can change the site. "
            "Give it only a read-only auditor role."
        ]
    return []


# --- refresh ----------------------------------------------------------------------


def resolve_output(value: str | None) -> Path:
    value = value or os.environ.get("VIGILANTE_OUTPUT")
    if not value:
        raise CliError(
            "Choose where to write the snapshot: --output PATH or VIGILANTE_OUTPUT in .env. "
            "Use a folder outside this repository (for example a private Git repo)."
        )
    output = Path(value).expanduser().resolve()
    if output == _TOOL_REPO or _TOOL_REPO in output.parents:
        raise CliError(
            f"{output} is inside the Vigilante repository, which is public. "
            "Write snapshots to a separate, private folder."
        )
    return output


def load_previous(output: Path) -> dict | None:
    path = output / ROOT_FOLDER / "snapshot.json"
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def cmd_refresh(args, source, out=print) -> int:
    output = resolve_output(args.output)
    connect(source)
    previous = load_previous(output)
    scope = {"include_raw_source": not args.no_raw_source, "include_standard_apps": False}

    try:
        result = engine.run(
            source,
            scope,
            previous_snapshot=previous,
            generated_on=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )
    except AuthenticationFailed as exc:
        raise CliError(f"{exc} Regenerate the keys for the API user and update .env.") from exc

    for skip in result["skipped"]:
        out(f"[skipped] {skip['collector']}: {skip['reason']}")
    if result["errors"]:
        for err in result["errors"]:
            last = err["error"].strip().splitlines()[-1]
            out(f"[error]   {err['collector']}: {last}")
        out("Nothing written: fix the errors above and run refresh again.")
        return 1

    changes = result["changes"]
    target = output / ROOT_FOLDER
    if previous and change_detection.is_empty(changes) and not args.force:
        out(f"No changes since the last refresh. {target} left as is.")
        return 0

    write_folder(build_all_files(result["snapshot"]), str(output))

    counts = result["counts"]
    out(f"Wrote {target}")
    out("  " + ", ".join(f"{k}: {v}" for k, v in sorted(counts.items()) if k != "total"))
    out(f"  total: {counts.get('total', 0)} artifacts in {result['duration']}s")
    if previous:
        s = changes["summary"]
        out(f"  changes: +{s['added']} -{s['removed']} ~{s['modified']} (see changelog/CHANGES.md)")
    return 0


# --- entry point ------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="vigilante",
        description="Read-only ERPNext customization snapshots over the Frappe REST API.",
    )
    parser.add_argument("--env", default=".env", help="path to the .env file (default: ./.env)")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("check", help="test the connection and the API user's read access")

    refresh = sub.add_parser("refresh", help="snapshot the site into OUTPUT/developer_snapshot")
    refresh.add_argument("--output", "-o", help="folder to write into (default: $VIGILANTE_OUTPUT)")
    refresh.add_argument(
        "--no-raw-source", action="store_true", help="omit full Client/Server Script source"
    )
    refresh.add_argument(
        "--force", action="store_true", help="rewrite the folder even if nothing changed"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    load_env_file(Path(args.env))
    try:
        source = make_source()
        if args.command == "check":
            return cmd_check(args, source)
        return cmd_refresh(args, source)
    except CliError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
