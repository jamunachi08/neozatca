// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// ZATCA Control Center — phase, environment and health of every company and device on one screen.

frappe.pages["zatca-control-center"].on_page_load = function (wrapper) {
	const page = frappe.ui.make_app_page({ parent: wrapper, title: __("ZATCA Control Center"), single_column: true });
	const cc = new ZatcaControlCenter(page);
	wrapper.zatca_cc = cc;
	cc.refresh();
};

frappe.pages["zatca-control-center"].on_page_show = function (wrapper) {
	wrapper.zatca_cc && wrapper.zatca_cc.refresh();
};

class ZatcaControlCenter {
	constructor(page) {
		this.page = page;
		this.$body = $(`<div class="nzcc"></div>`).appendTo(page.main);
		this.inject_style();
		page.set_secondary_action(__("Refresh"), () => this.refresh(), "refresh");
		page.add_inner_button(__("Fatoora Portal"), () => window.open("https://fatoora.zatca.gov.sa/", "_blank", "noopener"));
		page.add_inner_button(__("Developer Portal (Sandbox)"), () => window.open("https://sandbox.zatca.gov.sa/", "_blank", "noopener"));
		page.add_inner_button(__("All Devices"), () => frappe.set_route("List", "NeoZatca Setting"));
		page.add_inner_button(__("Submission Logs"), () => frappe.set_route("List", "NeoZatca Logs"));
		frappe.realtime.on("neozatca_onboarding", (d) => d && d.complete && this.refresh());
	}

	refresh() {
		frappe.call("neozatca.zatca.control_center.get_overview").then(({ message }) => {
			this.data = message;
			this.render();
		});
	}

	render() {
		const d = this.data;
		const esc = frappe.utils.escape_html;
		const companies = d.companies.length
			? d.companies.map((c) => this.company_html(c)).join("")
			: `<div class="nzcc-empty">${__("No Saudi companies found. Set the Company country to Saudi Arabia and its Tax ID to the VAT number.")}</div>`;

		const links = d.links.map((l) =>
			`<a class="nzcc-link" href="${esc(l.url)}" target="_blank" rel="noopener" title="${esc(l.otp_hint || "")}">
				<span>${esc(__(l.label))}</span><span class="nzcc-link-ar" dir="rtl">${esc(l.label_ar || "")}</span>
			</a>`).join("");

		this.$body.html(`
			<div class="nzcc-summary">
				<div>
					<div class="nzcc-site">${__("Site default phase")}: <b>${__(d.site_phase)}</b></div>
					<div class="text-muted small">${__("Each company can override it. Phase One adds the QR at submit; Phase Two clears (B2B) or reports (B2C) every invoice with ZATCA.")}</div>
				</div>
				<div class="nzcc-legend">
					${Object.entries(d.environments).map(([k, e]) => `<span class="nzcc-env-chip nzcc-${e.color}">${esc(__(e.label))}</span>`).join("")}
				</div>
			</div>
			${companies}
			<section class="nzcc-links-wrap">
				<h5>${__("ZATCA links")}</h5>
				<div class="nzcc-links">${links}</div>
			</section>`);
		this.bind();
	}

	company_html(c) {
		const esc = frappe.utils.escape_html;
		const phase_ctl = this.data.is_system_manager
			? `<div class="nzcc-seg" data-company="${esc(c.company)}">
				${[["", __("Site default")], ["Phase One", __("Phase One")], ["Phase Two", __("Phase Two")]].map(([v, l]) =>
					`<button class="${(c.phase_override || "") === v ? "active" : ""}" data-phase="${v}">${l}</button>`).join("")}
			   </div>`
			: `<span class="nzcc-phase">${__(c.phase)}</span>`;

		const advice = c.advice.map(([color, t]) => `<div class="nzcc-tip nzcc-tip-${color}">${esc(t)}</div>`).join("");
		const missing = c.missing.length
			? `<details class="nzcc-missing"><summary>${__("Missing company data ({0})", [c.missing.length])}</summary>
				<ul>${c.missing.map((m) => `<li>${esc(m)}</li>`).join("")}</ul></details>` : "";

		const devices = c.devices.length
			? c.devices.map((dv) => this.device_html(c, dv)).join("")
			: `<div class="nzcc-empty small">${__("No ZATCA device for this company.")}</div>`;

		return `
		<section class="nzcc-company">
			<header>
				<div>
					<h4><a href="/app/company/${encodeURIComponent(c.company)}">${esc(c.company)}</a></h4>
					<div class="text-muted small">${__("VAT")} ${esc(c.vat_number || "—")} · ${__("CR")} ${esc(c.cr_number || "—")} · ${__("Effective phase")}: <b>${__(c.phase)}</b></div>
				</div>
				<div class="nzcc-head-actions">
					${phase_ctl}
					${this.data.can_manage ? `<button class="btn btn-sm btn-primary nzcc-quick" data-company="${esc(c.company)}">${c.devices.length ? __("Add branch device") : __("ZATCA Quick Setup")}</button>` : ""}
				</div>
			</header>
			${advice}${missing}
			<div class="nzcc-devices">${devices}</div>
		</section>`;
	}

