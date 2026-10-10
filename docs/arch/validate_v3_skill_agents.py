#!/usr/bin/env python3
"""Question-level multi-skill synthetic-agent validation for v3 pool.

Agents answer the real generated questions. A deterministic hash samples a
correct answer from the agent's declared per-skill mastery; multi-tag questions
use the minimum tagged mastery, preventing a strong adjacent skill from hiding a
core-skill gap. This is synthetic validation, not population evidence.
"""
from __future__ import annotations
import hashlib, json
from pathlib import Path

POOL = Path(__file__).parent.parent / "business-logic" / "questions-v3.json"
PASS, HIGH, TOTAL = 13, 16, 18

# mastery by skill group: (junior-content, middle-content)
AGENTS = {
 "novice": (.20, .05),
 "backend_junior": (.88, .25),
 "backend_strong_junior": (.96, .48),
 "backend_middle": (.96, .84),
 "backend_api_gap_middle": (.96, .84),
 "frontend_junior": (.88, .25),
 "frontend_strong_junior": (.96, .48),
 "frontend_middle": (.96, .84),
 "frontend_react_gap_middle": (.96, .84),
}
GAP = {"backend_api_gap_middle":"api", "frontend_react_gap_middle":"react"}

def sample(agent: str, question: dict, target_grade: str) -> bool:
    junior, middle = AGENTS[agent]
    p = junior if target_grade == "junior" else middle
    if GAP.get(agent) in question["skillTags"]: p = .10
    # Deterministic, inspectable pseudo-randomness per agent/question.
    u = int(hashlib.sha256(f"{agent}:{question['id']}".encode()).hexdigest()[:8],16) / 2**32
    return u < p

def evaluate(agent: str, cell: str, questions: list[dict]) -> tuple[int, dict[str,float], str]:
    grade = cell.rsplit("-",1)[1]
    technical=[q for q in questions if q["skillTags"] != ["teamwork"]]
    outcomes={q["id"]:sample(agent,q,grade) for q in technical}
    skills=sorted({s for q in technical for s in q["skillTags"]})
    evidence={s:round(100*sum(outcomes[q["id"]] for q in technical if s in q["skillTags"])/sum(s in q["skillTags"] for q in technical),1) for s in skills}
    correct=sum(outcomes.values())
    verdict="high" if correct>=HIGH and min(evidence.values())>=70 else "pass" if correct>=PASS and min(evidence.values())>=50 else "fail"
    return correct,evidence,verdict

def main() -> int:
    pool=json.loads(POOL.read_text())
    failures=[]
    for cell,forms in pool.items():
        spec=cell.split("-",1)[0]
        cohort=["novice",f"{spec}_junior",f"{spec}_strong_junior",f"{spec}_middle",f"{spec}_{'api_gap_middle' if spec=='backend' else 'react_gap_middle'}"]
        print(f"\n{cell}")
        for agent in cohort:
            results=[evaluate(agent,cell,forms[f]) for f in "ABC"]
            verified={r[2] != "fail" for r in results}
            print(f"  {agent:<27}", " ".join(f"{n}/18 {v}" for n,_,v in results))
            if len(verified)!=1: failures.append(f"unstable category {cell}/{agent}: {verified}")
        if cell.endswith("middle"):
            for agent in (f"{spec}_strong_junior",):
                if any(evaluate(agent,cell,forms[f])[2] != "fail" for f in "ABC"): failures.append(f"false positive {cell}/{agent}")
            gap="api" if spec=="backend" else "react"
            for f in "ABC":
                _,ev,v=evaluate(f"{spec}_{'api_gap_middle' if spec=='backend' else 'react_gap_middle'}",cell,forms[f])
                if v != "fail" or ev[gap] >= 50: failures.append(f"core gate missing {cell}/{f}")
    print("\nPASS" if not failures else "\nFAIL\n"+"\n".join(failures))
    return 0 if not failures else 1
if __name__=="__main__": raise SystemExit(main())
