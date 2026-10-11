"""Build a TEST-ONLY APPROVED copy of the catalog for the isolated demo stand.

This mirrors the `approved` pytest fixture (tests/integration/test_assessment_v3_lifecycle.py):
it copies the shipped catalog and marks the ACTIVE artifacts as approved with
approval.reference = TEST-ONLY-DEMO-STAND, recomputing manifest sha256 hashes.

The published catalog inside the repository is never modified: the copy lives in
demo-stand/catalog and is mounted read-only into the stand's api container.

Run:  python demo-stand/make_approved_catalog.py
"""
from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

STAND_ROOT = Path(__file__).resolve().parents[1]
SOURCE = STAND_ROOT / "services" / "api" / "app" / "data" / "catalog"
TARGET = Path(__file__).resolve().parent / "catalog"
MARKER = "TEST-ONLY-DEMO-STAND"


def main() -> None:
    if not SOURCE.is_dir():
        raise SystemExit(f"catalog source not found: {SOURCE}")
    if TARGET.exists():
        shutil.rmtree(TARGET)
    shutil.copytree(SOURCE, TARGET)

    manifest = json.loads((TARGET / "manifest.json").read_bytes())
    active = set(manifest["activeBlueprints"]) | {manifest["activeCatalog"]}
    approved = []
    for ref in manifest["artifacts"]:
        data = json.loads((TARGET / ref["path"]).read_bytes())
        if ref["key"] not in active and data.get("schemaVersion") != 3:
            continue
        data.update(status="APPROVED", provenance="DS",
                    approval={"reference": MARKER, "approvedBy": "demo-stand-script"})
        raw = json.dumps(data).encode()
        (TARGET / ref["path"]).write_bytes(raw)
        ref["sha256"] = hashlib.sha256(raw).hexdigest()
        approved.append(f'{ref["key"]} ({ref["kind"]}) -> APPROVED')
    (TARGET / "manifest.json").write_text(json.dumps(manifest))
    (TARGET / "TESTONLY-MARKER.txt").write_text(
        f"{MARKER}\n"
        "Synthetic, TEST-ONLY approved content for the isolated demo stand.\n"
        "Never publish, merge or copy into the shipped catalog.\n", encoding="utf-8")
    print("approved (TEST-ONLY):")
    for line in approved:
        print(" ", line)
    print(f"active catalog: {manifest['activeCatalog']}")
    print(f"active blueprints: {', '.join(manifest['activeBlueprints'])}")
    print(f"output: {TARGET}")


if __name__ == "__main__":
    main()