	device_html(c, dv) {
		const esc = frappe.utils.escape_html;
		const status = dv.check_pcsid ? __("Connected") : __(dv.onboarding_status || "Not Started");
		const expiry = dv.days_left === null || dv.days_left === undefined ? "—"
			: dv.days_left < 0 ? `<span class="text-danger">${__("Expired")}</span>`
			: `${frappe.datetime.str_to_user(dv.certificate_expiry)} <span class="text-muted">(${__("{0} days", [dv.days_left])})</span>`;
		const tips = dv.advice.map(([color, t]) => `<div class="nzcc-tip nzcc-tip-${color}">${esc(t)}</div>`).join("");
		const can = this.data.can_manage;
		const connect_label = dv.check_csid ? __("Resume") : __("Connect");
		const otp_btn = !dv.check_pcsid || (dv.days_left !== null && dv.days_left <= 30)
			? `<a class="btn btn-xs btn-default" href="${esc(dv.portal.url)}" target="_blank" rel="noopener" title="${esc(dv.portal.otp_hint || "")}">${__("Get OTP")}</a>` : "";

		return `
		<div class="nzcc-device nzcc-rail-${dv.environment_color}">
			<div class="nzcc-rail"><span>${esc(__(dv.environment_label || ""))}</span></div>
			<div class="nzcc-device-body">
				<div class="nzcc-device-top">
					<a href="/app/neozatca-setting/${encodeURIComponent(dv.name)}"><b>${esc(dv.organization_unit_name || dv.commercial_register)}</b></a>
					<span class="indicator-pill ${dv.check_pcsid ? "green" : dv.onboarding_status === "Failed" ? "red" : "orange"}">${status}</span>
				</div>
				<div class="nzcc-metrics">
					<div><label>${__("Commercial Register")}</label><span>${esc(dv.commercial_register)}</span></div>
					<div><label>${__("Certificate expiry")}</label><span>${expiry}</span></div>
					<div><label>${__("Last 7 days")}</label><span>${__("{0} sent, {1} rejected", [dv.sent_7d, dv.failed_7d])}</span></div>
					<div><label>${__("Last accepted")}</label><span>${dv.last_success ? frappe.datetime.comment_when(dv.last_success) : "—"}</span></div>
				</div>
				${tips}
				<div class="nzcc-actions">
					${otp_btn}
					${can && !dv.check_pcsid && !["Queued", "In Progress"].includes(dv.onboarding_status)
						? `<button class="btn btn-xs btn-primary nzcc-connect" data-name="${esc(dv.name)}">${connect_label}</button>` : ""}
					${["Queued", "In Progress"].includes(dv.onboarding_status)
						? `<button class="btn btn-xs btn-default nzcc-track" data-name="${esc(dv.name)}">${__("Show progress")}</button>` : ""}
					<a class="btn btn-xs btn-default" href="/app/neozatca-logs?commercial_register=${encodeURIComponent(dv.commercial_register)}">${__("Logs")}</a>
				</div>
			</div>
		</div>`;
	}

	bind() {
		const me = this;
		this.$body.find(".nzcc-quick").on("click", function () { neozatca.quick_setup($(this).data("company")); });
		this.$body.find(".nzcc-track").on("click", function () { neozatca.track($(this).data("name"), { on_complete: () => me.refresh() }); });
		this.$body.find(".nzcc-connect").on("click", function () {
			frappe.model.with_doc("NeoZatca Setting", $(this).data("name")).then((doc) => {
				neozatca.connect_device({ doc, reload_doc: () => me.refresh() });
			});
		});
		this.$body.find(".nzcc-seg button").on("click", function () {
			const company = $(this).closest(".nzcc-seg").data("company");
			const phase = $(this).data("phase");
			frappe.confirm(__("Set the ZATCA phase of {0} to {1}?", [company, phase || __("Site default")]), () =>
				frappe.call({ method: "neozatca.zatca.control_center.set_company_phase", args: { company, phase } })
					.then(() => { frappe.boot.zatca_companies = frappe.boot.zatca_companies || {}; me.refresh(); }));
		});
	}

