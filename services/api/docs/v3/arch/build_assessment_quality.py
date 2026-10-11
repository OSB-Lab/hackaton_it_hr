#!/usr/bin/env python3
"""Build the quality-pass-2 v3 question bank (backend/frontend x junior/middle).

Reads the authored content from ``assessment_content.py`` and reuses the LOCKED
structural parts (slots, rubric, scoring, thresholds) of the currently shipped
blueprints, so nothing about the contract changes here: only item text and
options do.

Outputs (all inside the repository working tree):

* ``app/data/catalog/blueprints/<cell>/<VERSION>.json`` — new blueprint artifacts
  carrying the new content under a NEW version id (append-only policy: the old
  ``v3-demo`` artifacts stay untouched);
* ``app/data/catalog/manifest.json`` — new artifact entries with fresh sha256 and
  ``activeBlueprints`` pointing at the new keys;
* ``docs/v3/business-logic/questions-v3.json`` — the authored pool in the shape
  consumed by ``validate_v3_skill_agents.py``;
* ``docs/assessment/QUESTION_METADATA.json`` — review metadata (rationale,
  difficulty, skill, group) kept OUT of the production schema.

Run from the repository root of this worktree::

    python services/api/docs/v3/arch/build_assessment_quality.py

The script is deterministic: rebuilding produces byte-identical artifacts.
"""
from __future__ import annotations

import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

HERE = Path(__file__).resolve().parent
API_ROOT = HERE.parents[2]            # services/api
CATALOG_ROOT = API_ROOT / "app" / "data" / "catalog"
VERSION = "v3-demo-q2"
FORMS = ("A", "B", "C")
CORE = {"backend": ("python", "sql", "api"),
        "frontend": ("javascript", "typescript", "react")}
PAIR_TAGS = tuple(combinations(range(3), 2))   # (0,1), (0,2), (1,2) — matches slot order
OLD_KEYS = {("backend", "junior"): "backend-junior-v3-demo",
            ("backend", "middle"): "backend-middle-v3-demo",
            ("frontend", "junior"): "frontend-junior-v3-demo",
            ("frontend", "middle"): "frontend-middle-v3-demo"}

sys.path.insert(0, str(HERE))
from assessment_content import CONTENT, DIFFICULTY  # noqa: E402


def option_order(question_id: str) -> list[int]:
    """Stable pseudo-random permutation: answer position never leaks the key."""
    return sorted(range(4), key=lambda i: hashlib.sha256(f"{question_id}:{i}".encode()).hexdigest())


def build_question(question_id: str, tags: list[str], item: tuple, slot_id: str) -> dict:
    prompt, correct, *wrong = item[:5]
    options = [correct, *wrong]
    order = option_order(question_id)
    options = [options[i] for i in order]
    return {
        "id": question_id,
        "slotId": slot_id,
        "type": "single_choice",
        "prompt": prompt,
        "skillTags": list(tags),
        "options": [{"id": f"o{i + 1}", "text": text} for i, text in enumerate(options)],
        "answerKey": {"optionId": f"o{options.index(correct) + 1}"},
    }


def cell_questions(spec: str, grade: str, form: str) -> list[dict]:
    """20 questions in slot order: 12 singles, 3 pairs, 3 triples, 2 teamwork."""
    core = CORE[spec]
    content = CONTENT[spec][grade]
    index = FORMS.index(form)
    questions: list[dict] = []
    slot = 1
    for skill in core:
        block = content[skill][index * 4:index * 4 + 4]
        for n, item in enumerate(block, 1):
            qid = f"{spec}-{grade}-{form}-{skill}-{n}"
            questions.append(build_question(qid, [skill], item, f"slot-{slot}"))
            slot += 1
    for pair_index, pair in enumerate(content["pairs"], 1):
        item = pair[index]
        qid = f"{spec}-{grade}-{form}-pair-{pair_index}"
        tags = [core[i] for i in PAIR_TAGS[pair_index - 1]]
        questions.append(build_question(qid, tags, item, f"slot-{slot}"))
        slot += 1
    for n, item in enumerate(content["triple"][index * 3:index * 3 + 3], 1):
        qid = f"{spec}-{grade}-{form}-all-{n}"
        questions.append(build_question(qid, list(core), item, f"slot-{slot}"))
        slot += 1
    for n, item in enumerate(content["teamwork"][index * 2:index * 2 + 2], 1):
        qid = f"{spec}-{grade}-{form}-teamwork-{n}"
        questions.append(build_question(qid, ["teamwork"], item, f"slot-{slot}"))
        slot += 1
    assert len(questions) == 20, len(questions)
    return questions


