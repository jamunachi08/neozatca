// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// NeoZatca — one-click ZATCA onboarding UI (shared by Company and NeoZatca Setting forms)

frappe.provide("neozatca");

neozatca.PORTALS = {
	production: { url: "https://fatoora.zatca.gov.sa/", label: __("Open Fatoora Portal"),
		hint: __("Fatoora portal → Onboard New Solution Unit/Device → copy the OTP. Valid for 1 hour.") },
	simulation: { url: "https://fatoora.zatca.gov.sa/", label: __("Open Fatoora (switch to Simulation)"),
		hint: __("Fatoora portal → “FATOORA Portal Simulation” (top right) → Onboard New Solution Unit/Device → copy the OTP.") },
	sandbox: { url: "https://sandbox.zatca.gov.sa/", label: __("Open Developer Portal"),
		hint: __("Developer sandbox: use the test OTP 123345.") },
};

neozatca.ENV_OPTIONS = [
	{ value: "production", label: __("Production (Live)") },
	{ value: "simulation", label: __("Simulation (Pre-production)") },
	{ value: "sandbox", label: __("Sandbox (Developer)") },
];

neozatca.otp_help = function (env) {
	const p = neozatca.PORTALS[env || "production"];
	return `${p.hint} <a href="${p.url}" target="_blank" rel="noopener">${p.label}</a>`;
};

neozatca.company_info = function (company) {
	return ((frappe.boot && frappe.boot.zatca_companies) || {})[company];
};

neozatca.phase_of = function (company) {
	const info = neozatca.company_info(company);
	return (info && info.phase) || (frappe.boot && frappe.boot.zatca_phase) || "Phase One";
};

neozatca.STAGES = [
	["credentials", __("CSR config, CSR, keys and PIH")],
	["compliance_csid", __("Compliance CSID, Basic Auth, request ID")],
	["compliance_checks", __("Compliance documents")],
	["production_csid", __("Production CSID (final auth)")],
];

// Progress dialog bound to one device; resolves when the run completes.
neozatca.track = function (setting, { on_complete } = {}) {
	const d = new frappe.ui.Dialog({
		title: __("Connecting to ZATCA"),
		fields: [{ fieldtype: "HTML", fieldname: "body" }],
		primary_action_label: __("Run in background"),
		primary_action: () => d.hide(),
	});
	const $b = d.fields_dict.body.$wrapper;
	$b.html(`
		<div class="nz-progress" style="margin-bottom:12px">
			<div class="progress" style="height:8px"><div class="progress-bar" style="width:2%"></div></div>
		</div>
		<ul class="list-unstyled nz-stages" style="margin:0">
			${neozatca.STAGES.map(([k, l]) => `<li data-stage="${k}" class="text-muted" style="padding:3px 0">○ ${l}</li>`).join("")}
		</ul>
		<div class="nz-msg small text-muted" style="margin-top:10px">${__("Queued…")}</div>`);
	d.show();

	let reached = -1;
	const handler = (data) => {
		if (!data || data.setting !== setting) return;
		$b.find(".progress-bar").css("width", `${Math.max(2, data.percentage || 0)}%`)
			.toggleClass("bg-danger", data.indicator === "red" && data.complete);
		$b.find(".nz-msg").text(data.message || "");
		const idx = neozatca.STAGES.findIndex(([k]) => k === data.stage);
		if (idx > reached) reached = idx;
		neozatca.STAGES.forEach(([k], i) => {
			const $li = $b.find(`[data-stage="${k}"]`);
			const label = $li.text().slice(2);
			if (i < reached || (data.complete && data.indicator === "green")) $li.removeClass("text-muted").html(`✔ ${label}`);
			else if (i === reached) $li.removeClass("text-muted").html(`◔ ${label}`);
		});
		if (data.complete) {
			frappe.realtime.off("neozatca_onboarding", handler);
			d.set_primary_action(__("Open Device"), () => {
				d.hide();
				frappe.set_route("Form", "NeoZatca Setting", setting);
			});
			on_complete && on_complete(data);
		}
	};
	frappe.realtime.on("neozatca_onboarding", handler);
	d.onhide = () => {};
	return d;
};

