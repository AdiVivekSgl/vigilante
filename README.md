# Dev Vigilante

**Developer Intelligence & Context Snapshot (DISC) for ERPNext / Frappe.**

Dev Vigilante inventories, documents, versions, and exports every customization made to
an ERPNext/Frappe instance. It produces a structured, human-readable, AI-optimized
snapshot that can be committed to Git or handed to an AI coding assistant to provide
complete project context — without anyone having to manually explore the ERP.

> **Non-invasive by design.** The app is strictly *read-only* with respect to ERP
> metadata. It only writes its own DocType rows and the export files it produces.

It runs two ways, sharing the same collectors, change detection and exporters:

- **Remote CLI (recommended)** — `vigilante` runs on your machine and reads the site over
  the Frappe REST API with a read-only API user. Nothing is installed on the ERP. See
  [Remote CLI](#remote-cli-rest-api).
- **In-site app** — installed on the bench, with a dashboard, scheduled snapshots and
  optional LLM summaries. See [Install (Frappe v15)](#install-frappe-v15).

---

## What it captures (MVP core)

| Collector        | What it documents                                                        |
|------------------|--------------------------------------------------------------------------|
| System Info      | Frappe/ERPNext/Python/Node/MariaDB/Bench versions, installed & custom apps, modules, sanitized site config & system settings |
| Custom Fields    | Every Custom Field with DocType, label, type, options, depends-on, flags, insert-after, fetch-from, default, description |
| Property Setters | Every Customize Form override of a standard field/DocType property (label, reqd, hidden, options, default print format, ...) |
| Client Scripts   | Script, applies-to, enabled, parsed functions/events/referenced fields, summary |
| Server Scripts   | Script type/trigger/event/API/scheduled, reference DocType, summary       |
| Custom DocTypes  | UI-created DocTypes (any module) and DocTypes shipped by custom apps: fields, permissions, links, naming, workflow reference, summary |

The architecture is built around pluggable **collectors** and **exporters**, so the
remaining artifact types from the full DISC spec (Reports, Print Formats, Workspaces,
Workflows, Notifications, Roles/Permissions, Web Forms, Fixtures, Hooks, Custom Apps,
etc.) slot in later as new files without changing the engine.

## Output

Each run produces a `developer_snapshot/` tree, bundled as a ZIP and attached to the
`Vigilante Snapshot` record:

```
developer_snapshot/
  README.md              # index of the snapshot
  snapshot.json          # full machine-readable snapshot
  search.json            # full-text search index
  changelog/CHANGES.md   # added / removed / modified vs previous snapshot
  system/                # system information
  custom_fields/         # per-DocType custom field pages
  scripts/               # per-script pages
  doctypes/              # per-DocType pages
  ...
```

## AI summaries

Every object receives a generated summary. Summaries are **pluggable**:

- **Heuristic (default):** deterministic, offline, rule-based prose derived from the
  parsed structure of each object. Same ERP state → identical output (clean Git diffs).
- **LLM (optional):** enable a provider (Claude / OpenAI) in **Vigilante Settings** to
  generate richer prose. Requires network + an API key.

## Remote CLI (REST API)

### 1. On ERPNext (admin, once)

1. **Role → New**: `ERPNext Auditor`.
2. **Role Permissions Manager**: give that role **Read only** on `Module Def`,
   `Custom Field`, `Property Setter`, `Client Script`, `Server Script`, `DocType`,
   `Workflow`.
3. **User → New**, a *System User* (e.g. `erpnext-auditor@yourdomain.com`) with **only**
   the `ERPNext Auditor` role — never System Manager or Administrator.
4. On that user: **Settings → API Access → Generate Keys**. Copy the key and secret.

### 2. On your machine

Python 3.10+ is required. From a clone of this repository:

```bash
python -m venv .venv
.venv\Scripts\activate        # Windows (source .venv/bin/activate elsewhere)
pip install -e .
```

Create `.env` next to `pyproject.toml` (it is git-ignored; see `.env.example`):

```text
FRAPPE_URL=https://your-site.frappe.cloud
FRAPPE_API_KEY=...
FRAPPE_API_SECRET=...
VIGILANTE_OUTPUT=C:\path\to\erpnext-config
```

`VIGILANTE_OUTPUT` must be **outside this repository** (this repo is public; the tool
refuses to write inside it). A separate *private* Git repo is ideal — Git history then
becomes the history of your GUI configuration.

### 3. Use it

```bash
vigilante check      # connection, API user's roles, Read access per DocType
vigilante refresh    # writes $VIGILANTE_OUTPUT/developer_snapshot
```

- `refresh` only rewrites the folder when a customization actually changed, and lists
  the changes in `developer_snapshot/changelog/CHANGES.md`.
- DocTypes the API user cannot read are **skipped** (reported, not fatal); their previous
  results are kept rather than reported as deleted.
- Options: `--output PATH`, `--no-raw-source` (omit script bodies), `--force`, and
  `--env PATH` for a `.env` elsewhere.

The REST client only ever sends `GET` requests, refuses plain `http://` for non-local
sites, and will not follow redirects to another host (which would leak the token).

## Install (Frappe v15)

```bash
bench get-app https://github.com/AdiVivekSgl/vigilante
bench --site your.site install-app dev_vigilante
bench --site your.site migrate
bench restart
```

Snapshots run on the `long` background queue, so the site needs its workers running
(standard on production benches via supervisor; in development, `bench start`).
Scheduled snapshots also need the scheduler enabled (`bench --site your.site enable-scheduler`).

Then open the **Dev Vigilante Dashboard** at `/app/vigilante-dashboard` and click
**Generate Snapshot** — you'll get a notification when it finishes. Only System Managers
can generate or download snapshots. Or run one inline from the shell:

```bash
bench --site your.site execute dev_vigilante.api.generate_snapshot --kwargs "{'run_now': 1}"
```

### Settings worth knowing

- **Export format** — `ZIP` (Markdown + JSON), `Markdown only`, `JSON only`, or
  `Git-ready folder`, which additionally writes the tree to
  `<Git-ready Output Directory>/developer_snapshot` (absolute path, writable by the bench
  user). Files from the previous run that no longer exist are removed so Git sees deletions.
- **Include raw source** — embed full Client/Server Script source in the export.
- **LLM summaries** — when enabled, each artifact's structured metadata (not its raw
  source) is sent to the chosen provider. Leave off if that metadata must stay on-prem.
- Site config is exported with secrets redacted (password/key/token-like keys and
  credentials embedded in URLs), but review the first export before sharing it.

## Design principles

- **Readability first** — Markdown optimized for humans *and* AI.
- **Deterministic output** — same ERP state always produces the same structure.
- **Extensible** — collectors/exporters registry; add artifact types without touching the core.
- **Non-invasive** — read-only against ERP metadata.
- **Fast** — change detection identifies what changed between snapshots.

## Development

Pure-function logic (heuristic summarizer, change detection, search index) has unit tests
that run without a bench:

```bash
python -m pytest dev_vigilante/tests
```

## License

MIT — see [license.txt](license.txt).