def _old_path(spec: str, grade: str) -> str:
    manifest = json.loads((CATALOG_ROOT / "manifest.json").read_bytes())
    ref = next(r for r in manifest["artifacts"] if r["key"] == OLD_KEYS[(spec, grade)])
    return ref["path"]


def build_blueprint(spec: str, grade: str) -> dict:
    """Reuse LOCKED structure (slots/rubric/scoring) from the shipped blueprint."""
    template = json.loads((CATALOG_ROOT / _old_path(spec, grade)).read_bytes())
    template["version"] = VERSION
    template["variants"] = [{"id": form, "questions": cell_questions(spec, grade, form)}
                            for form in FORMS]
    return template


def write_artifact(path: Path, payload: dict) -> str:
    raw = (json.dumps(payload, ensure_ascii=False, indent=2) + "\n").encode("utf-8")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def build_pool() -> dict:
    """Authored pool in the shape validate_v3_skill_agents.py consumes."""
    pool: dict = {}
    for spec in CORE:
        for grade in ("junior", "middle"):
            pool[f"{spec}-{grade}"] = {form: cell_questions(spec, grade, form) for form in FORMS}
    return pool


def build_metadata(blueprints: dict) -> dict:
    """Review metadata for humans; deliberately outside the production schema."""
    rows = []
    for (spec, grade), blueprint in blueprints.items():
        for variant in blueprint["variants"]:
            for question in variant["questions"]:
                item = _item_for(question["id"], spec, grade, variant["id"])
                rows.append({
                    "id": question["id"], "specialization": spec, "grade": grade,
                    "form": variant["id"], "skillTags": question["skillTags"],
                    "slotId": question["slotId"],
                    "prompt": question["prompt"],
                    "correct": next(o["text"] for o in question["options"]
                                    if o["id"] == question["answerKey"]["optionId"]),
                    "rationale": item[5],
                    "difficulty": DIFFICULTY[grade],
                    "measurableSkill": "+".join(question["skillTags"]),
                    "status": "DEMO-authored, pending expert review",
                })
    return {"schemaVersion": 1, "version": VERSION, "generatedBy": "build_assessment_quality.py",
            "note": ("Metadata is intentionally kept out of the blueprint schema. "
                     "Difficulty and rationale are author statements, not calibrated measurements."),
            "items": rows}


def _item_for(question_id: str, spec: str, grade: str, form: str) -> tuple:
    """Locate the authored tuple for a question id built by cell_questions()."""
    core = list(CORE[spec])
    parts = question_id.split("-")
    skill, name = parts[3], parts[4]
    index = FORMS.index(form)
    if skill == "pair":
        return CONTENT[spec][grade]["pairs"][int(name) - 1][index]
    if skill == "all":
        return CONTENT[spec][grade]["triple"][index * 3 + int(name) - 1]
    if skill == "teamwork":
        return CONTENT[spec][grade]["teamwork"][index * 2 + int(name) - 1]
    assert skill in core, question_id
    return CONTENT[spec][grade][skill][index * 4 + int(name) - 1]


def main() -> None:
    manifest_path = CATALOG_ROOT / "manifest.json"
    manifest = json.loads(manifest_path.read_bytes())
    blueprints = {}
    new_keys = []
    for spec in ("backend", "frontend"):
        for grade in ("junior", "middle"):
            blueprint = build_blueprint(spec, grade)
            blueprints[(spec, grade)] = blueprint
            rel = f"blueprints/{spec}-{grade}/{VERSION}.json"
            digest = write_artifact(CATALOG_ROOT / rel, blueprint)
            key = f"{spec}-{grade}-{VERSION}"
            new_keys.append(key)
            manifest["artifacts"] = [r for r in manifest["artifacts"] if r["key"] != key]
            manifest["artifacts"].append({
                "key": key, "kind": "blueprint", "id": blueprint["id"],
                "version": VERSION, "path": rel, "sha256": digest,
            })
            print(f"wrote {rel} sha256={digest[:16]} key={key}")

    # Append-only: the previous v3-demo artifacts stay listed and loadable.
    old_keys = list(manifest["activeBlueprints"])
    manifest["activeBlueprints"] = new_keys
    manifest_path.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(f"activeBlueprints: {old_keys} -> {new_keys}")

    pool_path = API_ROOT / "docs" / "v3" / "business-logic" / "questions-v3.json"
    pool_path.write_text(json.dumps(build_pool(), ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {pool_path.relative_to(API_ROOT)}")

    meta_path = API_ROOT / "docs" / "assessment" / "QUESTION_METADATA.json"
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    meta = build_metadata(blueprints)
    meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {meta_path.relative_to(API_ROOT)} items={len(meta['items'])}")


if __name__ == "__main__":
    main()

