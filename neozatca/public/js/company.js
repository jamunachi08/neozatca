function nz_ready(fn) {
	if (window.neozatca && typeof neozatca[fn] === "function") return true;
	frappe.msgprint({
		title: __("Reload needed"),
		message: __("NeoZatca was just updated. Reload this page (Ctrl+Shift+R, or Cmd+Shift+R on Mac) to load the new version."),
		indicator: "orange",
	});
	return false;
}


frappe.ui.form.on("Company", {
    refresh (frm) {
        frm.trigger("setup_query_filters");
        if (!frm.is_new() && frappe.user.has_role(["System Manager", "Accounts Manager"])) {
            frm.add_custom_button(__("ZATCA Process Flow"), () => {
                frappe.route_options = { company: frm.doc.name };
                frappe.set_route("zatca-process-flow");
            }, __("ZATCA"));
            frm.add_custom_button(__("ZATCA Quick Setup"), () => nz_ready("quick_setup") && neozatca.quick_setup(frm.doc.name), __("ZATCA"));
            frm.add_custom_button(__("ZATCA Devices"), () =>
                frappe.set_route("List", "NeoZatca Setting", { company: frm.doc.name }), __("ZATCA"));
        }
    },


    setup_query_filters(frm) {

        frm.set_query("commercial_register", () => {
            return {
                filters : {
                    is_main_commercial_register_for_the_company : 1
                }
            }
        })
    }
})
