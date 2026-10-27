# Copyright (c) 2026, Neotec Integrated Solutions and contributors
# For license information, please see license.txt
"""ZATCA EGS credentials, built in-process.

Everything ZATCA needs from the device before the first API call is minted
here, in memory, with the ``cryptography`` package: the secp256k1 key pair,
the CSR with ZATCA's two mandatory extensions, and a human-readable rendering
of the CSR configuration for audit. Nothing touches the filesystem and nothing
shells out to OpenSSL, so two branches of the same company can never overwrite
each other's keys and the flow works the same on Frappe Cloud as on a laptop.
"""

import base64
import hashlib
import uuid
from dataclasses import dataclass

from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.x509.oid import NameOID, ObjectIdentifier

# Microsoft "certificateTemplateName" extension, which ZATCA uses to pick the
# issuing template per environment.
OID_CERT_TEMPLATE = ObjectIdentifier("1.3.6.1.4.1.311.20.2")
OID_REGISTERED_ADDRESS = ObjectIdentifier("2.5.4.26")

CERTIFICATE_TEMPLATES = {
	# The sandbox template is "TSTZATCA" — any other spelling is rejected with
	# an opaque "Invalid Request".
	"sandbox": "TSTZATCA-Code-Signing",
	"simulation": "PREZATCA-Code-Signing",
	"production": "ZATCA-Code-Signing",
}

# Previous Invoice Hash for the very first invoice of a device:
# base64( hex( sha256("0") ) ), as fixed by the ZATCA data dictionary.
INITIAL_PIH = base64.b64encode(hashlib.sha256(b"0").hexdigest().encode()).decode()

VALID_INVOICE_TYPES = ("1100", "1000", "0100")


@dataclass
class DeviceIdentity:
	vat_number: str  # 15 digits, starts and ends with 3
	organization_name: str  # legal name (Arabic allowed)
	organization_unit: str  # branch name, or the 10-digit TIN for VAT groups
	common_name: str  # unique device name
	egs_serial: str  # "1-<solution>|2-<model>|3-<serial>"
	invoice_type: str  # "1100" | "1000" | "0100"
	registered_address: str  # one line
	business_category: str  # industry
	environment: str  # sandbox | simulation | production


@dataclass
class DeviceCredentials:
	csr_config: str
	csr_pem: str
	csr_b64: str  # what the compliance API expects
	private_key_pem: str
	public_key_pem: str


def new_egs_serial(solution: str = "NeoZatca", model: str = "ERPNext") -> str:
	return f"1-{solution}|2-{model}|3-{uuid.uuid4()}"


def new_common_name(vat_number: str) -> str:
	return f"NZ-{vat_number[-5:]}-{uuid.uuid4().hex[:8].upper()}"


