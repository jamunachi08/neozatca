# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""Saudi National Address lookups (Saudi Post / SPL, apina.address.gov.sa).

Fill an ERPNext Address from any one of:
  * the short address           e.g. RRRD2929
  * building no. + postal code + additional (secondary) no.
  * free text                   e.g. "8228 12643"
  * a map location              latitude / longitude

The subscription key is stored in Zatca Main Settings (National Address section). Results are
cached for a day per query to spare the API quota.
"""

import hashlib
import json
import re

import frappe
import requests
from frappe import _

BASE = "https://apina.address.gov.sa/NationalAddress"
ENDPOINTS = {
	"short_address": "/NationalAddressByShortAddress/NationalAddressByShortAddress",
	"verify": "/v3.1/Address/address-verify",
	"fixed": "/v3.1/Address/address-fixed-params",
	"free_text": "/v3.1/Address/address-free-text",
	"geocode": "/v3.1/Address/address-geocode",
}
SHORT_ADDRESS_RE = re.compile(r"^[A-Z]{4}\d{4}$")
CACHE_SECONDS = 24 * 3600
TIMEOUT = 15


def _settings():
	settings = frappe.get_cached_doc("Zatca Main Settings")
	key = None
	if settings.meta.has_field("national_address_api_key"):
		key = settings.get_password("national_address_api_key", raise_exception=False)
	if not key:
		frappe.throw(
			_("Add your National Address API key in Zatca Main Settings (National Address section). "
			  "Subscribe at api.address.gov.sa."),
			title=_("National Address API key missing"),
		)
	return key, (settings.get("national_address_language") or "E")


def _call(endpoint: str, params: dict) -> dict:
	key, language = _settings()
	query = {"language": language, "format": "json", "encode": "utf8", **{k: v for k, v in params.items() if v not in (None, "")}}
	cache_key = "neozatca:na:" + hashlib.sha1(json.dumps([endpoint, query], sort_keys=True).encode()).hexdigest()
	cached = frappe.cache().get_value(cache_key)
	if cached:
		return cached
	try:
		resp = requests.get(BASE + ENDPOINTS[endpoint], params=query, headers={"api_key": key}, timeout=TIMEOUT)
	except requests.RequestException as e:
		frappe.throw(_("Could not reach the National Address service: {0}").format(str(e)[:200]))
	if resp.status_code in (401, 403):
		frappe.throw(_("The National Address service refused the API key (HTTP {0}). Check the key and your subscription.").format(resp.status_code))
	if resp.status_code == 429:
		frappe.throw(_("National Address API quota exceeded. Try again later."))
	if resp.status_code >= 400:
		frappe.throw(_("National Address service error (HTTP {0}).").format(resp.status_code))
	try:
		data = resp.json()
	except ValueError:
		data = json.loads(resp.content.decode("utf-8-sig", errors="replace") or "{}")
	if data.get("success") is False:
		frappe.throw(_("National Address: {0}").format(data.get("statusdescription") or data.get("fullexception") or _("no result")))
	frappe.cache().set_value(cache_key, data, expires_in_sec=CACHE_SECONDS)
	return data


def normalize(raw: dict) -> dict:
	"""One API address → the fields of an ERPNext Address (with NeoZatca's national-address fields)."""
	g = lambda *keys: next((str(raw[k]).strip() for k in keys if raw.get(k) not in (None, "", "null")), "")
	lat, lng = g("Latitude"), g("Longitude")
	if not (lat and lng) and g("ObjLatLng"):
		parts = g("ObjLatLng").split()
		# "[ObjectId] lng lat" or "lng lat"
		nums = [p for p in parts if re.match(r"^-?\d+\.\d+$", p)]
		if len(nums) >= 2:
			lng, lat = nums[0], nums[1]
	return {
		"short_address": g("ShortAddress", "Short_Address", "shortaddress").upper(),
		"building_no": g("BuildingNumber"),
		"address_line1": g("Street"),
		"district": g("District"),
		"city": g("City"),
		"pincode": g("PostCode", "ZipCode"),
		"address_line2": g("AdditionalNumber"),  # labelled "Secondary No" by NeoZatca
		"state": g("RegionName"),
		"country": "Saudi Arabia",
		"unit": g("UnitNumber"),
		"latitude": lat,
		"longitude": lng,
		"line_1": g("Address1"),
		"line_2": g("Address2"),
		"street_alt": g("Street_L2"),
		"district_alt": g("District_L2"),
		"city_alt": g("City_L2"),
	}


def _results(data: dict) -> list[dict]:
	rows = data.get("Addresses") or data.get("addresses") or []
	if isinstance(rows, dict):
		rows = [rows]
	return [normalize(r) for r in rows if isinstance(r, dict)]


def _check_access():
	if not (frappe.has_permission("Address", "write") or frappe.has_permission("Address", "create")):
		frappe.throw(_("Not permitted to edit addresses"), frappe.PermissionError)


@frappe.whitelist()
def lookup(mode: str, short_address: str | None = None, building_no: str | None = None, pincode: str | None = None,
		additional_no: str | None = None, text: str | None = None, latitude: str | None = None, longitude: str | None = None) -> dict:
	"""Return matching national addresses (max 10) for the chosen lookup mode."""
	_check_access()
	if mode == "short_address":
		code = re.sub(r"\s+", "", short_address or "").upper()
		if not SHORT_ADDRESS_RE.match(code):
			frappe.throw(_("Short address is 4 letters and 4 digits, e.g. RRRD2929."))
		results = _results(_call("short_address", {"shortaddress": code, "page": 1}))
		for r in results:
			r["short_address"] = r["short_address"] or code
	elif mode == "numbers":
		for label, value, n in ((_("Building number"), building_no, 4), (_("Postal code"), pincode, 5)):
			if not (value and str(value).isdigit() and len(str(value)) == n):
				frappe.throw(_("{0} must be {1} digits.").format(label, n))
		params = {"buildingnumber": building_no, "zipcode": pincode, "page": 1}
		if additional_no:
			params["additionalnumber"] = additional_no
		results = _results(_call("fixed", params))
	elif mode == "free_text":
		if not (text or "").strip():
			frappe.throw(_("Type something to search, e.g. 8228 12643."))
		results = _results(_call("free_text", {"addressstring": text.strip(), "page": 1}))
	elif mode == "geocode":
		try:
			lat, lng = float(latitude), float(longitude)
		except (TypeError, ValueError):
			frappe.throw(_("Latitude and longitude are required."))
		if not (16 <= lat <= 33 and 34 <= lng <= 56):
			frappe.throw(_("That location is outside Saudi Arabia."))
		results = _results(_call("geocode", {"lat": lat, "long": lng}))
	else:
		frappe.throw(_("Unknown lookup mode"))
	return {"results": results[:10]}


@frappe.whitelist()
def verify_address(address: str) -> dict:
	"""Check an Address's building no. + postal code + secondary no. against the national register."""
	doc = frappe.get_doc("Address", address)
	doc.check_permission("read")
	b, z, a = (str(doc.get(f) or "").strip() for f in ("building_no", "pincode", "address_line2"))
	if not (b and z and a):
		return {"verified": False, "reason": _("Building number, postal code and secondary number are needed to verify.")}
	data = _call("verify", {"buildingnumber": b, "zipcode": z, "additionalnumber": a, "page": 1})
	ok = str(data.get("addressfound", data.get("AddressFound", ""))).lower() == "true" or bool(_results(data))
	return {"verified": ok, "reason": None if ok else _("No national address matches these numbers.")}


@frappe.whitelist()
def apply_to_address(address: str, result: str | dict) -> dict:
	"""Write a chosen lookup result into an existing Address (used from the Process Flow)."""
	doc = frappe.get_doc("Address", address)
	doc.check_permission("write")
	r = frappe.parse_json(result) if isinstance(result, str) else result
	for field in ("short_address", "building_no", "address_line1", "district", "city", "pincode", "address_line2", "state", "country"):
		if r.get(field) and doc.meta.has_field(field):
			doc.set(field, r[field])
	doc.save()
	return {"address": doc.name}
