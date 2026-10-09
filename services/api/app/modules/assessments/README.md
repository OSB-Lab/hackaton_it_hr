# SPR-15.1/15.2 assessments

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
writes profile grade, attempt grade or competency scores. DEMO cannot certify
a grade. Cancellation, expiry, grade-change, retest offers and cooldown are not implemented.
Submitted history does not prohibit another start; SPR-15's later cooldown must be
checked under the same owner lock rather than by blueprint version/variant.

Migration 0005 marks old attempts legacy, leaving snapshots, versions and timestamps
unknown/NULL while preserving answers, scores and grades. Legacy GET returns 409
without trying to reconstruct questions. Legacy rows do not occupy the active slot.

Snapshot immutability is a service contract, tested for GET/retry and catalog
unavailability. No public snapshot update path or DB trigger exists. Submit only
update answers/result/lifecycle fields and preserve snapshot metadata. Direct SQL
administration is outside this service-level immutability guarantee.

POST /assessments/{attempt_id}/submit is candidate-only. Body:
`{"answers": [{"questionId": "question-id", "optionId": "option-id"}]}`.
Every question in the saved variant must appear exactly once; explicit null optionId
means unanswered and uses unansweredFraction. Missing/extra/duplicate questions,
unknown options, wrong types and extra fields give 422 without mutations.
Foreign/missing attempts give 404; employers give 403; legacy/no-snapshot gives 409.
Unsupported/corrupt active snapshots give 503. No current catalog is loaded.

Response (200): id, status="submitted", submittedAt, result containing subscores
(skillId -> score on snapshot scale), totalScore, outcome="fail"|"pass"|"high",
and status="DEMO"|"APPROVED". No keys or internal rules are exposed. Start/GET
retain their existing contract; retrieve the saved result by repeating submit.
Structurally valid retries return the saved result regardless of answer coverage;
request-schema validation still applies to retries. Historical submitted rows lacking
a persisted result return 409 rather than being recalculated.

Scoring uses snapshot rubric fractions and weighted_normalized_sum, globally and
within each skill: scaleMax * sum(weight * awardedScore / maxScore) / sum(weight).
Threshold comparisons precede conversion to response floats; no additional rounding
or thresholds are introduced. Submit locks the owned attempt row in PostgreSQL and
commits answers, score, result, submitted_at and status together. Concurrent requests
return the first committed result; errors roll back. Migration 0006 adds only nullable
JSON result, preserving historical rows. Profile/category fields remain untouched.
