# ZATCA Process Flow

Open it from **Company → ZATCA → ZATCA Process Flow**, the ZATCA workspace, the Control Center or
the NeoZatca app icon. Pick the company at the top.

| Stage | Stations | What finishes them |
|-------|----------|--------------------|
| Prepare the company | Company identity, National address, Commercial registers & branches | VAT in Tax ID + Arabic name; address with 4-digit building no. and 5-digit postal code; at least one CR marked default |
| Configure VAT | VAT accounts & tax templates, Items tax-ready, B2B customers (optional) | **Set up VAT now**; **Fix items** applies a VAT template to the selected items; **Review customers** lists missing VAT/address |
| Connect to ZATCA | Test connection (optional), Production device | Quick Setup opens with the environment preselected (sandbox fills OTP 123345) |
| Go live | Enable NeoZatca & choose phase, First invoice | Zatca Main Settings / Company phase; a new Sales Invoice for the company |
| Run & monitor | Health & renewals | No rejections in 7 days and no certificate expiring within 30 days |

Statuses: **Done**, **To do**, **Needs attention**, **Running** (onboarding in progress) and
**Failed**. The page re-reads the site whenever you come back to it, so a station turns green as
soon as you've fixed it. **Continue with** always jumps to the next unfinished required step.

In **Phase One**, the device stations are optional and a submitted invoice with its QR code
completes *First invoice*. In **Phase Two**, a live device and an invoice accepted by ZATCA are
required.
