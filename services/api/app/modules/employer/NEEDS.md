# SPR-17 employer needs

POST /employer/needs creates (201). GET /employer/needs lists only the employer's
needs, ordered by id (200, [] when none). GET/PATCH /employer/needs/{need_id} read
and partially update (200). All routes use require_role("employer"): missing/invalid
auth 401, candidate 403, foreign/missing need identical 404. No company on create
gives 409. Ownership is derived from current_user -> Company; body IDs/unknown fields
are rejected with 422. Response is exactly id plus seven camelCase business fields.

POST requires title, specialization, minGrade, targetGrade. teamDescription defaults
to null; requiredSkills/optionalSkills default to []. Strings must be nonblank.
teamDescription can be cleared with null, skills with []. PATCH omits unchanged fields;
explicit null for other fields is rejected. Empty PATCH is a no-op.

Create and relevant PATCH changes validate against the active checksum-verified
SPR-14 catalog: specialization and grade IDs must exist; skills must belong to the
specialization. Grade order comes from catalog order, not a hardcoded enum.
minGrade <= targetGrade; neither skill list may contain duplicates, and lists must
not intersect. Validation precedes ORM changes, and PATCH validates merged values
under a need-row lock to avoid concurrent writes violating cross-field invariants.
Validation errors give 422; unavailable/corrupt catalog gives 503 without writes.
Duplicate title within a company gives 409 with rollback; cross-company names work.

Existing columns are reused: grade -> targetGrade, stack -> requiredSkills;
team_description/min_grade/optional_skills come from migration 0004. No new migration.
Legacy rows may contain nulls and display labels such as Python/FastAPI. Reads return
them unchanged. Title/description-only edits preserve those values. Changing either
grade validates the effective grade pair (legacy missing values stay unknown).
Changing specialization or either skills list validates their entire effective group;
legacy labels then need explicit replacement by valid IDs in the same PATCH.
There is no invented alias mapping or implicit seed/data rewrite.

Current catalog is DEMO. Validation is real against that catalog, but DS approval
and complete production coverage remain outstanding. No scoring/ranking or SPR-15
changes are introduced, and catalog version is not persisted on HiringNeed.
