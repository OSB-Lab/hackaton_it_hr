# Deterministic ranking (current)

POST `/employer/needs/{need_id}/recommendations` now returns 200 with a saved
snapshot, including a valid empty cohort. Employer RBAC/ownership remain unchanged.
Missing/foreign need is 404; incomplete legacy need (specialization/minGrade) or
nontechnical/duplicate/unknown skills is 422, unavailable catalog/evidence is 503.
No client candidate IDs, scores or qualifications are accepted.

Algorithm `v3-mvp-coverage-fsp-demo-2`: LOCKED weights 0.50 skillFit + 0.35 testStrength +
0.15 fspBonus. Public `assessmentStrength` remains the name for testStrength.
All components and final score are 0..1. Sort score DESC, assessmentStrength DESC,
candidate_id ASC, with contiguous one-based rank. Old algorithm versions retain
their previous validation/order. No migration or rewriting of saved data.

Temporary **team MVP policy, not an approved v3 normalization rule**:
coverage = mean(certified skill evidence / 100), absent evidence=0, empty required=0.
skillFit = .80 required + .20 optional; without optional, required has weight 1.
Only canonical technical skills are accepted (teamwork is rejected for ranking).
CompetencyScore is a mutable latest-attempt cache: an unsuccessful retest overwrites
it. Therefore ranking uses the same technical subscores/evidenceCounts preserved in
the immutable result of the attempt pointed to by verified_attempt_id, not that cache
or any later attempt. testStrength = that result's technicalTotal / 100.
No assessment rules are changed and no self-reported stack contributes to score.

FSP demo: `FSP_DEMO_MODE=true` enables the synthetic JSON registry. Only a linked ID
present in that file contributes a bounded type × role × stack × recency bonus;
missing history scores 0. Persisted FspAchievement/seed rows alone never certify
anything. This is simulated evidence, labelled `Demo FSP bonus`, NOT official FSP
verification. Outside demo mode the bonus is 0. See
[`docs/FSP_DEMO_ACHIEVEMENTS.md`](../../../docs/FSP_DEMO_ACHIEVEMENTS.md)
for schema, formula, constraints and validation. Real FSP integration and proof of
ID ownership remain future work. No weight redistribution or gate relaxation.

`eligible_for_ranking` checks current email/publication/privacy + authoritative v3
qualification/matches_need before scores. Qualification must reference a successful
submitted APPROVED v3 attempt with matching candidate/catalog/blueprint metadata.
DEMO remains ineligible. User/profile locks serialize creation with privacy changes;
need is locked while calculating. This deliberately simple MVP scans candidate users;
batching/query optimization is deferred until measured scale requires it.

Creation atomically stores RecommendationSnapshot plus RecommendationItem rows.
GET replays saved values and rechecks disclosure gates without ranking again.
Each item adds optional `reasons` (empty for legacy) with three bounded numeric
templates: required evidence %, technical test %, verified FSP bonus %. These are
allowlisted strings, never candidate text, raw answers or contact fields. Existing
legacy free-text RecommendationItem.reason remains hidden; ranks/scores unchanged.
Talent Bank continues to use saved rank/score and current privacy checks.

Tests use controlled test-only APPROVED fixtures, never approve production artifacts.
The active pool is still DEMO: production needs normally produce empty cohorts until
real expert approval and successful qualification. Ranking execution is not evidence
of production accuracy; independent labels/Precision@3 remain outstanding.

## Historical SPR-18.1 implementation notes (superseded for POST)

# v3 qualification integration

The authoritative provider is now assessments/qualification.py. It validates the
profile pointer to a successful submitted APPROVED v3 attempt, including candidate,
catalog and blueprint metadata. eligible_for_ranking(session, candidate_id, need)
checks verified specialization/minGrade as well as the existing disclosure gates.
The active v3 question pool is DEMO pending expert review, so it does not qualify.
Talent Bank can display/filter grade from this proof; without proof grade stays null.
Category taxonomy remains unavailable. No ranking implementation is enabled by this
change: POST recommendations remains 503. v3 fixes the rank weights, but FSP evidence
mapping/normalization and the ranking implementation/acceptance remain separate work.
The earlier SPR-18.1 notes below describe the initial blocked provider, superseded
by this section and ../assessments/README.md.

# SPR-18.1 recommendation infrastructure

Both endpoints require Bearer authentication and require_role("employer").
Ownership is resolved through current_user -> Company -> HiringNeed, never from a
request body. Missing/foreign needs or snapshots return 404; no token 401, candidate 403.

- POST /employer/needs/{need_id}/recommendations: no body. Currently always 503
  with detail.code=ranking_unavailable after checking ownership. No insert, flush,
  commit, fake recommendations or empty successful selection is performed.
- GET /employer/needs/{need_id}/recommendations/{snapshot_id}: 200 saved snapshot
  {id, needId, createdAt, algorithmVersion, weights, items}. Each item contains
  {candidate: {id}, rank, score, components}. Candidate ID is the profile ID.
  weights/components have skillFit, assessmentStrength, fspBonus numeric fields;
  these are ranking metadata, never internal assessment scoring rules.

