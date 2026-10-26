# Phases and environments

NeoZatca handles both ZATCA **phases** and all three **environments**.

## Phases

| Phase | What happens on a Sales Invoice |
|-------|---------------------------------|
| **Phase One** (generation) | A TLV QR code (seller, VAT no., timestamp, total, VAT) is attached at submit. No ZATCA connection needed. |
| **Phase Two** (integration) | The invoice is signed and sent to ZATCA first — **cleared** (standard / B2B) or **reported** (simplified / B2C) — and can be submitted only after that. |

The site default is set in **Zatca Main Settings → Phase**. Each Company can override it in
**Company → ZATCA Phase** (blank = follow the site default), so companies in different ZATCA
waves can run side by side. Safety rails:

- A Company cannot be switched to Phase Two until it has a connected ZATCA device.
- Switching the site default to Phase Two lists companies that have no Production (Live) device.
- In Phase Two, an invoice whose company is connected only to Simulation or Sandbox shows an
  orange banner: those submissions are not legally reported.

## Environments (per device)

| Environment | Use | Where the OTP comes from |
|-------------|-----|--------------------------|
| **Production (Live)** | Legally valid clearance/reporting | [Fatoora Portal](https://fatoora.zatca.gov.sa/) → Onboard New Solution Unit/Device |
| **Simulation (Pre-production)** | End-to-end test with real taxpayer data, not legally valid | Fatoora Portal → “FATOORA Portal Simulation” (top right) → Onboard New Solution Unit/Device |
| **Sandbox (Developer)** | Integration test against the [Developer Portal](https://sandbox.zatca.gov.sa/) | Test OTP `123345` (filled in automatically) |

Production and Simulation are independent: a device onboarded in one is not onboarded in the
other. To move a device from a test environment to Live, use **Reset Credentials** on the device
and connect again with a production OTP.

## ZATCA Control Center

**/app/zatca-control-center** (also in the ZATCA workspace) shows, per company: effective phase
(with a one-click override for System Managers), missing company data, and each device with its
environment, connection status, certificate expiry, last 7 days of submissions/rejections and the
last accepted invoice. Each device has **Get OTP** (opens the right portal for its environment),
**Connect / Resume** and **Logs**. Official ZATCA links (portals, specifications, user manual,
developer community, solution-provider support) are listed at the bottom.

## Certificate watch

A daily job records each production certificate's expiry and notifies System Managers and Accounts
Managers 30, 14, 7, 3 and 1 day(s) before, on the day, and after expiry. Renew from the device with
a new OTP (**ZATCA → Renew Production CSID**).
