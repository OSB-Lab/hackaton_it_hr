# v3 qualification integration

Invitation create now calls the shared assessments/qualification.py provider via
recommendations.service.has_verified_qualification. A successful submitted APPROVED
v3 attempt linked as the candidate's current proof unlocks this gate. Active shipped
questions remain DEMO pending expert review: no bypass was added. Existing privacy,
verified email, ownership, state transitions and atomic disclosure/audit remain.
Integration tests cover actual approved TEST-ONLY v3 submit -> invitation creation,
without replacing the qualification provider.

# Invitations and state machine

REST API (Bearer auth throughout):
- POST /invitations: employer-only, 201. Body example:
  {"companyId": 1, "candidateId": 2, "offerDescription": "Backend role",
   "contactMethod": "email", "salaryMin": "100000.00", "salaryMax": "150000.00",
   "currency": "RUB"}.
  companyId is checked against current_user; candidateId is a profile ID.
  All fields except currency are required; currency defaults to RUB and only RUB
  is allowed. contactMethod is a nonblank employer-provided preferred contact method,
  not permission to disclose candidate data. No method enum has been invented.
- GET /invitations: own sent invitations for employer, own received invitations for
  candidate, newest ID first. Does not mark viewed, never includes contacts.
- GET /invitations/{id}: own detail. Recipient reading sent marks it viewed.
  Employer reading does not change status. Cache-Control: no-store.
- POST /invitations/{id}/accept and /decline: recipient candidate only, 200.

Foreign/missing objects -> 404; unauthenticated -> 401; wrong role -> 403.
Input extras and invalid/missing monetary fields -> 422. Monetary JSON must be
strings or integers; JSON floating-point values/bools, nonfinite numbers, fractions
beyond two decimal places and overflow are rejected. Both salaries are >0 and
salaryMax >= salaryMin. Python Decimal + NUMERIC(18,2), response amounts are strings.

Creation locks the owned Company and recipient User (same privacy lock as profile
PATCH). It checks existing verified email, candidate role, publication consent and
privacy veto. Nonsearchable/missing candidate -> generic 404. Missing authoritative
qualification -> 503 detail.code=verified_qualification_unavailable, with no invitation
or audit row. Profile/seed/selfDeclaredGrade or a standalone high score are not
qualification. The shared v3 provider requires a certifying APPROVED submitted attempt
linked to the candidate. Legacy unit fixtures isolate the provider; integration tests
exercise real TEST-ONLY approved submit. There is no production DEMO bypass.

Active uniqueness scope is (company_id,candidate_id): the existing model has no
need_id. Both sent and viewed are active. A company row lock plus PostgreSQL partial
unique index protect concurrent creates; duplicate -> 409 and rollback. Terminal
accepted/declined invitations do not prohibit a future invitation; another company
can independently invite the same candidate. No restriction on all future offers.

Transitions: sent -> viewed -> accepted/declined, or sent -> accepted/declined.
A repeated view never changes viewed/terminal status; repeating the same terminal
command returns 200 with no new event. Opposite terminal command -> 409. Invitation
row locks serialize view/accept/decline. Existing DB rejected maps to API declined;
no historical status rewrite. Lists are read-only, not a view action.

Every actual create/view/accept/decline transition writes AuditEvent atomically with
its state change. user_id is actor, action is invitation.created/viewed/accepted/
declined, created_at is event time, payload contains invitationId/from/to using API
status names. No salary, offer text or candidate contacts enter audit payloads.
Audit failure rolls back the state change; idempotent calls add no event.

DTO fields: id/companyId/candidateId/offerDescription/contactMethod/salaryMin/
salaryMax/currency/status/createdAt/updatedAt. No candidate name/contact projection.
Detail additionally has contacts=null, except an owned employer detail after accepted
when current verified email/publication/processing consent checks pass,
privacy_settings.publish_profile is explicitly true AND the existing
privacy_settings.show_contacts is explicitly true. Then only email and phone are
returned, only if a ContactDisclosure exists for THIS invitation. Absent/false
show_contacts never grants access. Successful accept records ContactDisclosure and
invitation.accepted in the same transaction as the status change, irrespective of
current privacy (which still gates every read). GET never creates a disclosure or
an audit event for contact access. Old invitation.contacts_disclosed audit rows are
preserved; no new such events are emitted. Revocation immediately hides contacts
again, without deleting history. Lists/action responses never include contacts.
Candidates read/change the flag through GET/PATCH /me/candidate-profile using
privacy.showContacts (strict boolean, default false). Accepting an invitation does
not automatically grant any consent or change the flag.

