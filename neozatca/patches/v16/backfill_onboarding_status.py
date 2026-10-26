import frappe

from neozatca.zatca.csr import INITIAL_PIH, certificate_expiry


def execute():
	"""Devices onboarded before one-click onboarding: mark status, seed the PIH, record certificate expiry."""
	if not frappe.db.has_column("NeoZatca Setting", "onboarding_status"):
		return
	for row in frappe.get_all("NeoZatca Setting", fields=["name", "check_pcsid", "check_csr", "onboarding_status", "pih", "certificate", "certificate_expiry"]):
		values = {}
		if not row.onboarding_status or row.onboarding_status == "Not Started":
			if row.check_pcsid:
				values["onboarding_status"] = "Completed"
			elif row.check_csr:
				values["onboarding_status"] = "Failed"
		if not row.pih and row.check_csr:
			values["pih"] = INITIAL_PIH
		if row.check_pcsid and row.certificate and not row.certificate_expiry:
			values["certificate_expiry"] = certificate_expiry(row.certificate)
		if values:
			frappe.db.set_value("NeoZatca Setting", row.name, values, update_modified=False)
