import hashlib
import json
import shutil
from copy import deepcopy

import pytest
from pydantic import ValidationError

from app.commands.seed_demo import _read_json
from app.modules.catalog.public import PublicQuestion, PublicVariant, public_variant
from app.modules.catalog.repository import CatalogRepository, DATA_ROOT, Loaded, decode
from app.modules.catalog.schemas import Blueprint, Catalog
from app.modules.catalog.validators import validate_grade, validate_skills, validate_specialization


@pytest.fixture
def repo():
    return CatalogRepository()


@pytest.fixture
def bundle(tmp_path):
    root = tmp_path / "catalog"
    shutil.copytree(DATA_ROOT, root)
    return root


def raw_blueprint(repo):
    return repo.blueprint("backend-junior-v1-demo").document.model_dump(mode="json")


def write_json(path, data):
    raw = (json.dumps(data, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def test_bundle_coverage_and_equivalence(repo):
    repo.validate_all()
    pairs = set()
    for key in repo.manifest.activeBlueprints:
        loaded = repo.blueprint(key)
        bp = loaded.document
        pairs.add((bp.specialization, bp.grade))
        assert len(loaded.checksum) == 64
        assert {v.id for v in bp.variants} == {"A", "B", "C"}
        assert all({q.slotId for q in v.questions} == {s.id for s in bp.slots} for v in bp.variants)
    assert pairs == {(s, g) for s in ("backend", "frontend", "fullstack") for g in ("junior", "middle", "senior")}
    with pytest.raises(ValidationError):
        repo.catalog().document.version = "changed"
    with pytest.raises(ValidationError):
        repo.blueprint(repo.manifest.activeBlueprints[0]).document.slots[0].weight = 9.0


@pytest.mark.parametrize("key", ["backend-junior-v1-demo", "backend-middle-v1-demo", "frontend-junior-v1-demo", "frontend-middle-v1-demo"])
@pytest.mark.parametrize("variant", ["A", "B"])
def test_public_projection_does_not_leak(repo, key, variant):
    loaded = repo.blueprint(key)
    public = public_variant(loaded, variant)
    data = public.model_dump(mode="json")
    text = public.model_dump_json()
    for forbidden in ("answerKey", "rubric", "scoring", "thresholds", "correctFraction", "optionId", "weight", "maxScore", "checksum"):
        assert forbidden not in text
    assert data["variant"] == variant
    assert "answerKey" not in PublicQuestion.model_fields
    assert "scoring" not in PublicVariant.model_fields
    assert len(data["questions"]) == len(loaded.document.slots)
    other = next(v for v in loaded.document.variants if v.id != variant)
    assert all(q.id not in text for q in other.questions)
    with pytest.raises(ValidationError):
        PublicQuestion.model_validate_json(json.dumps({**data["questions"][0], "answerKey": {"optionId": "o1"}}))


@pytest.mark.parametrize("variant", ["A", "B"])
def test_public_output_independent_of_correct_option_and_scoring(repo, variant):
    loaded = repo.blueprint("backend-junior-v1-demo")
    original = public_variant(loaded, variant)
    internal = loaded.document.model_dump(mode="json")
    for item in internal["variants"]:
        for question in item["questions"]:
            old_key = question["answerKey"]["optionId"]
            question["answerKey"]["optionId"] = next(
                option["id"] for option in question["options"] if option["id"] != old_key
            )
    internal["rubric"][0]["incorrectFraction"] = 0.25
    internal["slots"][0]["weight"] = 3.0
    internal["scoring"]["thresholds"]["passScore"] = 60.0
    changed = Loaded(decode(Blueprint, json.dumps(internal)), "internal-checksum-not-public")
    projected = public_variant(changed, variant)
    assert projected == original
    assert projected.model_dump_json() == original.model_dump_json()


@pytest.mark.parametrize("case", [
    "missing_b", "third_variant", "duplicate_a", "missing_slot", "duplicate_slot", "unknown_slot",
    "missing_rubric", "unknown_rubric", "missing_thresholds", "missing_high", "reversed_thresholds",
    "out_of_range", "nan", "negative_weight", "zero_max", "unknown_type", "bad_key",
    "duplicate_option", "duplicate_question", "variant_override", "unknown_formula",
])
def test_invalid_blueprints_rejected(repo, case):
    bp = raw_blueprint(repo)
    if case == "missing_b": bp["variants"].pop()
    elif case == "third_variant": bp["variants"].append(deepcopy(bp["variants"][0]))
    elif case == "duplicate_a": bp["variants"][1]["id"] = "A"
    elif case == "missing_slot": bp["variants"][1]["questions"].pop()
    elif case == "duplicate_slot": bp["variants"][1]["questions"][1]["slotId"] = "slot-1"
    elif case == "unknown_slot": bp["variants"][1]["questions"][0]["slotId"] = "unknown"
    elif case == "missing_rubric": del bp["rubric"]
    elif case == "unknown_rubric": bp["slots"][0]["rubricId"] = "missing"
    elif case == "missing_thresholds": del bp["scoring"]["thresholds"]
    elif case == "missing_high": del bp["scoring"]["thresholds"]["highScore"]
    elif case == "reversed_thresholds": bp["scoring"]["thresholds"]["passScore"] = 101
    elif case == "out_of_range": bp["scoring"]["thresholds"]["highScore"] = 101
    elif case == "nan": bp["scoring"]["thresholds"]["passScore"] = float("nan")
    elif case == "negative_weight": bp["slots"][0]["weight"] = -1
    elif case == "zero_max": bp["slots"][0]["maxScore"] = 0
    elif case == "unknown_type": bp["variants"][0]["questions"][0]["type"] = "essay"
    elif case == "bad_key": bp["variants"][0]["questions"][0]["answerKey"]["optionId"] = "missing"
    elif case == "duplicate_option": bp["variants"][0]["questions"][0]["options"][1]["id"] = "o1"
    elif case == "duplicate_question": bp["variants"][1]["questions"][0]["id"] = bp["variants"][0]["questions"][0]["id"]
    elif case == "variant_override": bp["variants"][1]["rubric"] = []
    elif case == "unknown_formula": bp["scoring"]["formula"] = "execute_python"
    with pytest.raises(ValueError):
        decode(Blueprint, json.dumps(bp))


@pytest.mark.parametrize("case", ["duplicate_skill", "unknown_skill", "duplicate_order"])
def test_invalid_catalog(repo, case):
    cat = repo.catalog().document.model_dump(mode="json")
    if case == "duplicate_skill": cat["skills"].append(cat["skills"][0])
    elif case == "unknown_skill": cat["specializations"][0]["skillIds"].append("missing")
    elif case == "duplicate_order": cat["grades"][1]["order"] = 0
    with pytest.raises(ValueError):
        decode(Catalog, json.dumps(cat))


def test_seed_compatibility_and_shared_validators(repo):
    catalog = repo.catalog().document
    old = _read_json("catalog.json")
    assert old["grades"] == ["junior", "middle", "senior"]
    assert old["competencies"] == [s.id for s in catalog.skills]
    assert validate_specialization(catalog, "backend") == "backend"
    assert validate_grade(catalog, "junior") == "junior"
    validate_skills(catalog, ["python", "sql"], "backend")
    for action in (lambda: validate_grade(catalog, "invented"),
                   lambda: validate_specialization(catalog, "invented"),
                   lambda: validate_skills(catalog, ["invented"]),
                   lambda: validate_skills(catalog, ["react"], "backend")):
        with pytest.raises(ValueError): action()


@pytest.mark.parametrize("case", ["checksum", "path", "identity", "catalog_version", "skill"])
def test_loader_rejects_invalid_bundle(bundle, case):
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text())
    ref = manifest["artifacts"][1]
    path = bundle / ref["path"]
    bp = json.loads(path.read_text())
    if case == "checksum": path.write_bytes(path.read_bytes() + b" ")
    elif case == "path": ref["path"] = "../escape.json"
    else:
        if case == "identity": bp["version"] = "wrong-version"
        elif case == "catalog_version": bp["catalogVersion"] = "missing-version"
        elif case == "skill": bp["slots"][0]["skillId"] = "react"
        ref["sha256"] = write_json(path, bp)
    write_json(manifest_path, manifest)
    with pytest.raises(ValueError): CatalogRepository(bundle).blueprint(ref["key"])


def test_explicit_version_survives_active_switch(bundle):
    repo = CatalogRepository(bundle)
    old = repo.catalog()
    manifest = json.loads((bundle / "manifest.json").read_text())
    newer = old.document.model_dump(mode="json")
    newer["version"] = "v2-demo"
    digest = write_json(bundle / "catalog-v2.json", newer)
    manifest["artifacts"].append({"key": "catalog-v2-demo", "kind": "catalog", "id": newer["id"], "version": newer["version"], "path": "catalog-v2.json", "sha256": digest})
    manifest["activeCatalog"] = "catalog-v2-demo"
    manifest["activeBlueprints"] = []
    write_json(bundle / "manifest.json", manifest)
    switched = CatalogRepository(bundle)
    switched.validate_all()
    assert switched.catalog().document.version == "v2-demo"
    assert switched.catalog(old.document.version) == old
    assert switched.blueprint(repo.manifest.activeBlueprints[0]).document.catalogVersion == "v3"
    with pytest.raises(ValueError): switched.catalog("unknown")
    with pytest.raises(ValueError): switched.blueprint("unknown")


def test_duplicate_json_keys_rejected():
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        decode(Catalog, '{"schemaVersion":1,"schemaVersion":1}')
