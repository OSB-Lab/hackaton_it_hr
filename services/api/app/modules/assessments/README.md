# Assessment v3 (SPR-14 / SPR-15.3)

Normative source: docs/v3/business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md,
pinned from origin/dev/docs commit 88859d0. The imported documents and question
pool are provenance copies; runtime serves only app/data/catalog artifacts.
Business rules are LOCKED; question content is still pending expert review.

## HTTP contract

All three endpoints require Bearer JWT and role=candidate. Foreign/missing attempt
IDs are indistinguishable 404. No frontend changes are included.

- POST /assessments/start: {"specialization":"backend","grade":"junior"}.
  New attempt: 201. Same active parameters: 200 with the original snapshot/variant,
  even if the active catalog changes. Different active parameters: 409.
  Missing profile: 409; unsupported specialization/grade, including senior: 422.
  Corrupt/unavailable catalog: 503, no insertion.
- GET /assessments/{attempt_id}: saved public snapshot only. Response retains id,
  status, createdAt, submittedAt, assessment. assessment contains blueprintId,
  blueprintVersion, catalogVersion, DEMO/APPROVED status, variant and questions.
  Each v3 question has id, slotId, skillTags, type, prompt, options (id/text).
  No answerKey, rubric, internal weights/thresholds, other forms or raw snapshot.
- POST /assessments/{attempt_id}/submit:
  {"answers":[{"questionId":"backend-junior-A-python-1","optionId":"o2"}, ...]}.
  Every question occurs exactly once; null optionId is an unanswered question.
  Missing/extra/duplicate question or unknown option: 422 without writes.
  200: id, status=submitted, submittedAt, result. Result retains subscores,
  totalScore, outcome=fail|pass|high, status=DEMO|APPROVED, and adds technicalTotal,
  correctTechnical, teamworkSubscore, evidenceCounts, verifiedGrade,
  verifiedSpecialization, retestOffer, retestTargetGrade, retestAvailableAt.
  A structurally valid repeated submit returns the stored original result;
  it neither scores again nor changes the qualification date.

## Scoring and qualification

schemaVersion=3 uses 18 technical + 2 diagnostic questions, shared slots, exactly
A/B/C. First start chooses A/B; retests use unseen forms including reserve C.
All forms have the same tag matrix: four singles per core, one per pair, three
triples; nine observations per core. Public IDs preserve authored uppercase forms.

technicalTotal = correctTechnical / 18 * 100, counting each question once.
Each skill evidence = correctTagged / taggedCount * 100. Integer cross-products
implement exact core gates. HIGH: >=16 correct and all core >=70%; otherwise PASS:
>=13 correct and all core >=50%; otherwise FAIL. Teamwork never affects grade.

Only a v3 APPROVED blueprint AND APPROVED catalog can establish qualification.
The shipped v3-demo artifacts are DEMO: results work, but do not certify or write
qualifying CompetencyScore records. A document with locked rules is not expert
approval. Publish reviewed questions/approval as a NEW immutable version.

CandidateProfile verified_grade/verified_specialization/verified_attempt_id and
last_grade_change_at are the single authority. The pointer must reference the same
candidate's submitted, successful, APPROVED v3 attempt with matching metadata.
No seed grade, selfDeclaredGrade, historical high score, DEMO or FSP substitutes.
GET /me/candidate-profile exposes read-only verifiedGrade/verifiedSpecialization;
eligibleForEmployerSearch also requires this proof, verified email and publication.

PASS/HIGH assign or promote, never downgrade. First assignment/promotion starts
ASSESSMENT_COOLDOWN_DAYS (default 90); same-grade confirmation keeps original date
and establishing attempt. FAIL keeps the existing qualification/date; first middle
FAIL offers junior. HIGH offers the next catalog grade (senior has no blueprint,
so start remains 422). A proposal does not bypass cooldown or create an attempt.
Same/higher start before the date: 409 detail={code:"assessment_cooldown",
retest_available_at:<UTC ISO timestamp>}. First/fail attempts do not start cooldown.
Only adjacent promotions are permitted. Switching an already verified specialization
is blocked with 409 until its product policy is specified; no silent replacement.

Seen forms are scoped by candidate, specialization, grade and blueprint version.
Forms seen within the configured cooldown interval cannot be reused; exhausting
A/B/C returns 409 assessment_pool_exhausted and the earliest form reuse timestamp.
A new immutable version has a fresh pool. This pool exposure limit also applies to
failed/DEMO attempts independently of the grade-change cooldown.

Approved v3 submit upserts technical competency scores with source=test, teamwork
with source=assessment_diagnostic, plus evidence_count, blueprint_version, attempt_id.
The establishing attempt retains immutable evidence even if later evidence differs.
No speculative discrepancy thresholds or automatic deletion of self-declared skills.

## Transactions and compatibility

Start and submit lock the same candidate profile; submit also locks its owned
attempt. Answers/result/evidence/qualification/status commit atomically. A partial
unique index forbids parallel active attempts. Failures roll everything back.
Snapshots are immutable through the service, without DB triggers; direct SQL
administration is outside this guarantee. Checksums pin original artifact bytes,
not reserialized JSON. Checksums are not cryptographic signatures.

Migration 0010 follows 0009. It adds nullable proof/evidence fields and expands
variant/source checks. No legacy backfill, no changes to old migrations. score is
technicalTotal for v3; diagnostic and retest metadata reuse the existing result JSON
instead of duplicate columns. Old schemaVersion=1 snapshots keep their old scorer;
legacy attempts without snapshots remain 409 and are never reconstructed/certified.
Downgrade refuses v3 data instead of deleting evidence. Dev DB was not migrated.

Recommendations and invitations use the same authoritative qualification provider.
Need-aware eligibility checks verified specialization and minGrade before ranking;
privacy/email/consent conditions remain mandatory. Talent Bank only displays verified
grade from this provider. Category taxonomy remains unavailable (category filter 422).
Ranking generation remains 503: implementing/calibrating ranking/FSP bonus is outside
this assessment change. Historical snapshot reads do not recompute ranking.

## Release checks and remaining gates

pytest -q includes v3 gates, legacy regression, ownership, atomic/concurrent submit,
qualification/privacy/invitation integration and migrations on temporary databases.
python docs/v3/arch/validate_v3_skill_agents.py runs the unchanged upstream synthetic
validation. It is not evidence of item quality on a real population.

Expert item review, calibration/pilot and a reviewed immutable APPROVED publication
are required for real certification. Full E2E additionally requires separately
approved dev migration, frontend integration, and the ranking/FSP implementation.
