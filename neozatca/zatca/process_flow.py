# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""ZATCA Process Flow: the whole journey from an empty company to live e-invoicing.

Every step's status is computed from the site's own data on each call, so the flow is always
true to the site: fix something anywhere in ERPNext and the step turns green on refresh. Each
step carries the actions that finish it (open the document, create it, or run it here).
"""

import frappe
from frappe import _
from frappe.utils import add_days, cint, date_diff, getdate, now_datetime, today

from neozatca.zatca.links import portal_for
from neozatca.zatca.phase import PHASE_TWO, get_phase

VIEW_ROLES = ("System Manager", "Accounts Manager", "Accounts User")
FIX_ROLES = ("System Manager", "Accounts Manager")

STAGES = [
	{"key": "prepare", "label": "Prepare the company", "label_ar": "تجهيز المنشأة", "color": "#2563EB"},
	{"key": "tax", "label": "Configure VAT", "label_ar": "إعداد الضريبة", "color": "#7C3AED"},
	{"key": "connect", "label": "Connect to ZATCA", "label_ar": "الربط مع الهيئة", "color": "#0D9488"},
	{"key": "live", "label": "Go live", "label_ar": "التشغيل الفعلي", "color": "#D97706"},
	{"key": "operate", "label": "Run & monitor", "label_ar": "التشغيل والمتابعة", "color": "#DB2777"},
]


def _step(key, stage, title, title_ar, status, detail, actions, required=True, help=None):
	return {"key": key, "stage": stage, "title": title, "title_ar": title_ar, "status": status,
		"detail": detail, "actions": actions, "required": required, "help": help}


def _route(label, *route, primary=False, options=None):
	return {"type": "route", "label": label, "route": list(route), "options": options or {}, "primary": primary}


def _new(label, doctype, values=None, primary=False):
	return {"type": "new_doc", "label": label, "doctype": doctype, "values": values or {}, "primary": primary}


def _call(label, method, args=None, primary=False, confirm=None):
	return {"type": "method", "label": label, "method": method, "args": args or {}, "primary": primary, "confirm": confirm}


def _js(label, handler, args=None, primary=False):
	return {"type": "js", "label": label, "handler": handler, "args": args or {}, "primary": primary}


@frappe.whitelist()
def get_flow(company: str | None = None) -> dict:
	frappe.only_for(VIEW_ROLES)
	from neozatca.zatca.onboarding import _company_profile

	companies = frappe.get_all("Company", filters={"country": ["in", ["Saudi Arabia", "", None]]}, pluck="name", order_by="name") \
		or frappe.get_all("Company", pluck="name", order_by="name")
	company = company if company in companies else (frappe.defaults.get_user_default("Company") if frappe.defaults.get_user_default("Company") in companies else (companies[0] if companies else None))
	if not company:
		return {"companies": [], "stages": STAGES, "steps": []}

	can_fix = bool(set(frappe.get_roles()) & set(FIX_ROLES))
	phase = get_phase(company)
	phase_two = phase == PHASE_TWO
	profile = _company_profile(company, strict=False)
	c = frappe.db.get_value("Company", company, ["tax_id", "company_name", "abbr", "country"], as_dict=True)
	arabic = frappe.db.get_value("Company", company, "company_name_in_arabic") if frappe.get_meta("Company").has_field("company_name_in_arabic") else None
	steps = []

	# ---------------------------------------------------------------- 1. Prepare
	identity_gaps = []
	vat = (c.tax_id or "").strip()
	if not (len(vat) == 15 and vat.isdigit() and vat[0] == "3" and vat[-1] == "3"):
		identity_gaps.append(_("15-digit VAT number in Tax ID"))
	if not arabic:
		identity_gaps.append(_("Company name in Arabic"))
	if c.country and c.country != "Saudi Arabia":
		identity_gaps.append(_("Country = Saudi Arabia"))
	steps.append(_step("identity", "prepare", _("Company identity"), "بيانات المنشأة",
		"done" if not identity_gaps else "todo",
		_("VAT {0}, {1}").format(vat, arabic) if not identity_gaps else _("Missing: {0}").format(", ".join(identity_gaps)),
		[_route(_("Open Company"), "Form", "Company", company, primary=bool(identity_gaps))]))

	address_gaps = _address_gaps(profile.get("address_doc"))
	addr_actions = [_js(_("Fetch from National Address"), "fetch_address", {"address": profile["address"]}, primary=bool(address_gaps)),
		_route(_("Open Address"), "Form", "Address", profile["address"])] if profile["address"] else [
		_new(_("Create company address"), "Address", {"address_title": company, "address_type": "Billing", "country": "Saudi Arabia",
			"is_your_company_address": 1, "is_primary_address": 1, "links": [{"link_doctype": "Company", "link_name": company}]}, primary=True)]
	steps.append(_step("address", "prepare", _("National address"), "العنوان الوطني",
		"done" if profile["address"] and not address_gaps else "todo",
		_("{0}, {1}").format(profile["address"], profile["city"] or "") if profile["address"] and not address_gaps else ", ".join(address_gaps) or _("No address linked to the company"),
		addr_actions, help=_("Street, 4-digit building number, district, city and 5-digit postal code.")))

	crs = frappe.get_all("Commercial Register", filters={"company": company, "disabled": 0}, fields=["name", "commercial_register_name", "branch", "is_default"])
	has_default = any(r.is_default for r in crs)
	steps.append(_step("cr", "prepare", _("Commercial registers & branches"), "السجلات التجارية والفروع",
		"done" if crs and has_default else ("warn" if crs else "todo"),
		_("{0} CR(s): {1}").format(len(crs), ", ".join(f"{r.name}{' ★' if r.is_default else ''}" for r in crs)) + ("" if has_default or not crs else " — " + _("mark one as default"))
		if crs else _("No Commercial Register yet (Quick Setup can create it)"),
		[_route(_("Open CRs"), "List", "Commercial Register", options={"company": company}),
		 _new(_("Add CR / branch"), "Commercial Register", {"company": company, "address": profile["address"]}, primary=not crs)],
		help=_("One CR per branch; all branches share the company VAT.")))

	# ---------------------------------------------------------------- 2. Tax
	templates = frappe.get_all("Item Tax Template", filters={"company": company, "disabled": 0}, pluck="name")
	ksa_templates = [t for t in templates if "KSA VAT" in t]
	steps.append(_step("vat_setup", "tax", _("VAT accounts & tax templates"), "حسابات وقوالب الضريبة",
		"done" if len(ksa_templates) >= 4 else ("warn" if templates else "todo"),
		_("{0} KSA VAT templates ready (15%, 0%, exempt, out of scope)").format(len(ksa_templates)) if ksa_templates else _("Not set up for this company yet"),
		([_call(_("Set up VAT now"), "neozatca.zatca.process_flow.run_vat_setup", primary=not ksa_templates,
			confirm=_("Create tax categories, VAT accounts and 8 item tax templates for every company that lacks them?"))] if can_fix else [])
		+ [_route(_("Open templates"), "List", "Item Tax Template", options={"company": company})]))

	items_missing = frappe.db.sql("""
		SELECT COUNT(*) FROM `tabItem` i
		WHERE i.disabled = 0 AND i.is_sales_item = 1 AND NOT EXISTS (
			SELECT 1 FROM `tabItem Tax` t WHERE t.parent = i.name AND t.parenttype = 'Item')""")[0][0]
	steps.append(_step("items", "tax", _("Items tax-ready"), "الأصناف جاهزة ضريبياً",
		"done" if not items_missing else "todo",
		_("All sales items carry a VAT template") if not items_missing else _("{0} sales item(s) have no VAT template").format(items_missing),
		([_js(_("Fix items"), "fix_items", {"company": company}, primary=True)] if items_missing and can_fix else [])
		+ [_route(_("Open items"), "List", "Item")]))

	bad_customers = _customers_needing_attention(limit=None)
	steps.append(_step("customers", "tax", _("B2B customers"), "عملاء المنشآت",
		"done" if not bad_customers else "warn",
		_("Customers with a VAT number have a valid VAT and an address") if not bad_customers
		else _("{0} customer(s) need a valid VAT or an address for standard (B2B) invoices").format(len(bad_customers)),
		([_js(_("Review customers"), "review_customers", primary=True)] if bad_customers else []) + [_route(_("Open customers"), "List", "Customer")],
		required=False, help=_("Simplified (B2C) invoices don't need customer VAT.")))

	# ---------------------------------------------------------------- 3. Connect
	devices = frappe.get_all("NeoZatca Setting", filters={"company": company},
		fields=["name", "api_endpoints", "check_csid", "check_pcsid", "onboarding_status", "certificate_expiry", "commercial_register"])
	test_dev = [d for d in devices if d.check_pcsid and d.api_endpoints != "production"]
	live_dev = [d for d in devices if d.check_pcsid and d.api_endpoints == "production"]
	in_progress = [d for d in devices if d.onboarding_status in ("Queued", "In Progress")]
	failed = [d for d in devices if d.onboarding_status == "Failed" and not d.check_pcsid]

	steps.append(_step("test_device", "connect", _("Test connection (sandbox / simulation)"), "ربط تجريبي",
		"done" if test_dev or live_dev else ("progress" if in_progress else "todo"),
		_("Tested on {0}").format(", ".join(sorted({d.api_endpoints for d in test_dev}))) if test_dev
		else (_("Skipped — already live") if live_dev else _("Recommended before production: sandbox accepts OTP 123345")),
		[_js(_("Connect a test device"), "quick_setup", {"company": company, "environment": "sandbox"}, primary=not (test_dev or live_dev)),
		 _route(_("Developer Portal"), "url", portal_for("sandbox")["url"])],
		required=False))

	live_actions = []
	if failed:
		live_actions.append(_route(_("Open failed device"), "Form", "NeoZatca Setting", failed[0].name, primary=True))
	live_actions.append(_js(_("Connect Production (Live)"), "quick_setup", {"company": company, "environment": "production"}, primary=not live_dev and not failed))
	live_actions.append(_route(_("Get OTP — Fatoora"), "url", portal_for("production")["url"]))
	steps.append(_step("live_device", "connect", _("Production device (Live)"), "الربط الفعلي",
		"done" if live_dev else ("progress" if in_progress else ("error" if failed else "todo")),
		_("{0} live device(s): {1}").format(len(live_dev), ", ".join(d.commercial_register for d in live_dev)) if live_dev
		else (_("Onboarding running…") if in_progress else (_("Onboarding failed on {0} — open it and press Resume").format(failed[0].name) if failed
		else _("Needs an OTP from the Fatoora portal (valid 1 hour)"))),
		live_actions, required=phase_two, help=None if phase_two else _("Needed only from Phase Two.")))

	# ---------------------------------------------------------------- 4. Go live
	enabled = cint(frappe.db.get_single_value("Zatca Main Settings", "enable_neozatca"))
	steps.append(_step("enable", "live", _("Enable NeoZatca & choose phase"), "التفعيل واختيار المرحلة",
		"done" if enabled and (not phase_two or live_dev) else ("warn" if enabled else "todo"),
		(_("Enabled, {0}").format(_(phase)) + ("" if not phase_two or live_dev else " — " + _("Phase Two needs a live device"))) if enabled
		else _("NeoZatca is switched off in Zatca Main Settings"),
		[_route(_("Open ZATCA Settings"), "Form", "Zatca Main Settings", primary=not enabled),
		 _route(_("Company phase"), "Form", "Company", company)]))

	ok_logs = frappe.db.count("NeoZatca Logs", {"company": company, "status": ["in", ["Success", "Warning"]], "api_endpoint": ["in", ["clearance", "reporting"]]})
	first_needed = phase_two
	submitted = frappe.db.count("Sales Invoice", {"company": company, "docstatus": 1})
	steps.append(_step("first_invoice", "live", _("First invoice"), "أول فاتورة",
		"done" if (ok_logs if first_needed else submitted) else "todo",
		(_("{0} invoice(s) accepted by ZATCA").format(ok_logs) if ok_logs else _("No invoice accepted by ZATCA yet")) if first_needed
		else (_("{0} invoice(s) submitted with Phase One QR").format(submitted) if submitted else _("Submit an invoice to see the QR code")),
		[_new(_("New Sales Invoice"), "Sales Invoice", {"company": company}, primary=True),
		 _route(_("Submission logs"), "List", "NeoZatca Logs", options={"company": company})]))

	# ---------------------------------------------------------------- 5. Operate
	since = add_days(now_datetime(), -7)
	rejected = frappe.db.count("NeoZatca Logs", {"company": company, "status": "Failed", "creation": [">=", since]})
	expiring = [d for d in live_dev if d.certificate_expiry and date_diff(getdate(d.certificate_expiry), getdate(today())) <= 30]
	health_status = "done" if live_dev and not rejected and not expiring else ("warn" if rejected or expiring else "todo")
	notes = []
	if rejected:
		notes.append(_("{0} rejected in 7 days").format(rejected))
	if expiring:
		notes.append(_("{0} certificate(s) expire within 30 days").format(len(expiring)))
	steps.append(_step("health", "operate", _("Health & renewals"), "المتابعة والتجديد",
		health_status,
		", ".join(notes) or (_("All clear — certificates valid, no rejections this week") if live_dev else _("Starts once a live device is connected")),
		[_route(_("Control Center"), "zatca-control-center", primary=bool(notes)),
		 _route(_("Rejected invoices"), "List", "NeoZatca Logs", options={"company": company, "status": "Failed"})],
		required=phase_two))

	required = [s for s in steps if s["required"]]
	done = [s for s in required if s["status"] == "done"]
	next_step = next((s["key"] for s in steps if s["required"] and s["status"] != "done"), None) \
		or next((s["key"] for s in steps if s["status"] in ("todo", "warn", "error")), None)

	return {
		"company": company, "companies": companies, "phase": phase, "can_fix": can_fix,
		"stages": STAGES, "steps": steps, "next": next_step,
		"progress": {"done": len(done), "total": len(required)},
	}


def _address_gaps(address) -> list:
	if not address:
		return [_("No address linked to the company")]
	gaps = []
	for field, label in (("address_line1", _("street")), ("building_no", _("building number")), ("district", _("district")),
			("city", _("city")), ("pincode", _("postal code"))):
		if address.meta.has_field(field) and not str(address.get(field) or "").strip():
			gaps.append(label)
	b, p = str(address.get("building_no") or ""), str(address.get("pincode") or "")
	if b and not (b.isdigit() and len(b) == 4):
		gaps.append(_("building number must be 4 digits"))
	if p and not (p.isdigit() and len(p) == 5):
		gaps.append(_("postal code must be 5 digits"))
	return [_("Address: {0}").format(", ".join(gaps))] if gaps else []


def _customers_needing_attention(limit=50):
	rows = frappe.db.sql(f"""
		SELECT c.name, c.customer_name, c.tax_id,
			EXISTS(SELECT 1 FROM `tabDynamic Link` dl WHERE dl.link_doctype='Customer' AND dl.link_name=c.name AND dl.parenttype='Address') AS has_address
		FROM `tabCustomer` c
		WHERE c.disabled = 0 AND IFNULL(c.tax_id, '') != ''
		ORDER BY c.modified DESC {'' if limit is None else 'LIMIT 500'}""", as_dict=True)
	out = []
	for r in rows:
		vat = (r.tax_id or "").strip()
		problems = []
		if not (len(vat) == 15 and vat.isdigit() and vat[0] == "3" and vat[-1] == "3"):
			problems.append(_("VAT must be 15 digits starting and ending with 3"))
		if not r.has_address:
			problems.append(_("no address"))
		if problems:
			out.append({"name": r.name, "customer_name": r.customer_name, "tax_id": vat, "problems": ", ".join(problems)})
	return out if limit is None else out[:limit]


@frappe.whitelist()
def get_customers_needing_attention() -> list:
	frappe.only_for(VIEW_ROLES)
	return _customers_needing_attention(limit=50)


@frappe.whitelist()
def get_items_without_tax(limit: int = 100) -> list:
	frappe.only_for(VIEW_ROLES)
	return frappe.db.sql("""
		SELECT i.name, i.item_name, i.item_group FROM `tabItem` i
		WHERE i.disabled = 0 AND i.is_sales_item = 1 AND NOT EXISTS (
			SELECT 1 FROM `tabItem Tax` t WHERE t.parent = i.name AND t.parenttype = 'Item')
		ORDER BY i.modified DESC LIMIT %s""", (cint(limit) or 100,), as_dict=True)


@frappe.whitelist()
def apply_item_tax_template(template: str, items: str | list) -> dict:
	"""Add one Item Tax Template row to each selected item (skips items that already have it)."""
	frappe.only_for(FIX_ROLES)
	items = frappe.parse_json(items) if isinstance(items, str) else items
	if not frappe.db.exists("Item Tax Template", template):
		frappe.throw(_("Item Tax Template {0} not found").format(template))
	tax_category = frappe.db.get_value("Item Tax Template", template, "tax_category") if frappe.get_meta("Item Tax Template").has_field("tax_category") else None
	updated, failed = [], []
	for name in items[:500]:
		try:
			item = frappe.get_doc("Item", name)
			if any(t.item_tax_template == template for t in item.get("taxes") or []):
				continue
			row = {"item_tax_template": template}
			if tax_category:
				row["tax_category"] = tax_category
			item.append("taxes", row)
			item.save()
			updated.append(name)
		except Exception as e:
			failed.append({"item": name, "error": str(e)[:200]})
	frappe.db.commit()
	return {"updated": len(updated), "failed": failed}


@frappe.whitelist()
def run_vat_setup() -> dict:
	frappe.only_for(FIX_ROLES)
	from neozatca.setup.setup_vat_system.set_tax_configuration import create_complete_vat_system

	create_complete_vat_system()
	frappe.db.commit()
	return {"ok": True}