0007 adds nullable algorithm_version, weights and ordered_items JSON to snapshots.
Existing RecommendationItem rows are preserved. Legacy GET uses stored rank (NULL
last), then candidate_id and row ID; unknown version/weights/components remain null.
Legacy free-text reason is deliberately not exposed because it may contain contacts.
New payloads preserve their recorded order, require unique candidate IDs, contiguous
ranks and descending score with ascending candidate_id tie-breaks. DTOs are frozen,
including nested components and tuple items. No update/delete endpoint or service
exists. Immutability is an API/service contract, not protection against direct SQL.
The future writer must validate SnapshotPayload and write it once; it is absent here.
Downgrade removes new metadata; only exercised on disposable test databases.

GET does not load current catalog, score candidates, or infer qualifications. It
checks current candidate role, verified email, publication Consent and the existing
privacy veto. If any saved candidate cannot be disclosed, the entire response is
409 (no candidate data); stored items/order remain unchanged. This prevents consent
revocation being bypassed through history, without silently re-ranking a snapshot.
Reading history is not a claim that candidates are currently ranking-eligible.
Malformed/incomplete new payloads fail closed with 503, without returning raw data.
The minimal candidate DTO only exposes the numeric profile ID: no arbitrary text,
contacts, answers, correct option IDs, rubric, thresholds or internal rules.

has_verified_qualification currently always returns False: there is no authoritative
SPR-15.3 qualification contract. Neither grade/selfDeclaredGrade, seeded competency
scores nor an APPROVED/high assessment imply verified qualification. The separate
eligible_for_ranking gate combines disclosure and qualification checks. No DS policy,
specialization/minGrade eligibility or grade assignment is invented here.

BLOCKED: SPR-15.3 qualification evidence and DS-approved ranking formulas, weights,
normalization, missing-data rules and hand-calculated fixtures. No runtime weights or
DEMO algorithm are provided. Tests use persistence fixtures only, not ranking policy.
Before enabling creation, implement the approved qualification/need filters and
algorithm plus acceptance tests. SPR-18 is not complete.


## Talent bank (4.3): filtered view, no ranking

GET /employer/needs/{need_id}/recommendations/{snapshot_id}/items adds a separate
view without changing the existing snapshot GET contract. Bearer employer RBAC and
need/snapshot ownership apply. There is no POST/reset endpoint for this view.
Frontend retains baseSnapshotId (equal to snapshot_id); reset repeats the same URL
without query parameters. The backend does not persist per-client filter state.

Optional query parameters:
- specialization: exact active catalog specialization ID.
- grade: exact active catalog grade ID. Without authoritative qualification every
  valid grade filter currently returns an empty items array. No seed/profile grade
  or assessment result substitutes for certification.
- category: currently any supplied value returns 422 with
  detail.code=category_catalog_unavailable. SPR-14 has no category catalog. This
  temporary behavior is explicitly agreed; fail/pass/high are not category IDs.
- stack: repeat the parameter, e.g. stack=python&stack=sql. ALL requested skill IDs
  must match (AND); each ID is validated against catalog skills. No comma splitting,
  display-label mapping or normalization. Duplicates do not change the result.
- hasFspAchievements: boolean, true or false. For new snapshots the flag is
  `saved components.fspBonus > 0`, so it remains consistent with ranking even if
  the file changes later. For historical snapshots it is derived from a linked ID
  and nonempty achievements in the active synthetic registry; legacy history rows
  alone cannot set the flag. No link/no_history/empty record => false. The flag is
  not a claim of real FSP certification.

All filters combine with AND; a valid nonmatching combination returns 200/items=[].
Unknown catalog values, invalid booleans or extra query parameters return 422.
Catalog unavailable/corrupt => 503. The catalog remains DEMO, without new DS values.

Example request:
GET /employer/needs/7/recommendations/12/items?specialization=backend&stack=python&hasFspAchievements=true

Response shape (illustrative persisted item, not an algorithm or production seed):
```json
{
  "baseSnapshotId": 12,
  "needId": 7,
  "items": [{
    "candidate": {
      "id": 42, "specialization": "backend", "stack": ["python", "sql"],
      "grade": null, "category": null, "hasFspAchievements": true
    },
    "rank": 3, "score": 12, "components": null
  }]
}
```

Cards contain only numeric profile ID, allowlisted catalog IDs and a history flag.
Specialization and stack are CURRENT profile attributes, not verified qualification;
unknown/legacy display labels are omitted (specialization becomes null). grade and
category remain null until an authoritative contract is integrated. No names,
contacts, arbitrary text, achievement details, answers or assessment rules leave
this view. Scores/components/ranks come exclusively from the saved snapshot.

Filtering is a stable subsequence: ranks may have gaps; no sorting, re-ranking,
mutation, insert or score calculation occurs. Reset restores the saved order while
current profile/history/catalog determine filter attributes. Privacy is rechecked on
EVERY read before filters: same 409 policy as snapshot GET when any saved candidate
is no longer disclosable. Reset cannot bypass revoked consent. Old snapshots use the
same safe legacy projection and need no backfill. Existing 0007 is sufficient;
4.3 adds no migration and does not upgrade dev DB.

BLOCKED for complete Jira acceptance: category catalog and authoritative verified
grade/category source (SPR-15.3). Their successful-match tests require those real
contracts; current acceptance tests assert fail-closed behavior instead. Ranking
creation remains 503, independent of these read-only filters.