	inject_style() {
		if (document.getElementById("nzcc-style")) return;
		$(`<style id="nzcc-style">
			.nzcc { max-width: 1100px; margin: 0 auto; padding-bottom: 32px; }
			.nzcc-summary { display:flex; justify-content:space-between; gap:16px; flex-wrap:wrap; align-items:flex-start;
				padding:14px 0 18px; border-bottom:1px solid var(--border-color); margin-bottom:18px; }
			.nzcc-site { font-size: var(--text-lg); }
			.nzcc-legend { display:flex; gap:6px; flex-wrap:wrap; }
			.nzcc-env-chip { font-size: var(--text-xs); padding:2px 8px; border-radius:4px; border-left:4px solid; background: var(--subtle-fg); }
			.nzcc-green { border-color: var(--green-500); } .nzcc-orange { border-color: var(--orange-500); } .nzcc-red { border-color: var(--red-500); }
			.nzcc-company { margin-bottom:28px; }
			.nzcc-company > header { display:flex; justify-content:space-between; gap:12px; flex-wrap:wrap; align-items:flex-end; margin-bottom:8px; }
			.nzcc-company h4 { margin:0 0 2px; }
			.nzcc-head-actions { display:flex; gap:8px; align-items:center; flex-wrap:wrap; }
			.nzcc-seg { display:inline-flex; border:1px solid var(--border-color); border-radius:6px; overflow:hidden; }
			.nzcc-seg button { border:0; background:transparent; padding:4px 10px; font-size: var(--text-sm); color: var(--text-muted); }
			.nzcc-seg button + button { border-left:1px solid var(--border-color); }
			.nzcc-seg button.active { background: var(--fg-hover-color); color: var(--text-color); font-weight:600; }
			.nzcc-seg button:focus-visible, .nzcc-link:focus-visible { outline:2px solid var(--primary); outline-offset:1px; }
			.nzcc-tip { font-size: var(--text-sm); padding:4px 0 4px 10px; border-left:3px solid; margin:4px 0; }
			.nzcc-tip-red { border-color: var(--red-500); } .nzcc-tip-orange { border-color: var(--orange-500); } .nzcc-tip-blue { border-color: var(--blue-500); }
			.nzcc-missing { font-size: var(--text-sm); margin:4px 0 8px; } .nzcc-missing ul { margin:4px 0 0 18px; }
			.nzcc-devices { display:grid; gap:10px; margin-top:8px; }
			.nzcc-device { display:flex; border:1px solid var(--border-color); border-radius:8px; overflow:hidden; background: var(--card-bg); }
			.nzcc-rail { width:34px; flex:none; display:flex; align-items:center; justify-content:center; }
			.nzcc-rail span { writing-mode: vertical-rl; transform: rotate(180deg); font-size: var(--text-xs); font-weight:600; color:#fff; white-space:nowrap; }
			.nzcc-rail-green .nzcc-rail { background: var(--green-600); }
			.nzcc-rail-orange .nzcc-rail { background: var(--orange-600); }
			.nzcc-rail-red .nzcc-rail { background: var(--red-600); }
			.nzcc-device-body { flex:1; padding:10px 14px; min-width:0; }
			.nzcc-device-top { display:flex; justify-content:space-between; gap:8px; align-items:center; }
			.nzcc-metrics { display:grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap:6px 16px; margin:8px 0 4px; }
			.nzcc-metrics label { display:block; font-size: var(--text-xs); color: var(--text-muted); margin:0; }
			.nzcc-actions { display:flex; gap:6px; flex-wrap:wrap; margin-top:8px; }
			.nzcc-empty { color: var(--text-muted); padding:12px 0; }
			.nzcc-links-wrap { border-top:1px solid var(--border-color); padding-top:16px; }
			.nzcc-links { display:grid; grid-template-columns: repeat(auto-fit, minmax(240px, 1fr)); gap:8px; }
			.nzcc-link { display:flex; justify-content:space-between; gap:8px; padding:8px 10px; border:1px solid var(--border-color);
				border-radius:6px; color: var(--text-color); text-decoration:none; font-size: var(--text-sm); }
			.nzcc-link:hover { background: var(--fg-hover-color); text-decoration:none; }
			.nzcc-link-ar { color: var(--text-muted); }
		</style>`).appendTo("head");
	}
}