Migration 0008 follows existing uncommitted 0007: title becomes Text and maps to
API offerDescription, integer salaries become exact NUMERIC(18,2), nullable
contact_method/currency are added. Legacy unknown metadata remains null, no RUB or
method is invented. Existing rows, statuses and audit history are preserved.
If duplicate legacy active pairs exist, migration aborts without deleting/merging
rows; explicit reconciliation is required. Downgrade removes the new metadata and
refuses fractional/overflow salaries rather than silently rounding. Test DB only;
dev DB is not upgraded by this task.

Migration 0009 adds validated PostgreSQL CHECK constraints on the actual columns:
salary_from > 0, salary_to >= salary_from (also rejecting numeric NaN), and
currency = 'RUB'. No rows are repaired or deleted; invalid legacy values abort the
migration transaction. SQL CHECK deliberately preserves NULL currency as unknown
for legacy compatibility (it is NOT a NOT NULL constraint); all non-NULL values
must be RUB. API creation still supplies only RUB. Existing salaries remain NOT NULL.
Direct SQL INSERT/UPDATE are checked, not only Pydantic. Downgrade of 0009 only drops
these constraints. Historical AuditEvent/ContactDisclosure are never deleted when
any required consent/privacy permission is revoked.

Remaining content gate: expert-reviewed APPROVED question/catalog publication.
The authoritative v3 qualification implementation already exists.
DS/scoring/ranking/frontend and company/candidate active uniqueness are unchanged.


## Jira 5.2: contracts for the two frontend interfaces

No endpoint changes from 5.1. All requests use Authorization: Bearer <access JWT>.

Employer offer form: POST /invitations with companyId, candidateId (profile ID),
offerDescription, contactMethod, salaryMin/salaryMax as decimal strings, currency=RUB
(optional, defaults to RUB). Response 201 is InvitationDTO, without contacts.
Employer sent offers: GET /invitations returns InvitationDTO[] for the owned company.
Candidate inbox: same GET /invitations returns received InvitationDTO[]. Lists never
mark viewed. Candidate opens GET /invitations/{id} -> sent becomes viewed once.
Candidate submits POST /invitations/{id}/accept or /decline, no body -> InvitationDTO.
Repeat same terminal action returns 200 unchanged; opposite terminal action is 409.
UI statuses are sent, viewed, accepted, declined (DB rejected maps to declined).

Employer contact display: fetch GET /invitations/{id} for that exact accepted offer.
InvitationDetailDTO adds contacts, default null. Example authorized fragment:
`{"status":"accepted","contacts":{"email":"candidate@example.com","phone":null}}`.
Do not infer contact permission from accepted or global showContacts alone. Contacts
can become null after revocation; refetch detail and do not persist contact values
in snapshot/Talent Bank caches. Candidate detail always has contacts=null.
HiringCandidateDTO now also has contacts: ContactsDTO|null, default null, using the
same ContactsDTO type. Existing hiring_profile has no employer/invitation context
and ALWAYS leaves it null. No new candidate endpoint or duplicate DTO is introduced.
Snapshot/Talent Bank DTOs remain unchanged and never attach contacts, even when an
employer has a disclosure elsewhere. Invitation lists/action responses retain their
existing contact-free shape; only the authorized detail may populate ContactsDTO.

Disclosure is company/invitation-specific, not global candidate permission:
ContactDisclosure.invitation_id is an existing UNIQUE FK. Through Invitation it
binds candidate_id and origin company_id; company.user_id establishes employer
ownership. The API never reassigns these IDs. No redundant candidate/company fields
or new migration are necessary. Invitation row locking serializes accept/decline;
the DB UNIQUE constraint also rejects direct duplicate disclosure INSERTs.
The existing revealed_at column records grant creation at accept, not evidence of
an actual contact read. Privacy denial does not remove the historical grant.
Decline never creates a grant. Audit/disclosure insertion failures roll back the
entire accept. Idempotent repeats never insert another grant/event.

