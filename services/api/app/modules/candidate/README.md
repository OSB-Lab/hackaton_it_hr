# Candidate profile (SPR-12)

GET and PATCH `/me/candidate-profile` require Bearer authentication and candidate
role. Ownership always comes from current_user; no user/profile selector is accepted
in PATCH. Unknown fields, including email, grade and IDs, return 422.

GET returns a blank self profile if none exists, without writing to the database.
PATCH creates the owner's profile on first use. Omitted fields remain unchanged;
nullable scalar fields can be cleared with null, lists with []. Updates and consents
commit together; an owner row lock serializes concurrent creation/updates.

`email` is read-only from User. `role` is the professional role, not User.role.
`selfDeclaredGrade` is stored separately; tested `grade` is never written here.
Migration 0003 adds phone, professional_role, experience_months, soft_skills and
self_declared_grade to the existing candidate_profiles table. Existing rows and
confirmed grades are preserved. Profile content is not stored in privacy_settings.

PATCH accepts `consents: {processing: boolean, publication: boolean}`. Each value
is optional and independent. Existing Consent kinds are reused: processing maps
to privacy, publication to publish_profile; terms is untouched. Missing consent
means false. Grant sets granted_at, revoke clears it; repeating a grant preserves
its timestamp. Publication updates privacy_settings.publish_profile while preserving
other settings. Eligibility requires an existing candidate profile, granted
publication consent and no privacy publication veto. Processing does not silently
grant publication, and is not an additional eligibility condition in this contract.

Future employer services must call `hiring_profile(session, user_id)` for a fresh
consent check and safe HiringCandidateDTO, or use `eligible_for_employer_search`
to filter eligibility. Ineligible users return None from hiring_profile. Do not
cache a projection across consent changes without rechecking eligibility.

SelfCandidateDTO includes contacts; HiringCandidateDTO uses an explicit allowlist
without email, phone, user ID or raw JSON. Free-text values containing @ or common
numeric phone patterns are omitted by the projection and rejected by direct DTO
validation. This guards ordinary contact strings, not arbitrary obfuscation in
user-authored text. No employer search/matching endpoint is introduced.
