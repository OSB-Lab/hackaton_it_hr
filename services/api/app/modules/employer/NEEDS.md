# SPR-17 employer needs

**BLOCKED BY SPR-14:** DoD `invalid catalog grade/skill -> 422` is not implemented.
SPR-17 cannot be considered fully closed until the agreed catalog validator is
connected. No hardcoded catalog or grade ordering is assumed. Structurally valid
unknown specialization/grade/skill identifiers are currently accepted.

All routes require require_role("employer") and Bearer authentication:
- POST /employer/needs: 201; without a company, 409.
- GET /employer/needs: 200, array containing only the owner's needs; empty if none.
- GET /employer/needs/{need_id}: 200; missing or foreign need returns identical 404.
- PATCH /employer/needs/{need_id}: 200; only provided fields are updated.

POST requires nonblank title, specialization, minGrade, targetGrade. teamDescription
defaults to null; requiredSkills and optionalSkills default to empty arrays.
Skills must be arrays of nonblank strings. Strings used as identifiers/title are
trimmed. PATCH allows clearing teamDescription with null and skill lists with [].
Other explicitly null fields are rejected. Unknown body fields, including IDs,
are forbidden (422). DTO contains id plus the seven business fields, no owner ID.

Ownership uses current_user -> Company -> HiringNeed in every read/write query.
Duplicate company/title yields 409 with rollback for both create and update;
different companies may use the same title. The existing database constraint is
the authority, including concurrent inserts.

grade stores targetGrade; stack stores requiredSkills. Migration 0004 adds nullable
team_description, min_grade and optional_skills without a backfill. Existing rows
retain NULL for new fields; response DTOs support legacy null values. New needs
use the request values. Existing seed source data is unchanged.