// Company -> VAT + OTP -> connected. Everything else is derived or generated.
neozatca.quick_setup = function (company, opts = {}) {
	frappe.call({
		method: "neozatca.zatca.onboarding.preview_quick_setup",
		args: { company },
	}).then(({ message: p }) => {
		const missing = (p.missing || []).map((m) => `<li>${frappe.utils.escape_html(m)}</li>`).join("");
		const summary = `
			<table class="table table-sm table-bordered small" style="margin-bottom:8px">
				<tr><th style="width:40%">${__("VAT Number")}</th><td>${p.vat_number || "—"}</td></tr>
				<tr><th>${__("Legal Name")}</th><td>${frappe.utils.escape_html(p.organization_name || "—")}</td></tr>
				<tr><th>${__("Commercial Registration")}</th><td>${p.cr_number || "—"}</td></tr>
				<tr><th>${__("Address")}</th><td>${p.address ? frappe.utils.escape_html(p.address) + " — " + (p.city || "") : "—"}</td></tr>
			</table>
			${(p.devices || []).length ? `<p class="small text-muted">${__("Existing devices")}: ${p.devices.map((x) =>
				frappe.utils.escape_html(`${x.organization_unit_name || x.commercial_register} (CR ${x.commercial_register}${x.check_pcsid ? ", " + x.api_endpoints : ""})`)).join(" · ")}.
				${__("Add another branch by choosing it below with its own CR number.")}</p>` : ""}
			${missing ? `<div class="alert alert-warning small"><b>${__("Complete before connecting:")}</b><ul style="margin:4px 0 0 16px">${missing}</ul></div>` : ""}`;

		const d = new frappe.ui.Dialog({
			title: __("ZATCA Quick Setup — {0}", [company]),
			size: "large",
			fields: [
				{ fieldtype: "HTML", fieldname: "summary", options: summary },
				{ fieldtype: "Section Break" },
				{ fieldtype: "Select", fieldname: "environment", label: __("Environment"), options: neozatca.ENV_OPTIONS, default: opts.environment || "production", reqd: 1,
					onchange: () => {
						const env = d.get_value("environment");
						d.set_df_property("otp", "description", neozatca.otp_help(env));
						if (env === "sandbox" && !d.get_value("otp")) d.set_value("otp", "123345");
					} },
				{ fieldtype: "Data", fieldname: "otp", label: __("ZATCA OTP"), reqd: 1, description: neozatca.otp_help(opts.environment || "production"),
					default: opts.environment === "sandbox" ? "123345" : undefined },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Data", fieldname: "cr_number", label: __("Commercial Registration No."), default: p.cr_number, reqd: 1 },
				{ fieldtype: "Link", fieldname: "branch", label: __("Branch (optional)"), options: "Branch",
					description: __("One device per branch, each with its own CR and address. Leave empty for the head office."),
					onchange: () => {
						const branch = d.get_value("branch");
						if (!branch) return;
						frappe.db.get_value("Branch", branch, "commercial_register").then(({ message }) => {
							if (message && message.commercial_register) d.set_value("cr_number", message.commercial_register);
							else d.set_value("cr_number", "");
						});
					} },
				{ fieldtype: "Link", fieldname: "address", label: __("Branch Address (optional)"), options: "Address",
					depends_on: "eval:doc.branch",
					description: __("National address of this branch. Leave empty to use the company address.") },
				{ fieldtype: "Section Break", label: __("Device"), collapsible: 1 },
				{ fieldtype: "Select", fieldname: "invoice_type", label: __("Invoices issued"), default: "1100",
					options: [
						{ value: "1100", label: __("Standard (B2B) + Simplified (B2C)") },
						{ value: "1000", label: __("Standard (B2B) only") },
						{ value: "0100", label: __("Simplified (B2C) only") },
					] },
				{ fieldtype: "Column Break" },
				{ fieldtype: "Data", fieldname: "industry", label: __("Industry / Business Category"), default: p.industry },
				{ fieldtype: "Data", fieldname: "group_tin", label: __("Member TIN (10 digits)"), depends_on: `eval:${p.is_vat_group ? 1 : 0}`,
					mandatory_depends_on: `eval:${p.is_vat_group ? 1 : 0}`, description: __("VAT group member: ZATCA requires the 10-digit TIN as Organization Unit.") },
			],
			primary_action_label: __("Connect to ZATCA"),
			primary_action: (v) => {
				d.get_primary_btn().prop("disabled", true);
				frappe.call({
					method: "neozatca.zatca.onboarding.quick_setup",
					args: { company, ...v },
					freeze: true,
					freeze_message: __("Preparing device…"),
				}).then(({ message }) => {
					d.hide();
					neozatca.track(message.setting);
				}).always(() => d.get_primary_btn().prop("disabled", false));
			},
		});
		d.show();
	});
};

