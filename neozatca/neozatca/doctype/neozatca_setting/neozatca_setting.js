// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// For license information, please see license.txt

function nz_ready(fn) {
	if (window.neozatca && typeof neozatca[fn] === "function") return true;
	frappe.msgprint({
		title: __("Reload needed"),
		message: __("NeoZatca was just updated. Reload this page (Ctrl+Shift+R, or Cmd+Shift+R on Mac) to load the new version."),
		indicator: "orange",
	});
	return false;
}

frappe.ui.form.on("NeoZatca Setting", {
	onload(frm) {
		if (frm.__nz_bound) return;
		frm.__nz_bound = true;
		frappe.realtime.on("neozatca_onboarding", (data) => {
			if (!data || data.setting !== frm.doc.name) return;
			frm.dashboard.show_progress(__("ZATCA Onboarding"), data.percentage || 0, data.message || "");
			if (data.complete) {
				frm.dashboard.hide_progress(__("ZATCA Onboarding"));
				frappe.show_alert({ message: data.message, indicator: data.indicator }, 7);
				frm.reload_doc();
			}
		});
	},

	refresh(frm) {
		frm.trigger("set_headline");
		if (frm.is_new()) return;

		const running = ["Queued", "In Progress"].includes(frm.doc.onboarding_status);
		if (!frm.doc.check_pcsid && !running) {
			frm.add_custom_button(
				frm.doc.check_csid ? __("Resume Onboarding") : __("Connect to ZATCA"),
				() => nz_ready("connect_device") && neozatca.connect_device(frm)
			).addClass("btn-primary");
		}
		const portal = ((window.neozatca && neozatca.PORTALS) || {production: {url: "https://fatoora.zatca.gov.sa/", label: __("Open Fatoora Portal")}})[frm.doc.api_endpoints || "production"];
		frm.add_custom_button(portal.label, () => window.open(portal.url, "_blank", "noopener"), __("ZATCA"));
		frm.add_custom_button(__("ZATCA Process Flow"), () => frappe.set_route("zatca-process-flow"), __("ZATCA"));
		frm.add_custom_button(__("ZATCA Control Center"), () => frappe.set_route("zatca-control-center"), __("ZATCA"));

		if (running) {
			frm.add_custom_button(__("Show Progress"), () => neozatca.track(frm.doc.name, { on_complete: () => frm.reload_doc() }));
		}
		if (frm.doc.check_pcsid) {
			frm.add_custom_button(__("Renew Production CSID"), () => {
				frappe.prompt(
					[{ fieldtype: "Data", fieldname: "otp", label: __("New OTP from Fatoora portal"), reqd: 1 }],
					(v) => frappe.call({
						method: "neozatca.zatca.onboarding.renew_production",
						args: { name: frm.doc.name, otp: v.otp },
						freeze: true,
						freeze_message: __("Renewing production CSID…"),
					}).then(() => { frappe.show_alert({ message: __("Production CSID renewed"), indicator: "green" }); frm.reload_doc(); }),
					__("Renew Production CSID"), __("Renew")
				);
			}, __("ZATCA"));
		}
		if (frappe.user.has_role("System Manager") && (frm.doc.check_csr || frm.doc.check_csid) && !running) {
			frm.add_custom_button(__("Reset Credentials"), () => {
				frappe.confirm(
					__("This erases the keys, certificates and tokens of <b>{0}</b>. A connected production device will stop clearing/reporting until onboarded again. Continue?", [frm.doc.name]),
					() => frappe.call({ method: "neozatca.zatca.onboarding.reset_onboarding", args: { name: frm.doc.name } })
						.then(() => frm.reload_doc())
				);
			}, __("ZATCA"));
		}
	},

	set_headline(frm) {
		const s = frm.doc.onboarding_status || "Not Started";
		let color = { Completed: "green", Failed: "red", "In Progress": "blue", Queued: "blue" }[s] || "orange";
		if (frm.doc.check_pcsid && frm.doc.api_endpoints !== "production") color = "orange";
		let msg = frm.doc.check_pcsid
			? __("Connected to ZATCA ({0}) since {1}", [frm.doc.api_endpoints, frappe.datetime.str_to_user(frm.doc.connected_on) || "—"])
			: __("Onboarding: {0}", [__(s)]);
		const env = (frappe.boot.zatca_environments || {})[frm.doc.api_endpoints || "production"];
		if (env) msg = `[${__(env.label)}] ` + msg;
		if (frm.doc.certificate_expiry) {
			const days = frappe.datetime.get_day_diff(frm.doc.certificate_expiry, frappe.datetime.get_today());
			if (days < 0) msg += " — " + __("certificate expired, renew now");
			else if (days <= 30) msg += " — " + __("certificate expires in {0} day(s)", [days]);
		}
		if (s === "Failed" && frm.doc.last_error) msg += ` — ${frappe.utils.escape_html(frm.doc.last_error).slice(0, 200)}`;
		frm.dashboard.set_headline_alert(msg, color);
	},
});
