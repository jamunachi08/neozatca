# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Daily certificate watch: warn before a production CSID expires."""

import frappe
from frappe import _
from frappe.utils import date_diff, getdate, today

from neozatca.zatca.csr import certificate_expiry

THRESHOLDS = (30, 14, 7, 3, 1, 0)


def check_certificates():
	for row in frappe.get_all(
		"NeoZatca Setting",
		filters={"check_pcsid": 1},
		fields=["name", "company", "api_endpoints", "certificate", "certificate_expiry"],
	):
		expiry = row.certificate_expiry
		if not expiry and row.certificate:
			expiry = certificate_expiry(row.certificate)
			if expiry:
				frappe.db.set_value("NeoZatca Setting", row.name, "certificate_expiry", expiry, update_modified=False)
		if not expiry:
			continue
		days = date_diff(getdate(expiry), getdate(today()))
		if days in THRESHOLDS or days < 0:
			_notify(row, days)


def _notify(row, days):
	if days < 0:
		subject = _("ZATCA certificate EXPIRED for {0} — invoices will be rejected").format(row.name)
	else:
		subject = _("ZATCA certificate for {0} expires in {1} day(s) — renew with a new OTP").format(row.name, days)
	users = {u for role in ("System Manager", "Accounts Manager") for u in frappe.get_all(
		"Has Role", filters={"role": role, "parenttype": "User"}, pluck="parent")}
	users = [u for u in users if u not in ("Administrator", "Guest") and frappe.db.get_value("User", u, "enabled")]
	for user in users:
		frappe.get_doc({
			"doctype": "Notification Log",
			"for_user": user,
			"type": "Alert",
			"document_type": "NeoZatca Setting",
			"document_name": row.name,
			"subject": subject,
		}).insert(ignore_permissions=True)
