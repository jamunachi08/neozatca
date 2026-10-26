# Onboarding — Docs

Everything about connecting a company's device to ZATCA (Fatoora) — the one-time setup that
turns a Commercial Register into a certificate-holding device that can clear and report
invoices.

| Document | For | What it covers |
|----------|-----|----------------|
| [user-guide.md](user-guide.md) | Implementers | Prerequisites, choosing the environment, the wizard steps, reading the result, renewal |
| [reference.md](reference.md) | Developers | One-click pipeline (`zatca/onboarding.py`), in-process CSR (`zatca/csr.py`), stages, fields, realtime, security |

Quickest path: **Company → ZATCA → ZATCA Quick Setup**, enter the OTP, done. The React wizard at
`/zatca-onboarding` uses the same engine. Its state lives on the **NeoZatca Setting** doctype (one per
**Commercial Register**), and it is resumable via the `check_csid` / `check_pcsid` stage flags.
