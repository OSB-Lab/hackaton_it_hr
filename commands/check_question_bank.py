#!/usr/bin/env python3
"""Catalog question-bank quality gate for ФСП | ИТ-подбор.

Standalone, read-only QA tool. It never imports the application, never writes to
the catalog and never changes production behaviour.

It reports two classes of findings:

* **error** — violations of the LOCKED structural contract, broken manifest or
  integrity problems (duplicate prompts/options, bad answer keys, missing
  blueprints, insufficient evidence). These fail the gate.
* **warning** — heuristics that need a human decision (near-duplicate wording,
  obviously absurd distractors, answer-position skew, option-length bias).

Heuristics are NOT a quality measurement: technical correctness, distractor
plausibility and real item difficulty must be judged by expert review.

Usage::

    python commands/check_question_bank.py [--catalog services/api/app/data/catalog]
                                           [--out report.json] [--quiet]
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import itertools
import json
import re
import sys
import unicodedata
from pathlib import Path

EXPECTED_CELLS = {(spec, grade) for spec in ("backend", "frontend")
                  for grade in ("junior", "middle")}
CORE_TAGS = {"backend": ("python", "sql", "api"),
             "frontend": ("javascript", "typescript", "react")}
QUESTIONS_PER_VARIANT = 20
EVIDENCE_OBSERVATIONS_PER_CORE = 9
TEAMWORK_OBSERVATIONS = 2
NEAR_DUPLICATE_THRESHOLD = 0.80
POSITION_TOLERANCE = 0.45          # max |share - 0.25| before warning
LONG_OPTION_RATIO = 1.65           # correct option vs mean distractor length

# Distractors that are not plausible mistakes for any seniority level.
ABSURD_DISTRACTORS = (
    "хранить ключи в ui", "повторять запрос бесконечно", "отключить типы",
    "скрыть ошибку", "обвинить коллегу", "молчать до дедлайна", "удалить задачу",
    "зависит от css", "выключить компьютер", "отключить интернет",
)
TOKEN_RE = re.compile(r"[A-Za-zА-Яа-яЁё0-9_]+")
# Internal schema words must never appear in candidate-visible text: the public
# projection is asserted leak-free, and such options are meaningless anyway.
INTERNAL_WORDS = ("answerkey", "optionid", "slotid", "maxscore", "rubricid", "checksum")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", unicodedata.normalize("NFKC", text or "").casefold()).strip()


def tokens(text: str) -> set[str]:
    return {t for t in TOKEN_RE.findall(normalize(text)) if len(t) > 2}


def jaccard(left: set[str], right: set[str]) -> float:
    return len(left & right) / len(left | right) if left and right else 0.0


class Report:
    def __init__(self) -> None:
        self.findings: list[dict] = []
        self.stats: dict = {}

    def add(self, severity: str, code: str, message: str, **extra) -> None:
        self.findings.append({"severity": severity, "code": code, "message": message, **extra})

    @property
    def errors(self) -> list[dict]:
        return [f for f in self.findings if f["severity"] == "error"]

    @property
    def warnings(self) -> list[dict]:
        return [f for f in self.findings if f["severity"] == "warning"]


def load_manifest(catalog: Path, report: Report) -> dict | None:
    path = catalog / "manifest.json"
    if not path.exists():
        report.add("error", "manifest_missing", f"manifest not found: {path}")
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        report.add("error", "manifest_corrupt", f"manifest is not valid JSON: {exc}")
        return None


def check_artifacts(catalog: Path, manifest: dict, report: Report) -> dict[str, dict]:
    documents: dict[str, dict] = {}
    for ref in manifest.get("artifacts", []):
        path = catalog / ref.get("path", "")
        if not path.exists():
            report.add("error", "artifact_missing", f"artifact file missing: {ref.get('path')}",
                       key=ref.get("key"))
            continue
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != ref.get("sha256"):
            report.add("error", "artifact_checksum",
                       f"sha256 mismatch for {ref.get('key')}",
                       key=ref.get("key"), expected=ref.get("sha256"), actual=digest)
            continue
        try:
            documents[ref["key"]] = json.loads(raw)
        except ValueError as exc:
            report.add("error", "artifact_json",
                       f"artifact is not valid JSON: {ref.get('key')} ({exc})", key=ref.get("key"))
    return documents


def active_blueprints(manifest: dict, documents: dict, report: Report) -> dict[tuple, dict]:
    active: dict[tuple, dict] = {}
    refs = {r["key"]: r for r in manifest.get("artifacts", [])}
    for key in manifest.get("activeBlueprints", []):
        ref = refs.get(key)
        if ref is None:
            report.add("error", "active_unknown", f"active blueprint key not in artifacts: {key}", key=key)
            continue
        document = documents.get(key)
        if document is None:
            continue
        cell = (document.get("specialization"), document.get("grade"))
        if cell in active:
            report.add("error", "active_duplicate_cell",
                       f"two active blueprints for {cell}", key=key)
        active[cell] = {"key": key, "ref": ref, "document": document}
    missing = EXPECTED_CELLS - set(active)
    if missing:
        report.add("error", "blueprint_missing",
                   f"no active blueprint for: {sorted(missing)}")
    extra = set(active) - EXPECTED_CELLS
    if extra:
        report.add("warning", "blueprint_unexpected",
                   f"active blueprint outside the MVP matrix: {sorted(extra)}")
    return active


def structural_checks(active: dict[tuple, dict], report: Report) -> list[dict]:
    """LOCKED contract checks; returns flattened questions for content checks."""
    flat: list[dict] = []
    ids_seen: dict[str, str] = {}
    for (spec, grade), entry in sorted(active.items()):
        document = entry["document"]
        key = entry["key"]
        if document.get("schemaVersion") != 3:
            report.add("error", "schema_version", f"{key}: expected schemaVersion 3", key=key)
            continue
        slots = document.get("slots") or []
        rubric_ids = {r.get("id") for r in document.get("rubric") or []}
        expected_matrix = collections.Counter()
        for tag in CORE_TAGS[spec]:
            expected_matrix[frozenset([tag])] = 4
        for pair in itertools.combinations(CORE_TAGS[spec], 2):
            expected_matrix[frozenset(pair)] = 1
        expected_matrix[frozenset(CORE_TAGS[spec])] = 3
        expected_matrix[frozenset(["teamwork"])] = TEAMWORK_OBSERVATIONS
        matrix = collections.Counter(frozenset(s.get("skillTags") or []) for s in slots)
        if len(slots) != QUESTIONS_PER_VARIANT:
            report.add("error", "slot_count", f"{key}: {len(slots)} slots, expected {QUESTIONS_PER_VARIANT}", key=key)
        if matrix != expected_matrix:
            report.add("error", "tag_matrix", f"{key}: slot tag matrix differs from the locked matrix",
                       key=key, actual={"+".join(sorted(k)): v for k, v in matrix.items()})
        for slot in slots:
            if slot.get("rubricId") not in rubric_ids:
                report.add("error", "slot_rubric", f"{key}/{slot.get('id')}: unknown rubricId", key=key)
            if slot.get("maxScore") != 1.0 or slot.get("weight") != 1.0:
                report.add("error", "slot_scoring", f"{key}/{slot.get('id')}: maxScore/weight must be 1.0", key=key)

        variants = document.get("variants") or []
        if {v.get("id") for v in variants} != {"A", "B", "C"}:
            report.add("error", "variant_set", f"{key}: variants must be exactly A/B/C", key=key)
        slot_ids = {s.get("id"): frozenset(s.get("skillTags") or []) for s in slots}
        for variant in variants:
            questions = variant.get("questions") or []
            if len(questions) != QUESTIONS_PER_VARIANT:
                report.add("error", "variant_length",
                           f"{key}/{variant.get('id')}: {len(questions)} questions, expected {QUESTIONS_PER_VARIANT}",
                           key=key)
            covered = [q.get("slotId") for q in questions]
            if sorted(covered) != sorted(slot_ids):
                report.add("error", "variant_slots",
                           f"{key}/{variant.get('id')}: slots are not covered exactly once", key=key)
            for question in questions:
                qid = question.get("id")
                cell = f"{key}/{variant.get('id')}"
                if qid in ids_seen:
                    report.add("error", "duplicate_question_id",
                               f"{qid} appears twice ({ids_seen[qid]} and {cell})", key=key, question=qid)
                ids_seen[qid] = cell
                options = question.get("options") or []
                texts = [normalize(o.get("text")) for o in options]
                if len(options) != 4:
                    report.add("error", "option_count", f"{qid}: {len(options)} options, expected 4",
                               key=key, question=qid)
                if len(set(texts)) != len(texts):
                    report.add("error", "duplicate_option_text",
                               f"{qid}: repeated option text", key=key, question=qid)
                answer = (question.get("answerKey") or {}).get("optionId")
                if answer not in {o.get("id") for o in options}:
                    report.add("error", "answer_key", f"{qid}: answerKey does not reference an option",
                               key=key, question=qid)
                if frozenset(question.get("skillTags") or []) != slot_ids.get(question.get("slotId")):
                    report.add("error", "question_tags", f"{qid}: tags differ from its slot", key=key, question=qid)
                flat.append({"cell": (spec, grade), "key": key, "variant": variant.get("id"),
                             "slotId": question.get("slotId"), "id": qid,
                             "skillTags": tuple(question.get("skillTags") or ()),
                             "prompt": question.get("prompt"),
                             "options": [(o.get("id"), o.get("text")) for o in options],
                             "answerKey": answer})
    # evidence: each core skill must be observable exactly nine times per variant
    for (spec, grade), entry in sorted(active.items()):
        key = entry["key"]
        for variant in entry["document"].get("variants") or []:
            counts = collections.Counter(tag for q in variant.get("questions") or []
                                         for tag in (q.get("skillTags") or []))
            for tag in CORE_TAGS[spec]:
                if counts.get(tag) != EVIDENCE_OBSERVATIONS_PER_CORE:
                    report.add("error", "evidence_count",
                               f"{key}/{variant.get('id')}: {tag} has {counts.get(tag)} observations, "
                               f"expected {EVIDENCE_OBSERVATIONS_PER_CORE}", key=key)
            if counts.get("teamwork") != TEAMWORK_OBSERVATIONS:
                report.add("error", "evidence_count",
                           f"{key}/{variant.get('id')}: teamwork has {counts.get('teamwork')} observations",
                           key=key)
    report.stats["questions"] = len(flat)
    report.stats["uniquePrompts"] = len({normalize(q["prompt"]) for q in flat})
    report.stats["cells"] = {f"{s}-{g}": sum(1 for q in flat if q["cell"] == (s, g)) for s, g in sorted(active)}
    return flat


def content_checks(flat: list[dict], report: Report) -> None:
    by_prompt: dict[str, list[dict]] = {}
    for question in flat:
        by_prompt.setdefault(normalize(question["prompt"]), []).append(question)

    for prompt, group in by_prompt.items():
        variants = {(q["cell"], q["variant"]) for q in group}
        cells = {q["cell"] for q in group}
        if len(group) > 1 and len(cells) == 1 and len(variants) > 1:
            report.add("error", "duplicate_prompt_across_forms",
                       f"same wording used in several forms of one cell: {group[0]['id']}",
                       prompt=group[0]["prompt"], ids=[q["id"] for q in group])
        elif len(group) > 1 and len(cells) < len(group):
            same_cell = [q for q in group if q["cell"] == group[0]["cell"]]
            if len(same_cell) > 1:
                report.add("error", "duplicate_prompt_in_form",
                           f"wording repeats inside one form: {group[0]['id']}",
                           prompt=group[0]["prompt"], ids=[q["id"] for q in same_cell])
            else:
                report.add("warning", "prompt_reused_across_cells",
                           f"wording shared between cells: {group[0]['id']}",
                           prompt=group[0]["prompt"], ids=[q["id"] for q in group])
        elif len(group) > 1:
            report.add("error", "duplicate_prompt_in_form",
                       f"wording repeats inside one form: {group[0]['id']}",
                       prompt=group[0]["prompt"], ids=[q["id"] for q in group])

    for cell in sorted({q["cell"] for q in flat}):
        variant_sets = {}
        for variant in ("A", "B", "C"):
            variant_sets[variant] = {normalize(q["prompt"]) for q in flat
                                     if q["cell"] == cell and q["variant"] == variant}
        for left, right in itertools.combinations(("A", "B", "C"), 2):
            overlap = variant_sets[left] & variant_sets[right]
            if overlap:
                report.add("error", "form_overlap",
                           f"{cell}: forms {left} and {right} share {len(overlap)} wordings",
                           cell=f"{cell[0]}-{cell[1]}", count=len(overlap))

    # near duplicates inside a cell across different forms
    for cell in sorted({q["cell"] for q in flat}):
        rows = [q for q in flat if q["cell"] == cell]
        for left, right in itertools.combinations(rows, 2):
            if left["variant"] == right["variant"] or left["slotId"] == right["slotId"]:
                continue
            score = jaccard(tokens(left["prompt"]), tokens(right["prompt"]))
            if score >= NEAR_DUPLICATE_THRESHOLD:
                report.add("warning", "near_duplicate_prompt",
                           f"{left['id']} ~ {right['id']} (similarity {score:.2f})",
                           ids=[left["id"], right["id"]])

    positions = collections.Counter()
    for question in flat:
        option_ids = [oid for oid, _ in question["options"]]
        if question["answerKey"] in option_ids:
            positions[option_ids.index(question["answerKey"]) + 1] += 1
        texts = [text for _, text in question["options"]]
        correct = next((t for oid, t in question["options"] if oid == question["answerKey"]), None)
        if correct is not None and len(texts) == 4:
            others = [len(t) for oid, t in question["options"] if oid != question["answerKey"]]
            mean_other = sum(others) / len(others) if others else 0
            if mean_other and len(correct) > LONG_OPTION_RATIO * mean_other:
                report.add("warning", "option_length_bias",
                           f"{question['id']}: correct option is much longer than distractors",
                           question=question["id"])
        for _, text in question["options"]:
            if normalize(text) in ABSURD_DISTRACTORS:
                report.add("warning", "implausible_distractor",
                           f"{question['id']}: implausible distractor «{text}»",
                           question=question["id"])
            lowered = normalize(text)
            if any(word in lowered for word in INTERNAL_WORDS):
                report.add("error", "internal_name_leak",
                           f"{question['id']}: option text exposes an internal schema name: «{text}»",
                           question=question["id"])
            if any(word in normalize(question["prompt"]) for word in INTERNAL_WORDS):
                report.add("error", "internal_name_leak",
                           f"{question['id']}: prompt exposes an internal schema name",
                           question=question["id"])

    total = sum(positions.values()) or 1
    report.stats["answerPositions"] = dict(sorted(positions.items()))
    for position, count in positions.items():
        share = count / total
        if abs(share - 0.25) > POSITION_TOLERANCE:
            report.add("warning", "answer_position_skew",
                       f"position {position} holds {share:.0%} of correct answers")


def run(catalog: Path) -> Report:
    report = Report()
    manifest = load_manifest(catalog, report)
    if manifest is None:
        return report
    documents = check_artifacts(catalog, manifest, report)
    active = active_blueprints(manifest, documents, report)
    if active:
        flat = structural_checks(active, report)
        content_checks(flat, report)
    report.stats["activeBlueprints"] = sorted(active)
    report.stats["artifactCount"] = len(manifest.get("artifacts", []))
    return report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--catalog", type=Path,
                        default=Path("services/api/app/data/catalog"))
    parser.add_argument("--out", type=Path)
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    report = run(args.catalog)
    payload = {"catalog": str(args.catalog), "stats": report.stats,
               "errors": report.errors, "warnings": report.warnings}
    if not args.quiet:
        print(f"catalog={args.catalog}")
        for name, value in report.stats.items():
            print(f"  {name}={value}")
        for finding in report.errors:
            print(f"ERROR   {finding['code']}: {finding['message']}")
        for finding in report.warnings:
            print(f"WARNING {finding['code']}: {finding['message']}")
        print(f"summary: {len(report.errors)} errors, {len(report.warnings)} warnings")
    if args.out:
        args.out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"report written to {args.out}")
    return 1 if report.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())




