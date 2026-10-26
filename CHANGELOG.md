# Changelog

## 1.1.0 — 2026-10-26
### Phases and environments
- Per-company **ZATCA Phase** (Company field; blank = site default). Used at invoice submit, by the
  Send to ZATCA button and by the desk boot info.
- Company cannot move to Phase Two without a connected device; site-wide switch to Phase Two lists
  companies without a Production (Live) device.
- Environment labels everywhere: Production (Live), Simulation (Pre-production), Sandbox (Developer).
- Sales Invoice banner when a Phase Two company has no device, or only a Simulation/Sandbox device.

### ZATCA links
- Official links registry (`zatca/links.py`): Fatoora Portal, Fatoora Simulation, Developer Portal,
  E-Invoice Specifications, Fatoora user manual, developer community, solution-provider support.
- OTP fields show the environment-specific steps with a link to the right portal; the sandbox test
  OTP is filled in automatically.
- Device form: open the portal for its environment, jump to the Control Center.
- Workspace: Control Center, ZATCA Devices, ZATCA Settings and portal shortcuts.

### Smart features
- **ZATCA Control Center** page: per-company phase (switchable), readiness gaps, devices with
  environment rail, connection status, certificate expiry, 7-day sent/rejected counts, last accepted
  invoice, contextual advice, and Get OTP / Connect / Resume / Logs actions.
- Daily certificate watch with notifications at 30/14/7/3/1/0 days and after expiry;
  `certificate_expiry` stored on each device and shown in the form headline.
- `after_migrate` re-applies custom fields, so new fields reach existing sites on deploy.


## 1.0.0 — 2026-10-26
App renamed to **NeoZatca** (`neozatca`). Publisher: Neotec Integrated Solutions · support@neotec.ai

### One-click onboarding
- **Company → ZATCA → ZATCA Quick Setup**: company details + OTP → connected device. Creates the
  Commercial Register and device record if missing; validates VAT, CR and national address first.
- Generates and stores all credentials: CSR config, CSR, PIH, private/public key, compliance
  certificate, compliance Basic auth, compliance request ID, production certificate, final auth.
- Background job (`long` queue) with live progress; resumable per stage; deduplicated per device.
- Compliance documents limited to what the device's invoice type needs (1100 / 1000 / 0100).
- Every certificate returned by ZATCA is checked against the device key before it is stored.
- New device form actions: Connect / Resume, Renew Production CSID, Reset Credentials.

### Fixes
- CSR and keys are built in-process with `cryptography` (no OpenSSL CLI, no files under
  `private/files`). Previously keys were written per company, so branches overwrote each other.
- Resuming onboarding no longer regenerates the private key after a CSID was issued (it used to,
  leaving the certificate and key mismatched).
- First invoice now chains from the ZATCA-defined initial PIH instead of a placeholder string.
- Private key, secrets and auth tokens moved to permlevel 1; the "All" role no longer exports
  device records; certificate renewal reads secrets server-side.
- `common_name` / `egs_serial_number` are generated, no longer mandatory on create.

### Platform
- `[tool.bench.frappe-dependencies]` for Frappe Cloud (frappe/erpnext `>=15,<17`).
- ERPNext v16 compatibility: `get_gl_entries` pass-through, `NumberFormat` in money-in-words.
- `scripts/verify_tree.py` structural guards in CI.
