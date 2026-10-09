# SPR-15.1 lifecycle only

POST /assessments/start accepts only specialization and grade. Candidate profile is
required (409 otherwise). Candidate-only JWT/RBAC protects both start and GET
/assessments/{attempt_id}. Foreign and missing IDs return identical 404.

New start returns 201. The same parameters return the existing active attempt (200),
even after the catalog changes. Another active combination returns 409. A profile
row lock serializes starts, backed by a partial unique index on candidate_id WHERE
status='active'. Unknown/unavailable combination gives 422; corrupt catalog gives
503 and no attempt. A/B is chosen server-side once using secrets.choice.

test_id is the blueprint ID. Versions, original artifact SHA-256 checksums, selected
variant and an internal snapshot of the complete blueprint/catalog are persisted.
The snapshot has its own schema version; source file checksums are not hashes of
the reserialized snapshot. GET and repeat start use only the saved snapshot.
Public responses contain id, status, createdAt, submittedAt and an allowlisted
assessment projection. Keys/rubric/scoring and the other variant never leave it.

Lifecycle status (active/submitted) is separate from content_status (DEMO/APPROVED).
The nested public assessment.status describes DEMO/APPROVED. This module never
writes profile grade, attempt grade/score or competency scores. DEMO cannot certify
a grade. There is no submit, scoring, cancellation, expiry or cooldown implementation.
Submitted history does not prohibit another start; SPR-15's later cooldown must be
checked under the same owner lock rather than by blueprint version/variant.

Migration 0005 marks old attempts legacy, leaving snapshots, versions and timestamps
unknown/NULL while preserving answers, scores and grades. Legacy GET returns 409
without trying to reconstruct questions. Legacy rows do not occupy the active slot.

Snapshot immutability is a service contract, tested for GET/retry and catalog
unavailability. No public update path or DB trigger exists. Future submit must only
update answers/result/lifecycle fields and preserve snapshot metadata. Direct SQL
administration is outside this service-level immutability guarantee.
