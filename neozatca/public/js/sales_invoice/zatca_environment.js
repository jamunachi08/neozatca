// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// Tells the user, on the invoice itself, which ZATCA phase and environment apply to its company.

frappe.ui.form.on("Sales Invoice", {
	refresh(frm) {
		if (!frm.doc.company) return;
		const info = neozatca.company_info(frm.doc.company);
		const phase = neozatca.phase_of(frm.doc.company);
		if (phase !== "Phase Two") return;

		if (!info || !info.environment) {
			frm.dashboard.set_headline_alert(
				`${__("ZATCA Phase Two: no device is connected for {0}. Invoices cannot be cleared or reported.", [frappe.utils.escape_html(frm.doc.company)])}
				 <a href="/app/zatca-control-center">${__("Open ZATCA Control Center")}</a>`, "red");
			return;
		}
		if (info.environment !== "production") {
			const env = (frappe.boot.zatca_environments || {})[info.environment] || {};
			frm.dashboard.set_headline_alert(
				__("ZATCA {0}: this company is connected to a test environment. Invoices sent from here are not legally reported.", [__(env.label || info.environment)]),
				"orange");
		}
	},
	company(frm) {
		frm.trigger("refresh");
	},
});
