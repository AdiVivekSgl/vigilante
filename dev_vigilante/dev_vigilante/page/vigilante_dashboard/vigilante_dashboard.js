frappe.pages["vigilante-dashboard"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({
		parent: wrapper,
		title: __("Dev Vigilante Dashboard"),
		single_column: true,
	});

	const dashboard = new VigilanteDashboard(page);
	dashboard.refresh();
};

const esc = (value) => frappe.utils.escape_html(value == null ? "" : String(value));

class VigilanteDashboard {
	constructor(page) {
		this.page = page;
		this.body = $('<div class="vigilante-dashboard"></div>').appendTo(page.body);

		this.page.set_primary_action(
			__("Generate Snapshot"),
			() => this.generate(),
			"octicon octicon-sync"
		);
		this.page.add_menu_item(__("Snapshot History"), () =>
			frappe.set_route("List", "Vigilante Snapshot")
		);
		this.page.add_menu_item(__("Settings"), () =>
			frappe.set_route("Form", "Vigilante Settings", "Vigilante Settings")
		);

		frappe.realtime.off("dev_vigilante_snapshot");
		frappe.realtime.on("dev_vigilante_snapshot", (m) => this.on_snapshot_done(m));
	}

	generate() {
		frappe
			.call("dev_vigilante.api.generate_snapshot", { trigger_type: "Manual" })
			.then((r) => {
				if (r.message) {
					this.page.set_indicator(__("Generating..."), "orange");
					frappe.show_alert({
						message: __("Snapshot {0} queued — you'll be notified when it finishes.", [
							r.message.name,
						]),
						indicator: "blue",
					});
					this.refresh();
				}
			});
	}

	on_snapshot_done(m) {
		if (m.status === "Completed") {
			frappe.show_alert({
				message: __("Snapshot {0} generated ({1} artifacts, {2}).", [
					m.name,
					m.counts.total,
					m.export_size,
				]),
				indicator: "green",
			});
		} else {
			frappe.show_alert({
				message: __("Snapshot {0} failed — see its Error Log.", [m.name]),
				indicator: "red",
			});
		}
		this.refresh();
	}

	refresh() {
		frappe.call("dev_vigilante.api.get_dashboard_data").then((r) => {
			this.render(r.message || {});
		});
	}

	render(data) {
		const latest = data.latest;
		const cards = latest
			? [
					{ label: __("Total Artifacts"), value: latest.total_artifacts, color: "blue" },
					{ label: __("Custom Fields"), value: latest.custom_fields_count, color: "green" },
					{ label: __("Client Scripts"), value: latest.client_scripts_count, color: "purple" },
					{ label: __("Server Scripts"), value: latest.server_scripts_count, color: "orange" },
					{ label: __("Custom DocTypes"), value: latest.custom_doctypes_count, color: "cyan" },
			  ]
			: [];

		let html = "";

		if (!latest) {
			html += `<div class="text-muted" style="padding:2rem 0;">${__(
				"No snapshots yet. Click <b>Generate Snapshot</b> to create the first one."
			)}</div>`;
		} else {
			this.page.set_indicator(__("Last: {0}", [latest.name]), "green");
		}

		const running = (data.history || []).find((row) => row.status === "In Progress");
		if (running) {
			this.page.set_indicator(__("Generating {0}...", [running.name]), "orange");
		}

		if (latest) {
			html += '<div class="vg-cards">';
			for (const c of cards) {
				html += `
					<div class="vg-card vg-${c.color}">
						<div class="vg-value">${frappe.utils.escape_html(String(c.value ?? 0))}</div>
						<div class="vg-label">${c.label}</div>
					</div>`;
			}
			html += "</div>";

			html += `
				<div class="vg-meta">
					<span><b>${__("Last snapshot")}:</b> ${esc(latest.name)} · ${frappe.datetime.str_to_user(
				latest.generated_on
			)}</span>
					<span><b>${__("Export size")}:</b> ${esc(latest.export_size || "-")}</span>
					<span><b>${__("Duration")}:</b> ${latest.generation_duration || 0}s</span>
					<span><b>${__("Changes")}:</b>
						<span class="text-success">+${latest.changes_added || 0}</span>
						<span class="text-danger">-${latest.changes_removed || 0}</span>
						<span class="text-warning">~${latest.changes_modified || 0}</span>
					</span>
				</div>`;
		}

		// History table
		const history = data.history || [];
		if (history.length) {
			html += `<h5 style="margin-top:1.5rem;">${__("Recent Snapshots")}</h5>`;
			html += '<table class="table table-bordered vg-history"><thead><tr>';
			for (const h of [
				__("Snapshot"),
				__("Status"),
				__("Trigger"),
				__("Generated"),
				__("Artifacts"),
				__("Changes"),
			]) {
				html += `<th>${h}</th>`;
			}
			html += "</tr></thead><tbody>";
			for (const row of history) {
				html += `<tr>
					<td><a href="/app/vigilante-snapshot/${encodeURIComponent(row.name)}">${esc(row.name)}</a></td>
					<td>${esc(row.status)}</td>
					<td>${esc(row.trigger_type)}</td>
					<td>${frappe.datetime.str_to_user(row.generated_on) || ""}</td>
					<td>${row.total_artifacts || 0}</td>
					<td><span class="text-success">+${row.changes_added || 0}</span>
						<span class="text-danger">-${row.changes_removed || 0}</span>
						<span class="text-warning">~${row.changes_modified || 0}</span></td>
				</tr>`;
			}
			html += "</tbody></table>";
		}

		this.body.html(html);
		this.inject_styles();
	}

	inject_styles() {
		if (document.getElementById("vg-dashboard-styles")) return;
		const style = document.createElement("style");
		style.id = "vg-dashboard-styles";
		style.textContent = `
			.vigilante-dashboard { padding: 0.5rem 0; }
			.vg-cards { display: flex; flex-wrap: wrap; gap: 1rem; }
			.vg-card { flex: 1 1 150px; border-radius: 10px; padding: 1.25rem;
				background: var(--card-bg, #fff); border: 1px solid var(--border-color, #e2e8f0);
				box-shadow: var(--shadow-sm); text-align: center; }
			.vg-value { font-size: 2rem; font-weight: 700; line-height: 1; }
			.vg-label { margin-top: 0.5rem; color: var(--text-muted); font-size: 0.85rem; }
			.vg-blue .vg-value { color: #2490ef; }
			.vg-green .vg-value { color: #28a745; }
			.vg-purple .vg-value { color: #8b5cf6; }
			.vg-orange .vg-value { color: #f59e0b; }
			.vg-cyan .vg-value { color: #06b6d4; }
			.vg-meta { display: flex; flex-wrap: wrap; gap: 1.25rem; margin-top: 1.25rem;
				color: var(--text-muted); font-size: 0.9rem; }
			.vg-history td, .vg-history th { font-size: 0.85rem; }
		`;
		document.head.appendChild(style);
	}
}
