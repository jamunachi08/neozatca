# Branches, Commercial Registers and VAT

## The rule

ZATCA registers **VAT per taxpayer** (legal entity). Branches of the same taxpayer have their own
**Commercial Registration (CR)** numbers and addresses, but the **same VAT number**.

| Situation | How to set it up in ERPNext / NeoZatca |
|-----------|-----------------------------------------|
| One company, several branches, each with its own CR | One **Company**; one **Commercial Register** + one ZATCA device per branch |
| Branches with **different VAT numbers** | They are different taxpayers → one **Company** each |
| VAT group | One Company per member; each uses the **group VAT** and puts its own **10-digit TIN** in Organization Unit (Quick Setup asks for it) |

## Adding a branch

1. Create the **Branch** and its **Address** (national address: building no., street, district, city, postal code).
2. Company → **ZATCA → ZATCA Quick Setup** (or Control Center → **Add branch device**).
3. Choose the Branch, enter its **CR number**, optionally its Address, paste a Fatoora OTP, connect.

Each branch device has its own certificate, invoice counter (ICV) and hash chain (PIH), as ZATCA
requires for every EGS unit.

## Which CR an invoice uses

1. The CR of the invoice's **Branch** (needs Branch as an accounting dimension on Sales Invoice).
2. Otherwise the user's **default CR** (User Permission on Commercial Register with *Is Default*).
3. Otherwise the company's default / main CR.

The QR code and the printed invoice show that branch's CR number.

## Test it on a test site

```bash
bench --site TEST_SITE execute neozatca.setup.branch_test_data.create --kwargs "{'confirm': True}"
bench --site TEST_SITE execute neozatca.setup.branch_test_data.verify
bench --site TEST_SITE execute neozatca.setup.branch_test_data.remove --kwargs "{'confirm': True}"
```
