# Architecture & delivery documentation

`arch/` owns system architecture, requirements traceability and delivery planning.
Business rules, team Q&A, use cases and question pool live in [`../business-logic/`](../business-logic/README.md).

## Read in this order

1. [`../materials/ФСП спец. трек ТЗ.pdf`](../materials/ФСП%20спец.%20трек%20ТЗ.pdf) and organiser Q&A.
2. [`requirements-coverage.md`](requirements-coverage.md) — TЗ → artefact → verification.
3. [`architecture.md`](architecture.md) — system boundaries, domains and API.
4. [`../business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md`](../business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md) — canonical assessment/matching rules.
5. [`../business-logic/USE_CASES_AND_MECHANISMS.md`](../business-logic/USE_CASES_AND_MECHANISMS.md) — user flows and state rules.
6. [`roadmap.md`](roadmap.md) — implementation order and DoD.

## Files

| File | Purpose |
|---|---|
| `architecture.md`, `architecture.canvas` | Architecture narrative and editable visual diagram |
| `requirements-coverage.md` | Requirement traceability |
| `roadmap.md` | Delivery plan |
| `build_assessment_v3.py` | Regenerates `../business-logic/questions-v3.json` |
| `validate_v3_skill_agents.py` | Question-level synthetic validation |
| `questions-v3.json` | Symlink for legacy tooling; canonical file is in `business-logic/` |

Never define scoring, thresholds, cooldown or ranking weights in `arch/`; link to the business contract instead.