Legacy accepted WITHOUT disclosure stays masked, including after repeated accept:
no historical grant is fabricated or backfilled by GET or retry. Legacy accepted
WITH disclosure remains readable subject to current permissions. Old disclosure
and audit records are preserved without migration/data rewrites.

Frontend errors: 401 missing/invalid auth; 403 wrong action role; 404 foreign/missing
company/invitation or unavailable candidate; 409 active duplicate or conflicting
terminal action; 422 invalid/missing fields (including monetary strings/boolean
privacy); 503 verified_qualification_unavailable blocks creation when the candidate
has no authoritative v3 qualification (including the current DEMO pool). Show actionable errors, not a fabricated successful offer.
Candidate privacy controls use PATCH /me/candidate-profile with
`{"privacy":{"showContacts":true},"consents":{"processing":true,"publication":true}}`.
GET of that endpoint returns current privacy/consents. Neither accept nor privacy
settings grant verified qualification. All qualifications in successful-create tests
remain explicitly test-only fixtures. Frontend implementation is left to its owner.


## Frontend handoff and browser acceptance

All routes below require Authorization: Bearer <access token>.

| Method and path | Success DTO | UI behaviour |
| --- | --- | --- |
| POST /invitations | 201 InvitationDTO | Submit employer offer form |
| GET /invitations | 200 InvitationDTO[] | Employer outbox or candidate inbox |
| GET /invitations/{id} | 200 InvitationDetailDTO | Recipient view marks sent as viewed; only origin employer may receive contacts |
| POST /invitations/{id}/accept | 200 InvitationDTO | No body; atomically accept and grant disclosure |
| POST /invitations/{id}/decline | 200 InvitationDTO | No body; decline without disclosure |
| GET/PATCH /me/candidate-profile | 200 SelfCandidateDTO | Candidate controls privacy.showContacts and independent consents |

Example detail (other fields are identical in masked/authorized responses):

```json
{
  "id": 42, "companyId": 1, "candidateId": 2,
  "offerDescription": "Backend role", "contactMethod": "email",
  "salaryMin": "100000.00", "salaryMax": "150000.00", "currency": "RUB",
  "status": "accepted", "createdAt": "2026-10-10T10:00:00Z",
  "updatedAt": "2026-10-10T11:00:00Z", "contacts": null
}
```

Only a permitted employer detail replaces null with
`{"email":"candidate@example.com","phone":"+79990000000"}` (phone may be null).
No candidate-only contact endpoint exists. Foreign invitation is 404, not an object
with leaked metadata. Another employer's own unrelated invitation remains masked;
if the candidate independently accepts that employer's invitation with its own grant,
that separate origin relationship can independently permit disclosure.

Frontend must treat accepted and contacts availability as separate conditions. Do not
cache contact values in Talent Bank/snapshot data or keep displaying them after a
refetch returns null. Detail responses have Cache-Control: no-store. HTTP cannot
retract contacts already delivered before a revocation; subsequent reads recheck
current permissions. No websocket/push revocation contract is added.

Playwright integration is left to the frontend owner; no fabricated pages are added.
Use TWO isolated browser contexts for the main flow: employer and candidate, with
separate storageState/cookies/tokens. Employer creates an offer, candidate sees the
inbox and opens it (viewed); employer still sees masked detail. Candidate accepts;
employer refetches and sees contacts only with all active permissions. Candidate
revokes showContacts, publication, then processing in separate reset scenarios;
employer refetch must become masked without losing invitation/audit history.
Repeat accept, try opposite decline (409), and check outbox/Talent Bank remain masked.
Run another two-context isolation scenario for origin employer vs second employer;
use API setup for the candidate's acceptance. Origin can read contacts, foreign GET
is 404 and second employer's own ungranted invitation stays masked. Also run candidate
A vs candidate B: foreign GET/accept/decline must be 404 and must not create grants.

For browser setup, use explicitly approved TEST-ONLY artifacts in an isolated test DB
or real expert-approved content. Never toggle the production qualification provider,
label DEMO as APPROVED, or create fake production ranking/qualification just for E2E.
Backend tests independently exercise privacy, transactions, races and v3 qualification
without any frontend. New migration is unnecessary: the existing UNIQUE FK on
ContactDisclosure.invitation_id plus the invitation row lock already protect grants.
