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
- hasFspAchievements: boolean, true or false. True requires a linked FspLink with
  fsp_id and linked_at and at least one persisted FspAchievement for the candidate.
  No link/no_history/no achievements => false. This uses server-owned FSP history,
  not free-text CV/profile claims; it does not independently authenticate an external
  provider or promote demo evidence to a verified qualification.

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
