# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""One-click ZATCA onboarding.

The user supplies what only they can: the company (whose VAT number, legal
name, CR and national address are already in ERPNext) and the OTP from the
Fatoora portal. Everything else is produced here, stage by stage:

    1. CSR config, CSR, private key, public key, initial PIH, EGS serial
    2. Compliance CSID   -> compliance certificate, Basic auth, request ID
    3. Compliance checks -> the sample documents ZATCA requires for the
                            device's invoice types (standard and/or simplified)
    4. Production CSID   -> production certificate and final Basic auth

Each stage persists and commits before the next starts, and each is skipped
when already done, so a failed run is resumed rather than restarted. Keys are
never regenerated once a CSID has been issued for them.
"""

import base64
import binascii
import traceback

import frappe
from frappe import _
from frappe.utils import cint, now_datetime

from neozatca.zatca.csr import (
	INITIAL_PIH,
	certificate_expiry,
	DeviceIdentity,
	certificate_matches_key,
	generate_credentials,
	new_common_name,
	new_egs_serial,
)

SETTING = "NeoZatca Setting"
EVENT = "neozatca_onboarding"
LEGACY_EVENT = "zatca"  # the onboarding SPA listens on this one

ONBOARDING_ROLES = ("System Manager", "Accounts Manager")

STANDARD_SAMPLES = ("invoice_one", "invoice_two", "invoice_three")
SIMPLIFIED_SAMPLES = ("invoice_four", "invoice_five", "invoice_six")

ARTEFACT_FIELDS = (
	"csr_config", "csr", "private_key", "public_key", "pih",
	"egs_serial_number", "common_name",
	"compliance_certificate", "compliance_binary_security_token", "compliance_secret",
	"compliance_authorization", "request_id",
	"binary_security_token", "secret", "certificate", "authorization", "token_type",
	"production_request_id", "certificate_expiry", "connected_on", "issuer_name", "serial_number509", "certificate_hash", "signature",
)
FLAG_FIELDS = ("check_csr", "check_csid", "check_pcsid", *STANDARD_SAMPLES, *SIMPLIFIED_SAMPLES)


# ====================================================================================================
# PUBLIC API


@frappe.whitelist()
def quick_setup(
	company: str,
	otp: str,
	environment: str = "production",
	cr_number: str | None = None,
	branch: str | None = None,
	invoice_type: str = "1100",
	industry: str | None = None,
	group_tin: str | None = None,
	address: str | None = None,
) -> dict:
	"""Company + OTP in, connected device out. Returns the device (setting) name.

	Call once per branch: each branch gets its own Commercial Register, address and device,
	all under the company's VAT number.
	"""
	frappe.only_for(ONBOARDING_ROLES)
	name = ensure_device(company, environment, cr_number, branch, invoice_type, industry, group_tin, address)
	start_onboarding(name, otp=otp)
	return {"setting": name}


@frappe.whitelist()
def start_onboarding(name: str, otp: str | None = None, environment: str | None = None) -> dict:
	frappe.only_for(ONBOARDING_ROLES)
	frappe.has_permission(SETTING, "write", name, throw=True)

	doc = frappe.get_doc(SETTING, name)
	if doc.onboarding_status in ("Queued", "In Progress"):
		frappe.throw(_("Onboarding is already running for {0}.").format(name))
	if cint(doc.check_pcsid):
		frappe.throw(_("{0} is already connected to ZATCA. Use Renew or Reset.").format(name))

	updates = {"onboarding_status": "Queued", "last_error": None}
	if environment and environment != doc.api_endpoints:
		if cint(doc.check_csid):
			frappe.throw(_("A CSID was already issued in {0}. Reset the device before switching environment.").format(doc.api_endpoints))
		updates["api_endpoints"] = environment
	if otp:
		updates["otp"] = otp.strip()
	elif not cint(doc.check_csid) and not doc.otp:
		frappe.throw(_("Enter the OTP from the Fatoora portal."))
	frappe.db.set_value(SETTING, name, updates)

	frappe.enqueue(
		"neozatca.zatca.onboarding.run_onboarding",
		queue="long",
		timeout=1200,
		job_id=f"neozatca-onboarding::{name}",
		deduplicate=True,
		enqueue_after_commit=True,
		name=name,
		user=frappe.session.user,
	)
	return {"queued": True}


@frappe.whitelist()
def reset_onboarding(name: str) -> None:
	"""Wipe credentials so the device can be onboarded again (e.g. sandbox -> production)."""
	frappe.only_for("System Manager")
	doc = frappe.get_doc(SETTING, name)
	if doc.onboarding_status in ("Queued", "In Progress"):
		frappe.throw(_("Wait for the running onboarding to finish."))
	clear = {f: None for f in ARTEFACT_FIELDS}
	clear.update({f: 0 for f in FLAG_FIELDS})
	clear.update({"otp": None, "onboarding_status": "Not Started", "last_error": None,
		"onboarding_log": _stamp(f"Credentials reset by {frappe.session.user}")})
	frappe.db.set_value(SETTING, name, clear)


@frappe.whitelist()
def renew_production(name: str, otp: str) -> None:
	"""Renew the production CSID with a fresh OTP. Runs server-side so secrets never leave the server."""
	frappe.only_for(ONBOARDING_ROLES)
	from neozatca.zatca.api import renew_production_csid

	doc = frappe.get_doc(SETTING, name)
	if not cint(doc.check_pcsid):
		frappe.throw(_("Device is not connected yet."))
	response = renew_production_csid(name, otp.strip(), doc.authorization, doc.csr)
	_apply_production(doc, response, stage_label="Production CSID renewed")


@frappe.whitelist()
def preview_quick_setup(company: str, cr_number: str | None = None, branch: str | None = None, address: str | None = None) -> dict:
	"""What quick_setup will use, so the dialog can show it and flag gaps before the OTP is spent."""
	frappe.only_for(ONBOARDING_ROLES)
	info = _company_profile(company, cr_number, branch, strict=False, address=address)
	info["devices"] = frappe.get_all(SETTING, filters={"company": company},
		fields=["name", "commercial_register", "organization_unit_name", "api_endpoints", "check_pcsid"])
	return {k: v for k, v in info.items() if k != "address_doc"}


# ====================================================================================================
# DEVICE PROVISIONING (Company -> Commercial Register -> Setting)


def ensure_device(company, environment, cr_number, branch, invoice_type, industry, group_tin, address=None) -> str:
	profile = _company_profile(company, cr_number, branch, strict=True, address=address)
	cr_name = _ensure_commercial_register(company, profile, branch)

	existing = frappe.db.get_value(SETTING, {"company": company, "commercial_register": cr_name}, "name")
	values = {
		"organization_identifier": profile["vat_number"],
		"organization_name": profile["organization_name"],
		"organization_unit_name": (group_tin or profile["unit_name"]).strip(),
		"location": profile["city"],
		"industry": industry or profile["industry"],
		"invoice_type": invoice_type or "1100",
		"address": profile["address"],
		"registration_type": "CRN",
		"country_name": "SA",
	}
	if existing:
		doc = frappe.get_doc(SETTING, existing)
		if not cint(doc.check_csid):
			doc.update(values)
			doc.api_endpoints = environment
			doc.save(ignore_permissions=True)
		return doc.name

	doc = frappe.get_doc({"doctype": SETTING, "company": company, "commercial_register": cr_name,
		"api_endpoints": environment, "onboarding_status": "Not Started", **values})
	doc.insert(ignore_permissions=True)
	return doc.name


def _company_profile(company, cr_number=None, branch=None, strict=True, address=None) -> dict:
	from frappe.contacts.doctype.address.address import get_company_address

	c = frappe.db.get_value("Company", company, ["company_name", "tax_id", "domain"], as_dict=True)
	if not c:
		frappe.throw(_("Company {0} not found").format(company))
	arabic = frappe.db.get_value("Company", company, "company_name_in_arabic") if frappe.get_meta("Company").has_field("company_name_in_arabic") else None
	custom_cr = frappe.db.get_value("Company", company, "custom_commercial_register") if frappe.get_meta("Company").has_field("custom_commercial_register") else None

	existing_cr = None
	linked_cr = None
	if not branch and frappe.get_meta("Company").has_field("commercial_register"):
		linked_cr = frappe.db.get_value("Company", company, "commercial_register")
	filters = {"company": company, "disabled": 0}
	if linked_cr:
		filters["name"] = linked_cr
	if branch:
		filters["branch"] = branch
	for row in frappe.get_all("Commercial Register", filters=filters,
			fields=["name", "commercial_register", "commercial_register_name", "address", "is_default", "is_main_commercial_register_for_the_company"],
			order_by="is_default desc, is_main_commercial_register_for_the_company desc, creation asc"):
		existing_cr = row
		break

	# A CR number that isn't on file yet is a new branch: don't borrow another branch's CR row.
	if cr_number and existing_cr and existing_cr.get("commercial_register") != cr_number:
		existing_cr = frappe.db.get_value("Commercial Register", cr_number,
			["name", "commercial_register", "commercial_register_name", "address"], as_dict=True)
	address_name = address or (existing_cr or {}).get("address") or (get_company_address(company) or frappe._dict()).get("company_address")
	address = frappe.get_doc("Address", address_name) if address_name else None

	missing = []
	vat = (c.tax_id or "").strip()
	if not (len(vat) == 15 and vat.isdigit() and vat[0] == "3" and vat[-1] == "3"):
		missing.append(_("Company Tax ID must be the 15-digit VAT number (starts and ends with 3)"))
	cr = (cr_number or (existing_cr or {}).get("commercial_register") or custom_cr or "").strip()
	if not cr:
		missing.append(_("Commercial Registration number"))
	if not address:
		missing.append(_("Company address (set a primary/billing Address linked to the Company)"))
	else:
		for field, label in (("address_line1", "Street"), ("building_no", "Building Number"),
				("district", "District"), ("city", "City"), ("pincode", "Postal Code")):
			if address.meta.has_field(field) and not (address.get(field) or "").strip():
				missing.append(_("Address {0}").format(label))
		if address.meta.has_field("building_no") and address.get("building_no") and not (str(address.building_no).isdigit() and len(str(address.building_no)) == 4):
			missing.append(_("Building Number must be 4 digits"))
		if address.get("pincode") and not (str(address.pincode).isdigit() and len(str(address.pincode)) == 5):
			missing.append(_("Postal Code must be 5 digits"))
	if strict and missing:
		frappe.throw("<br>".join(missing), title=_("Complete company details for ZATCA"))

	return {
		"vat_number": vat,
		"organization_name": (arabic or c.company_name or "").strip(),
		"unit_name": branch or (existing_cr or {}).get("commercial_register_name") or c.company_name,
		"cr_number": cr,
		"address": address_name,
		"address_doc": address,
		"city": address.city if address else None,
		"industry": c.domain or "Trading",
		"is_vat_group": vat[10:11] == "1",
		"missing": missing,
	}


def _ensure_commercial_register(company, profile, branch) -> str:
	cr = profile["cr_number"]
	if frappe.db.exists("Commercial Register", cr):
		return cr
	doc = frappe.get_doc({
		"doctype": "Commercial Register",
		"company": company,
		"commercial_register": cr,
		"commercial_register_name": branch or profile["unit_name"],
		"branch": branch,
		"address": profile["address"],
		"is_default": 0 if frappe.db.exists("Commercial Register", {"company": company}) else 1,
	})
	doc.insert(ignore_permissions=True)
	# Let invoices raised for this branch pick the right CR automatically.
	if branch and frappe.get_meta("Branch").has_field("commercial_register") and not frappe.db.get_value("Branch", branch, "commercial_register"):
		frappe.db.set_value("Branch", branch, "commercial_register", doc.name)
	return doc.name


# ====================================================================================================
# BACKGROUND RUN


def run_onboarding(name: str, user: str | None = None) -> None:
	ctx = _Run(name, user)
	try:
		_set(name, onboarding_status="In Progress")
		ctx.log("Onboarding started")
		_stage_credentials(ctx)
		_stage_compliance_csid(ctx)
		_stage_compliance_checks(ctx)
		_stage_production_csid(ctx)
		_set(name, onboarding_status="Completed", otp=None)
		ctx.publish(_("ZATCA onboarding completed — device connected"), "green", 100, complete=True)
	except Exception as e:
		frappe.db.rollback()
		msg = _clean_error(e)
		_set(name, onboarding_status="Failed", last_error=msg)
		ctx.log(f"FAILED: {msg}")
		frappe.log_error(title=f"NeoZatca onboarding failed: {name}", message=traceback.format_exc())
		ctx.publish(_("Onboarding failed: {0}").format(msg), "red", ctx.percent, complete=True)


class _Run:
	def __init__(self, name, user):
		self.name = name
		self.user = user or frappe.session.user
		self.percent = 0

	def doc(self):
		return frappe.get_doc(SETTING, self.name)

	def log(self, line):
		current = frappe.db.get_value(SETTING, self.name, "onboarding_log") or ""
		frappe.db.set_value(SETTING, self.name, "onboarding_log", (current + _stamp(line))[-20000:], update_modified=False)
		frappe.db.commit()

	def publish(self, message, indicator="blue", percent=None, complete=False, stage=None):
		if percent is not None:
			self.percent = percent
		payload = {"setting": self.name, "message": message, "indicator": indicator,
			"percentage": self.percent, "complete": complete, "stage": stage,
			"commercial_register_name": frappe.db.get_value(SETTING, self.name, "commercial_register")}
		frappe.publish_realtime(EVENT, payload, user=self.user, after_commit=False)
		frappe.publish_realtime(LEGACY_EVENT, payload, user=self.user, after_commit=False)


def _stage_credentials(ctx: _Run) -> None:
	doc = ctx.doc()
	if cint(doc.check_csid):
		ctx.log("Credentials: kept (CSID already issued for this key)")
		return
	from neozatca.zatca.utils import format_registered_address

	identity = DeviceIdentity(
		vat_number=(doc.organization_identifier or "").strip(),
		organization_name=(doc.organization_name or "").strip(),
		organization_unit=(doc.organization_unit_name or "").strip(),
		common_name=new_common_name(doc.organization_identifier or "000000000000000"),
		egs_serial=new_egs_serial(),
		invoice_type=doc.invoice_type or "1100",
		registered_address=format_registered_address(doc),
		business_category=(doc.industry or "Trading").strip(),
		environment=doc.api_endpoints or "production",
	)
	try:
		creds = generate_credentials(identity)
	except ValueError as e:
		frappe.throw(str(e))

	_set(doc.name,
		csr_config=creds.csr_config, csr=creds.csr_b64,
		private_key=creds.private_key_pem, public_key=creds.public_key_pem,
		egs_serial_number=identity.egs_serial, common_name=identity.common_name,
		pih=doc.pih or INITIAL_PIH, check_csr=1)
	ctx.log(f"Credentials generated — EGS {identity.egs_serial}, CN {identity.common_name}")
	ctx.publish(_("CSR, keys and PIH generated"), "blue", 10, stage="credentials")


def _stage_compliance_csid(ctx: _Run) -> None:
	doc = ctx.doc()
	if cint(doc.check_csid):
		ctx.log("Compliance CSID: already issued")
		return
	from neozatca.zatca.api import get_zatca_csid
	from neozatca.zatca.utils import extract_details_from_certificate, make_auth_header_for_request

	if not doc.otp:
		frappe.throw(_("OTP is required to request the compliance CSID."))
	ctx.publish(_("Requesting compliance CSID…"), "blue", 15, stage="compliance_csid")
	request_id, token, secret = get_zatca_csid(doc.name, doc.otp, doc.csr)
	certificate = _decode_token(token)
	if not certificate_matches_key(certificate, doc.private_key):
		frappe.throw(_("ZATCA returned a certificate for a different key. Reset the device and retry."))

	auth = make_auth_header_for_request(token, secret)
	details = {}
	extract_details_from_certificate(certificate, details)
	_set(doc.name,
		request_id=request_id,
		compliance_binary_security_token=token, compliance_secret=secret,
		compliance_certificate=certificate, compliance_authorization=auth,
		# Active credentials = compliance until production is issued; the
		# compliance-check signer reads these.
		binary_security_token=token, secret=secret, certificate=certificate, authorization=auth,
		check_csid=1, otp=None, **details)
	ctx.log(f"Compliance CSID issued — request ID {request_id}")
	ctx.publish(_("Compliance CSID issued"), "green", 30, stage="compliance_csid")


def _stage_compliance_checks(ctx: _Run) -> None:
	doc = ctx.doc()
	if cint(doc.check_pcsid):
		return
	required = required_samples(doc.invoice_type)
	pending = [f for f in required if not cint(doc.get(f))]
	if not pending:
		ctx.log("Compliance checks: all required documents already accepted")
		return
	from neozatca.zatca.demo import send_sample_sales_invoices

	results = {}

	def on_document(index, total, accepted):
		ctx.publish(_("Compliance document {0}/{1} {2}").format(index, total, _("accepted") if accepted else _("rejected")),
			"green" if accepted else "red", 30 + int(50 * index / total), stage="compliance_checks")

	send_sample_sales_invoices(doc, results, on_document=on_document, required=required)
	flags = {f: 1 for f in required if results.get(f)}
	if flags:
		_set(doc.name, **flags)
	failed = [f for f in required if not results.get(f) and not cint(doc.get(f))]
	if failed:
		frappe.throw(_("ZATCA rejected {0} compliance document(s). See NeoZatca Logs, fix, then Resume.").format(len(failed)))
	ctx.log(f"Compliance checks passed ({len(required)} documents)")


def _stage_production_csid(ctx: _Run) -> None:
	doc = ctx.doc()
	if cint(doc.check_pcsid):
		return
	from neozatca.zatca.api import get_production_csid

	ctx.publish(_("Requesting production CSID…"), "blue", 85, stage="production_csid")
	response = get_production_csid(doc.name, doc.compliance_binary_security_token, doc.compliance_secret, doc.request_id)
	_apply_production(doc, response, stage_label="Production CSID issued")
	ctx.log(f"Production CSID issued — request ID {response.get('requestID')}")


def _apply_production(doc, response: dict, stage_label: str) -> None:
	from neozatca.zatca.utils import extract_details_from_certificate, make_auth_header_for_request

	token, secret = response.get("binarySecurityToken"), response.get("secret")
	if not (token and secret):
		frappe.throw(_("ZATCA did not return a production token: {0}").format(frappe.as_json(response)[:500]))
	certificate = _decode_token(token)
	if not certificate_matches_key(certificate, doc.private_key):
		frappe.throw(_("Production certificate does not match this device's key."))
	details = {}
	extract_details_from_certificate(certificate, details)
	_set(doc.name,
		binary_security_token=token, secret=secret, certificate=certificate,
		authorization=make_auth_header_for_request(token, secret),
		production_request_id=response.get("requestID"), token_type=response.get("tokenType"),
		check_pcsid=1, connected_on=now_datetime(), certificate_expiry=certificate_expiry(certificate), **details)
	frappe.publish_realtime(EVENT, {"setting": doc.name, "message": stage_label, "indicator": "green", "percentage": 95})


# ====================================================================================================
# HELPERS


def required_samples(invoice_type: str | None) -> tuple:
	t = (invoice_type or "1100").ljust(4, "0")
	return (STANDARD_SAMPLES if t[0] == "1" else ()) + (SIMPLIFIED_SAMPLES if t[1] == "1" else ())


def _set(name, **values):
	frappe.db.set_value(SETTING, name, values, update_modified=True)
	frappe.db.commit()


def _stamp(line):
	return f"[{now_datetime().strftime('%Y-%m-%d %H:%M:%S')}] {line}\n"


def _decode_token(token: str) -> str:
	try:
		return base64.b64decode(token).decode("utf-8")
	except (binascii.Error, UnicodeDecodeError, TypeError) as e:
		frappe.throw(_("Invalid certificate from ZATCA: {0}").format(e))


def _clean_error(e: Exception) -> str:
	text = str(e) or e.__class__.__name__
	return frappe.utils.strip_html(text)[:1000]
