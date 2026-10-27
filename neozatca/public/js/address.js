// Copyright (c) 2026, Neotec Integrated Solutions and contributors
// Address: fill from the Saudi National Address register and verify it.

frappe.ui.form.on("Address", {
	refresh(frm) {
		if (frm.doc.country && frm.doc.country !== "Saudi Arabia") return;
		frm.add_custom_button(__("Fetch from National Address"), () => {
			neozatca.national_address_dialog({
				defaults: frm.doc,
				on_pick: (a) => {
					const map = ["short_address", "building_no", "address_line1", "district", "city", "pincode", "address_line2", "state", "country"];
					map.forEach((f) => { if (a[f] && frm.fields_dict[f]) frm.set_value(f, a[f]); });
					if (!frm.doc.address_name_in_arabic && frm.fields_dict.address_name_in_arabic && (a.street_alt || a.district_alt)) {
						frm.set_value("address_name_in_arabic", [a.building_no, a.street_alt, a.district_alt].filter(Boolean).join(" "));
					}
					frappe.show_alert({ message: __("Address filled from the National Address register"), indicator: "green" });
				},
			});
		}, __("National Address"));

		if (!frm.is_new() && frm.doc.building_no && frm.doc.pincode && frm.doc.address_line2) {
			frm.add_custom_button(__("Verify"), () => {
				frappe.call({ method: "neozatca.zatca.national_address.verify_address", args: { address: frm.doc.name }, freeze: true })
					.then(({ message }) => frappe.show_alert({
						message: message.verified ? __("Matches the National Address register") : message.reason,
						indicator: message.verified ? "green" : "orange" }, 7));
			}, __("National Address"));
		}
	},

	// Typing a complete short address on an empty address fetches it straight away.
	short_address(frm) {
		const code = (frm.doc.short_address || "").replace(/\s+/g, "").toUpperCase();
		if (!/^[A-Z]{4}\d{4}$/.test(code) || (frm.doc.building_no && frm.doc.pincode)) return;
		frappe.call({ method: "neozatca.zatca.national_address.lookup", args: { mode: "short_address", short_address: code } })
			.then(({ message }) => {
				const a = (message.results || [])[0];
				if (!a) return;
				["building_no", "address_line1", "district", "city", "pincode", "address_line2", "state"].forEach((f) => {
					if (a[f] && frm.fields_dict[f] && !frm.doc[f]) frm.set_value(f, a[f]);
				});
				frappe.show_alert({ message: __("Filled from short address {0}", [code]), indicator: "green" });
			});
	},
});
