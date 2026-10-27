# Saudi National Address lookup

NeoZatca fills addresses from the national register run by Saudi Post (SPL), so building numbers,
postal codes and districts are exactly what ZATCA expects.

## Set up
1. Subscribe at https://api.address.gov.sa and copy your subscription key.
2. **Zatca Main Settings → Saudi National Address**: paste the key (stored encrypted) and choose
   the result language (English or Arabic).

## Use
On any Saudi **Address**: **National Address → Fetch from National Address**, then find by

| Find by | Example |
|---------|---------|
| Short address | `RRRD2929` (4 letters + 4 digits, from the national address certificate) |
| Building no. + postal code (+ secondary no.) | `8228` + `12643` (+ `2121`) |
| Free text | `8228 12643` |
| Map location | latitude/longitude, or "Use my current location" |

Pick the result and the form fills Short Address, Building No, Street, District, City, Postal Code,
Secondary No and Region. Typing a full short address on an empty address fills it straight away.
**National Address → Verify** checks a saved address against the register.

The Process Flow's *National address* station can fetch and save the company address directly.

Results are cached for 24 hours per query to save API quota.