// From a device record: start or resume.
neozatca.connect_device = function (frm) {
	const issued = !!frm.doc.check_csid;
	const d = new frappe.ui.Dialog({
		title: issued ? __("Resume ZATCA Onboarding") : __("Connect to ZATCA"),
		fields: [
			{ fieldtype: "Select", fieldname: "environment", label: __("Environment"), options: neozatca.ENV_OPTIONS,
				default: frm.doc.api_endpoints || "production", read_only: issued ? 1 : 0,
				onchange: () => {
					const env = d.get_value("environment");
					d.set_df_property("otp", "description", neozatca.otp_help(env));
					if (env === "sandbox" && !d.get_value("otp")) d.set_value("otp", "123345");
				} },
			{ fieldtype: "Data", fieldname: "otp", label: __("ZATCA OTP"), reqd: issued ? 0 : 1, hidden: issued ? 1 : 0,
				description: neozatca.otp_help(frm.doc.api_endpoints || "production") },
			{ fieldtype: "HTML", options: issued
				? `<p class="small text-muted">${__("The compliance CSID is already issued. Remaining steps will run without a new OTP.")}</p>`
				: `<p class="small text-muted">${__("CSR, keys, PIH, compliance CSID, compliance documents and the production CSID are generated automatically.")}</p>` },
		],
		primary_action_label: issued ? __("Resume") : __("Connect"),
		primary_action: (v) => {
			frappe.call({
				method: "neozatca.zatca.onboarding.start_onboarding",
				args: { name: frm.doc.name, otp: v.otp, environment: v.environment },
			}).then(() => {
				d.hide();
				neozatca.track(frm.doc.name, { on_complete: () => frm.reload_doc() });
				frm.reload_doc();
			});
		},
	});
	d.show();
};


