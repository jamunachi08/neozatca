# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Data for the ZATCA Control Center page: one card per company, one row per device."""

import frappe
from frappe import _
from frappe.utils import add_days, date_diff, getdate, now_datetime, today

from neozatca.zatca.links import ENVIRONMENTS, ZATCA_LINKS, portal_for
from neozatca.zatca.onboarding import ONBOARDING_ROLES, _company_profile, required_samples
from neozatca.zatca.phase import PHASE_ONE, PHASE_TWO, get_phase, get_site_phase

VIEW_ROLES = ("System Manager", "Accounts Manager", "Accounts User")


@frappe.whitelist()
def get_overview() -> dict:
	frappe.only_for(VIEW_ROLES)
	has_override = frappe.get_meta("Company").has_field("zatca_phase")
	companies = frappe.get_all("Company", fields=["name", "country", "tax_id"], order_by="name")
	device_companies = {r.company for r in frappe.get_all("NeoZatca Setting", fields=["company"])}
	since = add_days(now_datetime(), -7)

	cards = []
	for c in companies:
		if c.country not in (None, "", "Saudi Arabia") and c.name not in device_companies:
			continue
		profile = _company_profile(c.name, strict=False)
		devices = []
		for d in frappe.get_all("NeoZatca Setting", filters={"company": c.name},
				fields=["name", "commercial_register", "organization_unit_name", "api_endpoints", "check_csid",
					"check_pcsid", "onboarding_status", "last_error", "certificate_expiry", "invoice_type", "connected_on"],
				order_by="creation asc"):
			stats = {s.status: s.n for s in frappe.db.sql("""
				SELECT status, COUNT(*) n FROM `tabNeoZatca Logs`
				WHERE company=%s AND commercial_register=%s AND creation >= %s AND api_endpoint IN ('clearance','reporting')
				GROUP BY status""", (c.name, d.commercial_register, since), as_dict=True)}
			last_ok = frappe.db.get_value("NeoZatca Logs",
				{"company": c.name, "commercial_register": d.commercial_register, "status": ["in", ["Success", "Warning"]],
				 "api_endpoint": ["in", ["clearance", "reporting"]]}, "creation", order_by="creation desc")
			days_left = date_diff(getdate(d.certificate_expiry), getdate(today())) if d.certificate_expiry else None
			devices.append({
				**d,
				"environment_label": ENVIRONMENTS.get(d.api_endpoints or "production", {}).get("label"),
				"environment_color": ENVIRONMENTS.get(d.api_endpoints or "production", {}).get("color"),
				"days_left": days_left,
				"sent_7d": sum(stats.values()),
				"failed_7d": stats.get("Failed", 0),
				"warnings_7d": stats.get("Warning", 0),
				"last_success": last_ok,
				"portal": portal_for(d.api_endpoints),
				"compliance_docs": len(required_samples(d.invoice_type)),
				"advice": _device_advice(d, days_left, stats),
			})
		phase = get_phase(c.name)
		cards.append({
			"company": c.name,
			"phase": phase,
			"phase_override": frappe.db.get_value("Company", c.name, "zatca_phase") if has_override else None,
			"vat_number": profile["vat_number"],
			"cr_number": profile["cr_number"],
			"missing": profile["missing"],
			"devices": devices,
			"advice": _company_advice(phase, devices, profile),
		})

	return {
		"site_phase": get_site_phase(),
		"can_manage": bool(set(frappe.get_roles()) & set(ONBOARDING_ROLES)),
		"is_system_manager": "System Manager" in frappe.get_roles(),
		"companies": cards,
		"links": ZATCA_LINKS,
		"environments": ENVIRONMENTS,
	}


@frappe.whitelist()
def set_company_phase(company: str, phase: str | None = None) -> str:
	"""Set or clear (blank = site default) a company's phase; Company.validate enforces readiness."""
	frappe.only_for("System Manager")
	if phase not in (None, "", PHASE_ONE, PHASE_TWO):
		frappe.throw(_("Invalid phase"))
	doc = frappe.get_doc("Company", company)
	doc.zatca_phase = phase or ""
	doc.save()
	return get_phase(company)


def _device_advice(d, days_left, stats) -> list:
	tips = []
	if d.onboarding_status == "Failed":
		tips.append(("red", _("Onboarding failed: {0}").format((d.last_error or "")[:160])))
	elif not d.check_pcsid and d.check_csid:
		tips.append(("orange", _("Compliance CSID issued — press Resume to finish (no new OTP needed).")))
	elif not d.check_pcsid:
		tips.append(("orange", _("Not connected yet — get an OTP and connect.")))
	if d.check_pcsid and d.api_endpoints != "production":
		tips.append(("orange", _("Test environment — invoices are not legally reported.")))
	if days_left is not None and days_left < 0:
		tips.append(("red", _("Certificate expired — renew now with a new OTP.")))
	elif days_left is not None and days_left <= 30:
		tips.append(("orange", _("Certificate expires in {0} day(s) — plan renewal.").format(days_left)))
	if stats.get("Failed"):
		tips.append(("red", _("{0} rejected submission(s) in the last 7 days — review NeoZatca Logs.").format(stats["Failed"])))
	return tips


def _company_advice(phase, devices, profile) -> list:
	tips = []
	if profile["missing"]:
		tips.append(("orange", _("Complete company data before onboarding ({0} item(s)).").format(len(profile["missing"]))))
	live = [d for d in devices if d["check_pcsid"] and d["api_endpoints"] == "production"]
	if phase == PHASE_TWO and not live:
		tips.append(("red", _("Phase Two without a Production (Live) device — invoices cannot be legally cleared/reported.")))
	if phase == PHASE_ONE and live:
		tips.append(("blue", _("A Live device is connected but the company is in Phase One — switch to Phase Two when your wave starts.")))
	if not devices:
		tips.append(("blue", _("No device yet — use ZATCA Quick Setup.")))
	return tips
