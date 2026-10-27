# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""One company, many branches: each branch has its own Commercial Register (CR), address and
ZATCA device; all of them share the company's VAT registration.

ZATCA registers VAT per taxpayer (legal entity), not per branch. A different VAT number means a
different taxpayer, which in ERPNext is a different Company. The one exception is a VAT group:
members share the group VAT number and are told apart by their own 10-digit TIN, which goes in
the device's Organization Unit.
"""

import frappe
from frappe import _

SETTING = "NeoZatca Setting"


def _cr_belongs(cr, company):
	return bool(cr) and frappe.db.get_value("Commercial Register", cr, "company") == company and not frappe.db.get_value(
		"Commercial Register", cr, "disabled")


@frappe.whitelist()
def default_commercial_register(company: str, branch: str | None = None) -> str | None:
	"""Branch's CR → the user's default CR → the company's default/main CR → its only CR."""
	if not company:
		return None
	if branch:
		cr = None
		if frappe.get_meta("Branch").has_field("commercial_register"):
			cr = frappe.db.get_value("Branch", branch, "commercial_register")
		cr = cr or frappe.db.get_value("Commercial Register", {"company": company, "branch": branch, "disabled": 0}, "name")
		if _cr_belongs(cr, company):
			return cr
	user_cr = frappe.defaults.get_user_default("Commercial Register")
	if _cr_belongs(user_cr, company):
		return user_cr
	for filters in ({"is_default": 1}, {"is_main_commercial_register_for_the_company": 1}, {}):
		rows = frappe.get_all("Commercial Register", filters={"company": company, "disabled": 0, **filters}, pluck="name", limit=2)
		if len(rows) == 1 or (rows and filters):
			return rows[0]
	return None


def ensure_invoice_commercial_register(doc, method=None):
	"""Sales Invoice before_validate: fill the branch CR when empty; refuse another company's CR."""
	if not doc.get("company"):
		return
	if not doc.get("commercial_register"):
		cr = default_commercial_register(doc.company, doc.get("branch"))
		if cr:
			doc.commercial_register = cr
		return
	owner = frappe.db.get_value("Commercial Register", doc.commercial_register, "company")
	if owner and owner != doc.company:
		frappe.throw(_("Commercial Register {0} belongs to {1}, not {2}.").format(doc.commercial_register, owner, doc.company))


def seller_identity(company: str, commercial_register: str | None = None) -> frappe._dict:
	"""Who the seller is on a given invoice: VAT, legal name, CR number and address of that branch."""
	c = frappe.db.get_value("Company", company, ["tax_id", "company_name"], as_dict=True) or frappe._dict()
	arabic = frappe.db.get_value("Company", company, "company_name_in_arabic") if frappe.get_meta("Company").has_field("company_name_in_arabic") else None
	ident = frappe._dict(vat=c.tax_id, legal_name=arabic or c.company_name, cr_number=None, address=None, setting=None)
	if commercial_register:
		cr = frappe.db.get_value("Commercial Register", commercial_register, ["commercial_register", "address"], as_dict=True)
		if cr:
			ident.cr_number, ident.address = cr.commercial_register, cr.address
		dev = frappe.db.get_value(SETTING, {"commercial_register": commercial_register},
			["name", "organization_identifier", "organization_name"], as_dict=True)
		if dev:
			ident.setting = dev.name
			ident.vat = dev.organization_identifier or ident.vat
			ident.legal_name = dev.organization_name or ident.legal_name
	return ident


def validate_device_vat(setting_doc) -> None:
	"""A device must carry its company's VAT number (group VAT for VAT-group members)."""
	company_vat = (frappe.db.get_value("Company", setting_doc.company, "tax_id") or "").strip()
	device_vat = (setting_doc.organization_identifier or "").strip()
	if company_vat and device_vat and company_vat != device_vat:
		frappe.throw(
			_("VAT {0} on this device differs from {1}'s VAT {2}. Branches of one company share its VAT "
			  "registration and differ only by Commercial Register. A different VAT number is a different "
			  "taxpayer: create it as a separate Company. VAT-group members keep the group VAT here and "
			  "put their own 10-digit TIN in Organization Unit.").format(device_vat, setting_doc.company, company_vat),
			title=_("VAT number mismatch"),
		)
