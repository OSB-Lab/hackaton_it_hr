# Employer company (SPR-13)

GET /employer/company returns the authenticated employer's company (200), or 404
if none exists. PUT /employer/company creates or replaces it and returns 200.
Both endpoints use require_role("employer"): no valid token gives 401; candidate
gives 403. Ownership always comes from the authenticated ORM User.

PUT accepts name (required, nonblank), description (string or null) and contacts
(JSON object or null). Omitted description/contacts become null: PUT is replacement,
not PATCH. Unknown top-level fields, including id, user_id and owner IDs, give 422.
The response contains exactly id, name, description, contacts; no owner ID.

The existing Company table is reused without migrations. PostgreSQL upsert uses
the unique user_id constraint, preserving company ID and preventing duplicate
companies on concurrent first writes. Nested contacts data is stored only as JSON
and cannot select an owner or mutate ownership. Repeated identical PUT retains the
company ID and values. Company operations do not modify hiring needs or seed data.

SPR-17 needs endpoints and catalog validation are described in [NEEDS.md](NEEDS.md).
