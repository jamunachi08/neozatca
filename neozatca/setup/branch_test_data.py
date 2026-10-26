# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""The multi-branch test company, as real records on a test site, plus the same checks.

    bench --site TEST_SITE execute neozatca.setup.branch_test_data.create --kwargs "{'confirm': True}"
    bench --site TEST_SITE execute neozatca.setup.branch_test_data.verify
    bench --site TEST_SITE execute neozatca.setup.branch_test_data.remove --kwargs "{'confirm': True}"

Use a test site. `create` adds two companies (each with a chart of accounts), two branches,
four commercial registers, four addresses, one ZATCA device record (not onboarded), a test user
with a default-CR permission and, unless told not to, a "Branch" accounting dimension (which adds
a Branch field to Sales Invoice and other accounting documents site-wide). `verify` only reads
and raises nothing; it never saves an invoice. `remove` deletes what `create` made, except the
accounting dimension.
"""

import frappe
from click import secho

VAT = "300000000000003"          # ACME (NZ Test) — 15 digits, starts and ends with 3
OTHER_VAT = "300000000200003"    # OTHER (NZ Test)
COMPANY = "ACME (NZ Test)"
OTHER = "OTHER (NZ Test)"
JEDDAH = "Jeddah (NZ Test)"
DAMMAM = "Dammam (NZ Test)"
TEST_USER = "nz.branch.tester@example.com"

COMPANIES = [
	{"company_name": COMPANY, "abbr": "ACMT", "tax_id": VAT, "company_name_in_arabic": "أكمي للتجارة"},
	{"company_name": OTHER, "abbr": "OTHT", "tax_id": OTHER_VAT, "company_name_in_arabic": "شركة أخرى"},
]
# key, company, city, building, district, postal code, street
ADDRESSES = [
	("HQ", COMPANY, "Riyadh", "2929", "Al Olaya", "12211", "King Fahd Road"),
	("JED", COMPANY, "Jeddah", "4410", "Al Rawdah", "23434", "Prince Sultan Road"),
	("DMM", COMPANY, "Dammam", "6120", "Al Faisaliyah", "32272", "King Saud Street"),
	("OTH", OTHER, "Riyadh", "3105", "Al Malqa", "13521", "Anas Ibn Malik Road"),
]
# CR number, company, CR name, branch, address key, is_default, is_main
REGISTERS = [
	("1010000001", COMPANY, "ACME Head Office", None, "HQ", 1, 1),
	("4030000002", COMPANY, "ACME Jeddah", JEDDAH, "JED", 0, 0),
	("2050000003", COMPANY, "ACME Dammam", DAMMAM, "DMM", 0, 0),
	("1010999999", OTHER, "OTHER Head Office", None, "OTH", 1, 1),
]


def _address_name(key):
	return frappe.db.get_value("Address", {"address_title": f"NZ Test {key}"}, "name")


def create(confirm: bool = False, with_branch_dimension: bool = True):
	if not confirm:
		secho("Creates test companies and records (see module docstring). Re-run with confirm=True on a TEST site.", fg="yellow")
		return
	for cr, *_ in REGISTERS:
		owner = frappe.db.get_value("Commercial Register", cr, "company")
		if owner and owner not in (COMPANY, OTHER):
			frappe.throw(f"CR {cr} already exists for {owner}; this script will not touch it.")

	for c in COMPANIES:
		if not frappe.db.exists("Company", c["company_name"]):
			frappe.get_doc({"doctype": "Company", "default_currency": "SAR", "country": "Saudi Arabia", **c}).insert(ignore_permissions=True)
			secho(f"  company {c['company_name']}", fg="green")

	for b in (JEDDAH, DAMMAM):
		if not frappe.db.exists("Branch", b):
			frappe.get_doc({"doctype": "Branch", "branch": b}).insert(ignore_permissions=True)

	for key, company, city, building, district, pincode, street in ADDRESSES:
		if not _address_name(key):
			frappe.get_doc({
				"doctype": "Address", "address_title": f"NZ Test {key}", "address_type": "Billing",
				"address_line1": street, "building_no": building, "district": district, "city": city,
				"pincode": pincode, "country": "Saudi Arabia", "is_your_company_address": 1,
				"is_primary_address": 1 if key in ("HQ", "OTH") else 0,
				"links": [{"link_doctype": "Company", "link_name": company}],
			}).insert(ignore_permissions=True)

	for cr, company, name, branch, addr, is_default, is_main in REGISTERS:
		if not frappe.db.exists("Commercial Register", cr):
			frappe.get_doc({
				"doctype": "Commercial Register", "commercial_register": cr, "company": company,
				"commercial_register_name": name, "branch": branch, "address": _address_name(addr),
				"is_default": is_default, "is_main_commercial_register_for_the_company": is_main,
			}).insert(ignore_permissions=True)

	# Jeddah is linked from the Branch side; Dammam only from the CR side — both paths get tested.
	if frappe.get_meta("Branch").has_field("commercial_register"):
		frappe.db.set_value("Branch", JEDDAH, "commercial_register", "4030000002")
		frappe.db.set_value("Branch", DAMMAM, "commercial_register", None)

	if not frappe.db.exists("NeoZatca Setting", {"commercial_register": "4030000002"}):
		frappe.get_doc({
			"doctype": "NeoZatca Setting", "company": COMPANY, "commercial_register": "4030000002",
			"organization_identifier": VAT, "organization_name": "أكمي للتجارة", "organization_unit_name": "ACME Jeddah",
			"country_name": "SA", "registration_type": "CRN", "industry": "Trading", "invoice_type": "1100",
			"api_endpoints": "sandbox", "address": _address_name("JED"),
		}).insert(ignore_permissions=True)

	if not frappe.db.exists("User", TEST_USER):
		u = frappe.get_doc({"doctype": "User", "email": TEST_USER, "first_name": "NZ Branch Tester", "send_welcome_email": 0})
		u.append("roles", {"role": "Accounts User"})
		u.insert(ignore_permissions=True)
	if not frappe.db.exists("User Permission", {"user": TEST_USER, "allow": "Commercial Register", "for_value": "2050000003"}):
		frappe.get_doc({"doctype": "User Permission", "user": TEST_USER, "allow": "Commercial Register",
			"for_value": "2050000003", "is_default": 1, "apply_to_all_doctypes": 1}).insert(ignore_permissions=True)

	if with_branch_dimension and not frappe.db.exists("Accounting Dimension", {"document_type": "Branch"}):
		frappe.get_doc({"doctype": "Accounting Dimension", "document_type": "Branch"}).insert(ignore_permissions=True)
		secho("  Branch accounting dimension created (fields are added by a background job in ~1 min)", fg="green")

	frappe.db.commit()
	secho("Test data ready. Now run neozatca.setup.branch_test_data.verify", fg="green")


def verify():
	from neozatca.zatca.branches import (
		default_commercial_register, ensure_invoice_commercial_register, seller_identity, validate_device_vat)

	results = []

	def check(label, ok, got=""):
		results.append(ok)
		secho(f"  {'PASS' if ok else 'FAIL'}  {label}" + (f"   (got: {got})" if not ok else ""), fg="green" if ok else "red")

	if not frappe.db.exists("Company", COMPANY):
		secho("Run create first.", fg="yellow")
		return

	r = default_commercial_register(COMPANY); check("no branch → company default CR 1010000001", r == "1010000001", r)
	r = default_commercial_register(COMPANY, JEDDAH); check("Jeddah branch → 4030000002 (via Branch link)", r == "4030000002", r)
	r = default_commercial_register(COMPANY, DAMMAM); check("Dammam branch → 2050000003 (via CR.branch)", r == "2050000003", r)

	me = frappe.session.user
	try:
		frappe.clear_cache(user=TEST_USER)
		frappe.set_user(TEST_USER)
		r = default_commercial_register(COMPANY); check("test user's default CR → 2050000003", r == "2050000003", r)
		r = default_commercial_register(OTHER); check("user default of another company ignored → 1010999999", r == "1010999999", r)
	finally:
		frappe.set_user(me)

	inv = frappe.new_doc("Sales Invoice"); inv.company = COMPANY; inv.branch = JEDDAH
	ensure_invoice_commercial_register(inv)
	check("new invoice for Jeddah gets CR 4030000002", inv.commercial_register == "4030000002", inv.commercial_register)

	inv = frappe.new_doc("Sales Invoice"); inv.company = COMPANY; inv.commercial_register = "1010999999"
	try:
		ensure_invoice_commercial_register(inv); check("another company's CR is refused", False, "accepted")
	except frappe.ValidationError:
		check("another company's CR is refused", True)

	s = seller_identity(COMPANY, "4030000002")
	check("seller on Jeddah invoice: CR 4030000002, VAT 300000000000003, device found",
		s.cr_number == "4030000002" and s.vat == VAT and bool(s.setting), dict(s))

	dev = frappe.get_doc("NeoZatca Setting", {"commercial_register": "4030000002"})
	dev.organization_identifier = OTHER_VAT
	try:
		validate_device_vat(dev); check("branch device with a different VAT is refused", False, "accepted")
	except frappe.ValidationError:
		check("branch device with a different VAT is refused", True)
	frappe.clear_messages()

	has_branch = frappe.get_meta("Sales Invoice").has_field("branch")
	secho(f"  INFO  Sales Invoice has a Branch field: {'yes' if has_branch else 'not yet (dimension job pending)'}", fg="blue")
	secho(f"\n{sum(results)}/{len(results)} checks passed", fg="green" if all(results) else "red")


def remove(confirm: bool = False):
	if not confirm:
		secho("Deletes everything create() made (except the Branch accounting dimension). Re-run with confirm=True.", fg="yellow")
		return
	for name in frappe.get_all("NeoZatca Setting", filters={"company": ["in", [COMPANY, OTHER]]}, pluck="name"):
		frappe.delete_doc("NeoZatca Setting", name, ignore_permissions=True, force=True)
	for name in frappe.get_all("User Permission", filters={"user": TEST_USER}, pluck="name"):
		frappe.delete_doc("User Permission", name, ignore_permissions=True, force=True)
	if frappe.db.exists("User", TEST_USER):
		frappe.delete_doc("User", TEST_USER, ignore_permissions=True, force=True)
	for b in (JEDDAH, DAMMAM):
		if frappe.db.exists("Branch", b) and frappe.get_meta("Branch").has_field("commercial_register"):
			frappe.db.set_value("Branch", b, "commercial_register", None)
	for cr, *_ in REGISTERS:
		if frappe.db.exists("Commercial Register", cr) and frappe.db.get_value("Commercial Register", cr, "company") in (COMPANY, OTHER):
			frappe.delete_doc("Commercial Register", cr, ignore_permissions=True, force=True)
	for key, *_ in ADDRESSES:
		if name := _address_name(key):
			frappe.delete_doc("Address", name, ignore_permissions=True, force=True)
	for b in (JEDDAH, DAMMAM):
		if frappe.db.exists("Branch", b):
			frappe.delete_doc("Branch", b, ignore_permissions=True, force=True)
	for c in (OTHER, COMPANY):
		if frappe.db.exists("Company", c):
			frappe.delete_doc("Company", c, ignore_permissions=True, force=True)
	frappe.db.commit()
	secho("Test data removed.", fg="green")
