# SPR-14 versioned catalog and blueprints

Data lives in app/data/catalog. No database access, migrations, endpoints, scoring
execution, assessment lifecycle or verified-grade assignment are implemented here.

CatalogRepository reads manifest.json. Each artifact is identified by kind/id/version
and a stable manifest key. sha256 is computed over exact file bytes (including
whitespace/newlines); mismatches, identity mismatches, duplicate JSON keys, unsafe
paths and unknown versions fail closed. Keep JSON files as LF bytes in distribution.
Validate the entire bundle with CatalogRepository().validate_all(). There is no
fallback to a different version or to unvalidated raw JSON. Explicit catalog version
and blueprint key loads do not depend on active pointers. Loaded documents are frozen
Pydantic models with immutable tuples; Loaded carries the verified checksum.

Published artifact bytes are append-only by repository policy: a content change
requires a new version and manifest entry, retaining old artifacts. Checksums detect
file changes against the manifest; they are not signatures and cannot prevent an
authorized editor from changing both files and manifest. Review version changes.

Catalog contains stable specialization IDs, ordered grade IDs and skill IDs, with
explicit specialization-to-skill associations. validators.py exposes common checks
for future HiringNeed/ranking consumers. Seed uses a compatibility projection of this
single catalog; the former duplicate commands/seed/catalog.json is removed. Existing
stack display labels are not silently converted into canonical skill IDs.

Blueprint pins catalogVersion and specialization/grade. Exactly A and B each fill
all shared slots once. Slots define skillId, questionType, maxScore, weight, rubricId.
Only single_choice questions and single_choice_exact rubric are currently supported;
unknown types/formulas are rejected. Extension requires an explicit typed schema.
Question IDs are unique across variants; option IDs are unique per question; answerKey
must reference an option. Common rubric/max scores/weights cannot be overridden in a
variant. This guarantees structural equivalence, not equivalent difficulty.

Scoring config is declarative only: weighted_normalized_sum names the future rule
scaleMax * sum(weight * awardedScore / maxScore) / sum(weight). Rubric stores correct,
incorrect and unanswered fractions. Threshold boundaries are explicit: future fail
below passScore, pass from passScore inclusive to highScore exclusive, high from
highScore inclusive. No result is calculated by SPR-14. Missing rubric/scoring/
thresholds fail validation. Finite positive max scores/weights, finite thresholds and
0 < passScore < highScore <= scaleMax are required. No silent numerical defaults.

All shipped data is DEMO, including catalog ordering/associations and every question,
weight, rubric and threshold. Four blueprints cover backend/frontend x junior/middle,
with two slots each. DEMO examples are reused across grades and are not calibrated.
The catalog also retains senior for seed compatibility; no senior blueprint exists.
DEMO thresholds 50/100 and scale 100 are fixtures, not approved DS policy.

DEMO cannot automatically become APPROVED. APPROVED requires provenance=DS and a
nonempty approval reference/reviewer; an approved blueprint also requires an approved
catalog. There is no promote operation. DS approval should be published as a new
reviewed version. Approval metadata records a decision; it does not authenticate it.

public_variant(loaded, 'A'|'B') returns a separate allowlisted DTO: identity/version,
status, selected variant and questions/options only. No answerKey, rubric, weights,
thresholds or other variant is exposed. Internal artifact checksums stay server-side.
Never serve raw files/internal models or mount this directory as public static data.

SPR-15 must store the exact catalog/blueprint versions, checksums, selected variant
and immutable internal snapshot when starting an attempt. Public projection is not
enough to reconstruct scoring. Later active-version changes must not alter an attempt.

TODO DS: approve canonical skill mappings and grade order; approve questions/keys,
slot coverage, scoring formula/weights/rubric/thresholds; calibrate A/B difficulty;
define verified-grade mapping. Until then these artifacts cannot establish verified
qualifications. SPR-15 lifecycle/cooldown is a separate contract.

The known dev-DB 0004 vs checkout 0003 mismatch is deliberately untouched. This
module is filesystem-only; do not stamp/reset the database to install it.