def _der_printable_string(value: str) -> bytes:
	raw = value.encode("ascii")
	if len(raw) < 0x80:
		return b"\x13" + bytes([len(raw)]) + raw
	length = len(raw).to_bytes((len(raw).bit_length() + 7) // 8, "big")
	return b"\x13" + bytes([0x80 | len(length)]) + length + raw


def render_csr_config(identity: DeviceIdentity) -> str:
	"""The CSR configuration in ZATCA's published OpenSSL layout.

	Kept for audit and support: it is exactly what the CSR below encodes, so it
	can be handed to the ZATCA SDK or OpenSSL to reproduce the request by hand.
	"""
	template = CERTIFICATE_TEMPLATES[identity.environment]
	return f"""oid_section = OIDS
[ OIDS ]
certificateTemplateName = 1.3.6.1.4.1.311.20.2

[ req ]
default_bits = 2048
req_extensions = v3_req
prompt = no
default_md = sha256
distinguished_name = dn
utf8 = yes
string_mask = utf8only

[ dn ]
C = SA
OU = {identity.organization_unit}
O = {identity.organization_name}
CN = {identity.common_name}

[ v3_req ]
certificateTemplateName = ASN1:PRINTABLESTRING:{template}
subjectAltName = dirName:alt_names

[ alt_names ]
SN = {identity.egs_serial}
UID = {identity.vat_number}
title = {identity.invoice_type}
registeredAddress = {identity.registered_address}
businessCategory = {identity.business_category}
"""


def generate_credentials(identity: DeviceIdentity) -> DeviceCredentials:
	validate_identity(identity)

	private_key = ec.generate_private_key(ec.SECP256K1())

	subject = x509.Name(
		[
			x509.NameAttribute(NameOID.COUNTRY_NAME, "SA"),
			x509.NameAttribute(NameOID.ORGANIZATIONAL_UNIT_NAME, identity.organization_unit),
			x509.NameAttribute(NameOID.ORGANIZATION_NAME, identity.organization_name),
			x509.NameAttribute(NameOID.COMMON_NAME, identity.common_name),
		]
	)
	alt_names = x509.Name(
		[
			x509.NameAttribute(NameOID.SURNAME, identity.egs_serial),
			x509.NameAttribute(NameOID.USER_ID, identity.vat_number),
			x509.NameAttribute(NameOID.TITLE, identity.invoice_type),
			x509.NameAttribute(OID_REGISTERED_ADDRESS, identity.registered_address),
			x509.NameAttribute(NameOID.BUSINESS_CATEGORY, identity.business_category),
		]
	)
	template = CERTIFICATE_TEMPLATES[identity.environment]

	csr = (
		x509.CertificateSigningRequestBuilder()
		.subject_name(subject)
		.add_extension(
			x509.UnrecognizedExtension(OID_CERT_TEMPLATE, _der_printable_string(template)),
			critical=False,
		)
		.add_extension(x509.SubjectAlternativeName([x509.DirectoryName(alt_names)]), critical=False)
		.sign(private_key, hashes.SHA256())
	)

	csr_pem = csr.public_bytes(serialization.Encoding.PEM).decode()
	private_pem = private_key.private_bytes(
		serialization.Encoding.PEM,
		serialization.PrivateFormat.TraditionalOpenSSL,
		serialization.NoEncryption(),
	).decode()
	public_pem = (
		private_key.public_key()
		.public_bytes(serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo)
		.decode()
	)

	return DeviceCredentials(
		csr_config=render_csr_config(identity),
		csr_pem=csr_pem,
		csr_b64=base64.b64encode(csr_pem.encode()).decode(),
		private_key_pem=private_pem,
		public_key_pem=public_pem,
	)


def validate_identity(identity: DeviceIdentity) -> None:
	errors = []
	vat = identity.vat_number or ""
	if not (len(vat) == 15 and vat.isdigit() and vat[0] == "3" and vat[-1] == "3"):
		errors.append("VAT number must be 15 digits, starting and ending with 3")
	if vat[10:11] == "1" and not (identity.organization_unit.isdigit() and len(identity.organization_unit) == 10):
		errors.append("VAT group member: Organization Unit must be the member's 10-digit TIN")
	if identity.invoice_type not in VALID_INVOICE_TYPES:
		errors.append("Invoice type must be 1100, 1000 or 0100")
	if identity.environment not in CERTIFICATE_TEMPLATES:
		errors.append("Environment must be sandbox, simulation or production")
	for label, value in (
		("Organization Name", identity.organization_name),
		("Organization Unit", identity.organization_unit),
		("Registered Address", identity.registered_address),
		("Business Category", identity.business_category),
	):
		if not (value or "").strip():
			errors.append(f"{label} is required")
	try:
		identity.egs_serial.encode("ascii")
		identity.common_name.encode("ascii")
	except UnicodeEncodeError:
		errors.append("EGS serial and common name must be ASCII")
	if errors:
		raise ValueError("; ".join(errors))


def certificate_matches_key(certificate_b64: str, private_key_pem: str) -> bool:
	"""True when a CSID certificate was issued for this device's key."""
	pem = "-----BEGIN CERTIFICATE-----\n" + certificate_b64.strip() + "\n-----END CERTIFICATE-----\n"
	cert = x509.load_pem_x509_certificate(pem.encode())
	key = serialization.load_pem_private_key(private_key_pem.encode(), password=None)
	fmt = (serialization.Encoding.DER, serialization.PublicFormat.SubjectPublicKeyInfo)
	return cert.public_key().public_bytes(*fmt) == key.public_key().public_bytes(*fmt)


def certificate_expiry(certificate_b64: str):
	"""notAfter date of a CSID certificate (base64 DER body), or None if unreadable."""
	try:
		pem = "-----BEGIN CERTIFICATE-----\n" + certificate_b64.strip() + "\n-----END CERTIFICATE-----\n"
		cert = x509.load_pem_x509_certificate(pem.encode())
		after = getattr(cert, "not_valid_after_utc", None) or cert.not_valid_after
		return after.date()
	except Exception:
		return None
