# Onboarding — Reference

One-click onboarding turns a Company (or one of its branches / Commercial Registers) into a
ZATCA-connected EGS device. The user provides the company and the Fatoora **OTP**; the app
generates and stores everything else.

| Module | Role |
|--------|------|
| `neozatca/zatca/onboarding.py` | Orchestrator: `quick_setup`, `start_onboarding`, `run_onboarding` (background), `renew_production`, `reset_onboarding`, `preview_quick_setup` |
| `neozatca/zatca/csr.py` | In-process key/CSR builder (`cryptography`, secp256k1). No OpenSSL CLI, no temp files |
| `neozatca/zatca/api.py` | Fatoora HTTP calls (compliance CSID, production CSID, renewal) |
| `neozatca/zatca/demo.py` | Compliance documents (standard and/or simplified, per invoice type) |
| `neozatca/public/js/neozatca_onboarding.js` | Quick Setup dialog (Company), Connect/Resume dialog (device), live progress |

## Inputs

| From | Value |
|------|-------|
| Company | Tax ID (15-digit VAT, starts/ends with 3), `company_name_in_arabic` (else company name), domain → business category |
| Commercial Register | CR number, name (→ Organization Unit), address. Created automatically if missing |
| Address | Street, building no. (4 digits), district, city, postal code (5 digits) |
| User | Environment, OTP, optional branch, invoice types (1100 / 1000 / 0100), member TIN for VAT groups |

`preview_quick_setup` shows these before the OTP is spent and lists anything missing.

## Stages (all in `run_onboarding`, queue `long`)

Each stage commits before the next and is skipped when already done, so **Resume** never
repeats a finished step and never regenerates a key that a CSID was issued for.

| # | Stage | Produces (NeoZatca Setting field) |
|---|-------|-----------------------------------|
| 1 | Credentials | `csr_config`, `csr` (base64 PEM), `pih` (seed), `private_key`, `public_key`, `egs_serial_number`, `common_name` |
| 2 | Compliance CSID (`POST /compliance`, OTP) | `compliance_certificate`, `compliance_authorization` (Basic), `request_id`, `compliance_binary_security_token`, `compliance_secret` |
| 3 | Compliance checks (`POST /compliance/invoices`) | `invoice_one…six` flags — only the documents required by `invoice_type` |
| 4 | Production CSID (`POST /production/csids`) | `authorization` (final Basic auth), `certificate`, `binary_security_token`, `secret`, `production_request_id`, `connected_on` |

Safety checks: every certificate returned by ZATCA is verified against the device's private key
before it is stored; the OTP is cleared once the compliance CSID is issued.

**Initial PIH** = `base64(hex(sha256("0")))` =
`NWZlY2ViNjZmZmM4NmYzOGQ5NTI3ODZjNmQ2OTZjNzljMmRiYzIzOWRkNGU5MWI0NjcyOWQ3M2EyN2ZiNTdlOQ==`.
The first live invoice of a device chains from it; later invoices chain from the last logged hash.

## CSR

Subject `C=SA, OU=<branch or member TIN>, O=<legal name>, CN=<device name>`; extensions
`certificateTemplateName` (1.3.6.1.4.1.311.20.2, PrintableString: `TSTZATCA-Code-Signing` /
`PREZATCA-Code-Signing` / `ZATCA-Code-Signing`) and `subjectAltName` dirName with
`SN` (EGS serial `1-NeoZatca|2-ERPNext|3-<uuid>`), `UID` (VAT), `title` (invoice type),
`registeredAddress`, `businessCategory`. `csr_config` holds the equivalent OpenSSL config, so
the request can be reproduced with the ZATCA SDK for support cases.

## Realtime

Event `neozatca_onboarding` (and legacy `zatca` for the wizard), sent to the user who started the
run: `{setting, stage, message, indicator, percentage, complete}`.

## Security

Private key, secrets and Basic-auth tokens are at **permlevel 1** (System Manager only).
The renewal endpoint reads secrets server-side; no secret is sent to the browser.
`Reset Credentials` (System Manager) wipes all artefacts to re-onboard, e.g. sandbox → production.
