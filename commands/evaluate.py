"""Offline ranking evaluation; no database, synthetic labels or fallback ranking."""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def evaluate(fixtures=None, labels=None, command=None):
    missing = [name for name, value in (("versioned fixtures", fixtures),
               ("independent relevance labels", labels), ("ranking adapter", command)) if not value]
    if missing:
        return {"status": "BLOCKED", "reason": "Missing: " + ", ".join(missing),
                "precisionAt3": None, "scenarios": "NOT_RUN",
                "variantComparison": "NOT_RUN", "determinism": "NOT_RUN"}
    data, truth = [json.loads(Path(p).read_text(encoding="utf-8")) for p in (fixtures, labels)]
    if data["schemaVersion"] != 1 or truth["schemaVersion"] != 1:
        raise ValueError("Unsupported schemaVersion")
    if not data["version"] or truth["fixtureVersion"] != data["version"] or not truth["version"]:
        raise ValueError("Version mismatch")
    provenance = truth["provenance"]
    if provenance.get("independentOfTuning") is not True or not provenance.get("reference"):
        raise ValueError("Independent held-out label provenance required")
    cases = data["cases"]
    if not isinstance(data["blueprintVersions"], list) or not data["blueprintVersions"]:
        raise ValueError("blueprintVersions required")
    if not cases or len({c["id"] for c in cases}) != len(cases):
        raise ValueError("Cases must be nonempty and unique")
    if set(truth["labels"]) != {c["id"] for c in cases}:
        raise ValueError("Labels must cover exactly the fixture cases")
    rows, versions = [], set()
    for case in cases:
        candidates = case["candidateIds"]
        if (case["scenario"] not in {"weak", "medium", "strong"}
                or not isinstance(case["profileId"], str) or not case["profileId"]
                or not isinstance(case["input"], dict)
                or not isinstance(candidates, list)
                or any(not isinstance(c, str) or not c for c in candidates)):
            raise ValueError("Invalid scenario/profile/input/candidate IDs")
        if len(candidates) < 3 or len(set(candidates)) != len(candidates):
            raise ValueError("At least three unique candidate IDs required")
        known = truth["labels"][case["id"]]
        if set(known) != set(candidates) or any(type(v) is not bool for v in known.values()):
            raise ValueError("Explicit boolean label required for every candidate")
        results = []
        for _ in range(3):
            run = subprocess.run(command, input=json.dumps(case["input"]), text=True,
                                 capture_output=True, timeout=120, check=True, encoding="utf-8")
            result = json.loads(run.stdout)
            if not result["algorithmVersion"]:
                raise ValueError("algorithmVersion required")
            order = result["orderedCandidateIds"]
            if len(order) != len(set(order)) or not set(order) <= set(candidates):
                raise ValueError("Invalid ranked candidate IDs")
            versions.add(result["algorithmVersion"])
            results.append(result)
        if results[1:] != results[:1] * 2:
            raise ValueError("Non-deterministic ranking output")
        rows.append({"id": case["id"], "scenario": case["scenario"],
                     "profileId": case["profileId"], "variant": case.get("variant"),
                     "precisionAt3": sum(known[c] for c in order[:3]) / 3,
                     "orderedCandidateIds": order})
    if len(versions) != 1:
        raise ValueError("Algorithm version changed during evaluation")
    pairs = []
    for profile in sorted({r["profileId"] for r in rows}):
        group = [r for r in rows if r["profileId"] == profile and r["variant"]]
        if len({r["variant"] for r in group}) >= 2:
            pairs.append({"profileId": profile, "results": group,
                          "sameOrder": all(r["orderedCandidateIds"] == group[0]["orderedCandidateIds"] for r in group)})
    absent = sorted({"weak", "medium", "strong"} - {r["scenario"] for r in rows})
    return {"status": "BLOCKED" if absent or not pairs else "PASS",
            "reason": "Missing scenarios: " + str(absent) + "; paired variants: " + str(bool(pairs)),
            "fixtureVersion": data["version"], "labelVersion": truth["version"],
            "fixtureSha256": digest(fixtures), "labelSha256": digest(labels),
            "algorithmVersion": next(iter(versions)), "blueprintVersions": data["blueprintVersions"],
            "precisionAt3": sum(r["precisionAt3"] for r in rows) / len(rows),
            "scenarios": rows, "variantComparison": pairs or "BLOCKED", "determinism": "PASS",
            "note": "PASS means evaluation executed, not production accuracy or quality acceptance."}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixtures")
    parser.add_argument("--labels")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--ranking-command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    try:
        report = evaluate(args.fixtures, args.labels, args.ranking_command)
    except (ValueError, KeyError, TypeError, OSError, subprocess.SubprocessError) as exc:
        report = {"status": "FAIL", "error": str(exc), "precisionAt3": None}
    raw = json.dumps(report, ensure_ascii=False, indent=2)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(raw + "\n", encoding="utf-8")
    print(raw)
    print(f"Evaluation: {report['status']}; Precision@3={report.get('precisionAt3')}", file=sys.stderr)
    return {"PASS": 0, "FAIL": 1, "BLOCKED": 2}[report["status"]]


if __name__ == "__main__":
    raise SystemExit(main())
