import frappe


def add_neozatca_boot_info(boot_info):
    from neozatca.zatca.links import ENVIRONMENTS
    from neozatca.zatca.phase import boot_company_map, get_site_phase

    boot_info["zatca_phase"] = get_site_phase()
    boot_info["zatca_environments"] = ENVIRONMENTS
    try:
        boot_info["zatca_companies"] = boot_company_map()
    except Exception:
        # Never break desk boot over a ZATCA lookup (e.g. mid-migration).
        frappe.log_error(title="NeoZatca boot info")
        boot_info["zatca_companies"] = {}