// ---------------------------------------------------------------------------------------------
// Saudi National Address lookup — shared by the Address form and the Process Flow.
// on_pick(result) receives the normalised address chosen by the user.
neozatca.national_address_dialog = function ({ title, on_pick, defaults = {} } = {}) {
	const esc = frappe.utils.escape_html;
	const d = new frappe.ui.Dialog({
		title: title || __("Fetch from National Address"),
		size: "large",
		fields: [
			{ fieldtype: "Select", fieldname: "mode", label: __("Find by"), reqd: 1, default: defaults.short_address ? "short_address" : "short_address",
				options: [
					{ value: "short_address", label: __("Short address (e.g. RRRD2929)") },
					{ value: "numbers", label: __("Building no. + postal code (+ secondary no.)") },
					{ value: "free_text", label: __("Free text") },
					{ value: "geocode", label: __("Map location (latitude / longitude)") },
				] },
			{ fieldtype: "Data", fieldname: "short_address", label: __("Short Address"), default: defaults.short_address,
				depends_on: "eval:doc.mode=='short_address'", description: __("4 letters + 4 digits, printed on the national address certificate.") },
			{ fieldtype: "Data", fieldname: "building_no", label: __("Building No"), default: defaults.building_no, depends_on: "eval:doc.mode=='numbers'" },
			{ fieldtype: "Data", fieldname: "pincode", label: __("Postal Code"), default: defaults.pincode, depends_on: "eval:doc.mode=='numbers'" },
			{ fieldtype: "Data", fieldname: "additional_no", label: __("Secondary No (optional)"), default: defaults.address_line2, depends_on: "eval:doc.mode=='numbers'" },
			{ fieldtype: "Data", fieldname: "text", label: __("Search"), depends_on: "eval:doc.mode=='free_text'", description: __("For example: 8228 12643") },
			{ fieldtype: "Float", fieldname: "latitude", label: __("Latitude"), precision: 7, depends_on: "eval:doc.mode=='geocode'" },
			{ fieldtype: "Float", fieldname: "longitude", label: __("Longitude"), precision: 7, depends_on: "eval:doc.mode=='geocode'" },
			{ fieldtype: "Button", fieldname: "here", label: __("Use my current location"), depends_on: "eval:doc.mode=='geocode'",
				click: () => {
					if (!navigator.geolocation) return frappe.msgprint(__("This browser can't share its location."));
					navigator.geolocation.getCurrentPosition(
						(pos) => { d.set_value("latitude", pos.coords.latitude); d.set_value("longitude", pos.coords.longitude); },
						() => frappe.msgprint(__("Location permission was denied.")));
				} },
			{ fieldtype: "HTML", fieldname: "results" },
		],
		primary_action_label: __("Search"),
		primary_action: (v) => {
			const $r = d.fields_dict.results.$wrapper.html(`<p class="text-muted">${__("Searching…")}</p>`);
			frappe.call({ method: "neozatca.zatca.national_address.lookup", args: v })
				.then(({ message }) => {
					const rows = message.results || [];
					if (!rows.length) return $r.html(`<p class="text-muted">${__("No national address found. Check the value and try again.")}</p>`);
					$r.html(`<div class="nz-na-results">${rows.map((a, i) => `
						<button class="nz-na-row" data-i="${i}">
							<b>${esc([a.building_no, a.address_line1].filter(Boolean).join(" "))}${a.district ? ", " + esc(a.district) : ""}</b>
							<span>${esc([a.city, a.pincode].filter(Boolean).join(" "))}${a.address_line2 ? " – " + esc(a.address_line2) : ""}${a.short_address ? ` <em>${esc(a.short_address)}</em>` : ""}</span>
							${a.street_alt || a.district_alt ? `<span dir="auto" class="text-muted">${esc([a.street_alt, a.district_alt, a.city_alt].filter(Boolean).join("، "))}</span>` : ""}
						</button>`).join("")}</div>
						<p class="text-muted small">${rows.length > 1 ? __("Pick the right one.") : __("Click to use this address.")}</p>`);
					$r.find(".nz-na-row").on("click", (e) => { d.hide(); on_pick(rows[$(e.currentTarget).data("i")]); });
					if (rows.length === 1) $r.find(".nz-na-row").first().trigger("focus");
				})
				.catch(() => $r.html(""));
		},
	});
	if (!document.getElementById("nz-na-style")) {
		$(`<style id="nz-na-style">
			.nz-na-results { display:grid; gap:8px; margin-top:6px; }
			.nz-na-row { display:flex; flex-direction:column; gap:2px; text-align:left; padding:10px 12px; border-radius:10px;
				border:1px solid var(--border-color); border-left:5px solid #2563EB; background: var(--card-bg, var(--bg-color)); color: var(--text-color); }
			.nz-na-row:hover, .nz-na-row:focus-visible { background: var(--fg-hover-color); outline: none; border-color:#2563EB; }
			.nz-na-row em { font-style: normal; font-weight:600; color:#2563EB; margin-left:6px; }
		</style>`).appendTo("head");
	}
	d.show();
	return d;
};
