# Dev Vigilante

**Developer Intelligence & Context Snapshot (DISC) for ERPNext / Frappe.**

Dev Vigilante inventories, documents, versions, and exports every customization made to
an ERPNext/Frappe instance. It produces a structured, human-readable, AI-optimized
snapshot that can be committed to Git or handed to an AI coding assistant to provide
complete project context — without anyone having to manually explore the ERP.

> **Non-invasive by design.** The app is strictly *read-only* with respect to ERP
> metadata. It only writes its own DocType rows and the export files it produces.

---

## What it captures (MVP core)

| Collector        | What it documents                                                        |
|------------------|--------------------------------------------------------------------------|
| System Info      | Frappe/ERPNext/Python/Node/MariaDB/Bench versions, installed & custom apps, modules, sanitized site config & system settings |
| Custom Fields    | Every Custom Field with DocType, label, type, options, depends-on, flags, insert-after, fetch-from, default, description |
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
