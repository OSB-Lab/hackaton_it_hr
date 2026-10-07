# Employer company (SPR-13)

GET /employer/company returns the authenticated employer's company (200), or 404
if none exists. PUT /employer/company creates or replaces it and returns 200.
Both endpoints use require_role("employer"): no valid token gives 401; candidate
gives 403. Ownership always comes from the authenticated ORM User.

PUT accepts name (required, nonblank), description (string or null) and contacts
(JSON object or null). Omitted description/contacts become null: PUT is replacement,
not PATCH. Unknown top-level fields, including id, user_id and owner IDs, give 422.
The response contains exactly id, name, description, contacts; no owner ID.

Hiring needs are documented separately in [NEEDS.md](NEEDS.md).
SPR-17 catalog validation (`invalid catalog grade/skill -> 422`) remains
**BLOCKED BY SPR-14**; SPR-17 is not fully closed until that validator is connected.

The existing Company table is reused without migrations. PostgreSQL upsert uses
the unique user_id constraint, preserving company ID and preventing duplicate
companies on concurrent first writes. Nested contacts data is stored only as JSON
and cannot select an owner or mutate ownership. Repeated identical PUT retains the
company ID and values. Company operations do not modify hiring needs or demo seed.
