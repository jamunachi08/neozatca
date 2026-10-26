# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Phase resolution: a company may override the site-wide phase.

Groups often have companies in different ZATCA waves, so one company can be in
Phase Two (integration) while another is still Phase One (QR only).
"""

import frappe
from frappe import _

PHASE_ONE = "Phase One"
PHASE_TWO = "Phase Two"


def get_site_phase() -> str:
	return frappe.db.get_single_value("Zatca Main Settings", "phase") or PHASE_ONE


def get_phase(company: str | None) -> str:
	if company and frappe.get_meta("Company").has_field("zatca_phase"):
		override = frappe.get_cached_value("Company", company, "zatca_phase")
		if override in (PHASE_ONE, PHASE_TWO):
			return override
	return get_site_phase()


def device_summary(company: str) -> dict:
	rows = frappe.get_all(
		"NeoZatca Setting",
		filters={"company": company},
		fields=["name", "api_endpoints", "check_pcsid", "onboarding_status", "certificate_expiry"],
	)
	live = [r for r in rows if r.check_pcsid and r.api_endpoints == "production"]
	test = [r for r in rows if r.check_pcsid and r.api_endpoints != "production"]
	return {
		"devices": len(rows),
		"live": len(live),
		"test": len(test),
		"environment": "production" if live else (test[0].api_endpoints if test else None),
	}


def boot_company_map() -> dict:
	"""Small per-company map for the desk: phase + environment, used by invoice banners."""
	out = {}
	companies = {r.company for r in frappe.get_all("NeoZatca Setting", fields=["company"])}
	if frappe.get_meta("Company").has_field("zatca_phase"):
		companies |= {r.name for r in frappe.get_all("Company", filters={"zatca_phase": ["in", [PHASE_ONE, PHASE_TWO]]})}
	for company in companies:
		info = device_summary(company)
		out[company] = {"phase": get_phase(company), "environment": info["environment"], "live": info["live"]}
	return out


def validate_company_phase(doc, method=None):
	"""Company.validate: Phase Two needs a connected device, otherwise every invoice submit is blocked."""
	if doc.get("zatca_phase") != PHASE_TWO or not doc.has_value_changed("zatca_phase"):
		return
	info = device_summary(doc.name)
	if not (info["live"] or info["test"]):
		frappe.throw(
			_("Connect a ZATCA device for {0} before switching it to Phase Two (Company → ZATCA → ZATCA Quick Setup). "
			  "In Phase Two an invoice cannot be submitted until ZATCA clears or reports it.").format(doc.name),
			title=_("No ZATCA device connected"),
		)
	if not info["live"]:
		frappe.msgprint(
			_("{0} is connected only to a test environment ({1}). Invoices will not be legally reported until a Production (Live) device is connected.").format(doc.name, info["environment"]),
			indicator="orange", alert=True,
		)


def warn_site_phase_change(doc) -> None:
	"""Zatca Main Settings: when the site default moves to Phase Two, list companies that aren't ready."""
	if doc.phase != PHASE_TWO:
		return
	gaps = []
	for c in frappe.get_all("Company", fields=["name", "tax_id", "country"]):
		if c.country and c.country != "Saudi Arabia":
			continue
		if frappe.get_meta("Company").has_field("zatca_phase") and frappe.db.get_value("Company", c.name, "zatca_phase") == PHASE_ONE:
			continue
		if not device_summary(c.name)["live"]:
			gaps.append(c.name)
	if gaps:
		frappe.msgprint(
			_("These companies follow the site phase but have no Production (Live) ZATCA device: {0}. "
			  "Connect them, or set their ZATCA Phase to Phase One on the Company.").format(", ".join(gaps)),
			title=_("Phase Two readiness"), indicator="orange",
		)
