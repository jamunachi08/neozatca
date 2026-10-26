import frappe

APP_ROLES = {"System Manager", "Accounts Manager", "Accounts User"}


def check_app_permission() -> bool:
	"""Show NeoZatca on the apps screen / desktop to accounting users only."""
	if frappe.session.user == "Administrator":
		return True
	return bool(APP_ROLES & set(frappe.get_roles()))
