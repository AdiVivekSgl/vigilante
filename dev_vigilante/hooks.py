app_name = "dev_vigilante"
app_title = "Dev Vigilante"
app_publisher = "Frontec"
app_description = (
    "Developer Intelligence & Context Snapshot (DISC): inventory, document, version and "
    "export every customization made to an ERPNext/Frappe instance."
)
app_email = "dev@frontec.example"
app_license = "MIT"

# ------------------------------------------------------------------------------
# Scheduler
# ------------------------------------------------------------------------------
# The weekly job runs a snapshot only if Vigilante Settings enables scheduling.
# The entry point itself is a no-op when scheduling is disabled, so it is safe to
# register unconditionally.
scheduler_events = {
    "weekly": [
        "dev_vigilante.api.run_weekly_snapshot",
    ],
    "monthly": [
        "dev_vigilante.api.run_monthly_snapshot",
    ],
}

# ------------------------------------------------------------------------------
# Fixtures
# ------------------------------------------------------------------------------
# Export the dashboard page/workspace-like artifacts so a fresh install has them.
# (The Single settings DocType is created on migrate; no fixture needed.)
fixtures = []
