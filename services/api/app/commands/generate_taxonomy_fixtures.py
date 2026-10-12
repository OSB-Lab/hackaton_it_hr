"""Deterministic file-only synthetic fixtures; never creates users or certified attempts."""
import argparse
import hashlib
import json
import random
from collections import defaultdict
from pathlib import Path

from app.modules.recommendations.taxonomy_filter import load_runtime
from app.modules.assessments.taxonomy_bank import load_seed_bank

SEED = 20261011
VERSION = 'taxonomy-synthetic-v1'
DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'tests' / 'fixtures' / 'taxonomy'
LOCATIONS = ('Москва', 'Санкт-Петербург', 'Казань', 'Новосибирск')
FORMATS = ('remote', 'hybrid', 'office')


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def generate(out=DEFAULT_OUT):
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    taxonomy, _ = load_runtime()
    bank = load_seed_bank()
    rng = random.Random(SEED)
    roles = list(taxonomy.role_edges)
    grades = list(taxonomy.grade_fit)
    candidates = []
    for i in range(1000):
        role = roles[i % len(roles)]
        grade = grades[(i // len(roles)) % len(grades)]
        skill_ids = bank.cell(role, grade).skillIds
        strength = ('weak', 'typical', 'strong')[(i // (len(roles) * len(grades))) % 3]
        base = 19 + 13 * grades.index(grade) + {'weak': -11, 'typical': 0, 'strong': 12}[strength]
        levels = {skill: max(0, min(100, base + rng.randint(-15, 15))) for skill in skill_ids}
        # Non-role skills are plausible CV claims, not assessment evidence.
        adjacent = roles[(i + 1) % len(roles)]
        claimed = sorted(set(rng.sample(list(skill_ids), min(4, len(skill_ids))) +
                             list(bank.cell(adjacent, grade).skillIds[:2])))
        fsp = ([{'recordId': f'syn-result-{i+1:04}', 'kind': 'competition_result',
                 'result': ('winner', 'prizewinner', 'finalist')[i % 3],
                 'role': ('lead', 'contributor', 'participant')[i % 3],
                 'skillIds': list(skill_ids[:2]), 'achievedAt': f'{2021+i%5}-06-01',
                 'source': 'synthetic-not-fsp'}] if i % 5 == 0 else [])
        candidates.append(dict(candidateId=f'syn-c{i+1:04}', roleId=role, gradeId=grade,
            personaStrength=strength, skillLevels=levels, qualificationStatus='hypothetical_only',
            selfDeclaredRoleId=adjacent if i % 7 == 0 else role,
            selfDeclaredGradeId=grades[(grades.index(grade)+1)%len(grades)] if i % 9 == 0 else grade,
            selfDeclaredSkillIds=claimed, experienceYears=i % 11,
            salaryExpectationRub=85000 + (i % 9)*33000,
            workFormats=[FORMATS[i % len(FORMATS)]], locations=[LOCATIONS[i % len(LOCATIONS)]],
            emailVerified=i % 31 != 0, publicationConsent=i % 29 != 0,
            syntheticFspAchievements=fsp, responseSeed=rng.randrange(2**31)))
    needs = []
    for i in range(50):
        role = roles[i % len(roles)]
        grade = grades[(i // len(roles)) % len(grades)]
        skills = list(bank.cell(role, grade).skillIds)
        required = rng.sample(skills, min(3, len(skills)))
        optional = rng.sample([s for s in skills if s not in required], min(2, len(skills)-len(required)))
        budget = 190000 + (i % 5) * 42000
        # An independent, declared synthetic relevance rule; not API ranking output.
        relevant = []
        for c in candidates:
            role_fit = 1 if c['roleId'] == role else float(taxonomy.role_edges[c['roleId']].get(role, 0))
            grade_fit = float(taxonomy.grade_fit[c['gradeId']][grade])
            skill_mean = sum(c['skillLevels'].get(s, 0) for s in required) / len(required)
            if (c['emailVerified'] and c['publicationConsent'] and role_fit >= .72
                    and grade_fit >= .8 and skill_mean >= 60
                    and c['salaryExpectationRub'] <= budget * 1.2):
                relevant.append(c['candidateId'])
        needs.append(dict(needId=f'syn-n{i+1:03}', roleId=role, gradeId=grade,
            requiredSkills=required, optionalSkills=optional, minExperienceYears=i % 6,
            salaryBudgetMaxRub=budget, workFormat=FORMATS[i % len(FORMATS)],
            location=LOCATIONS[i % len(LOCATIONS)], hardSkillIds=required[:1] if i % 4 == 0 else [],
            expectedRelevantIds=relevant))
    paths = {'candidates.v1.jsonl': ''.join(_json(row)+'\n' for row in candidates),
             'needs.v1.json': _json({'version': VERSION, 'needs': needs})+'\n'}
    manifest = {'version': VERSION, 'seed': SEED, 'candidateCount': len(candidates),
                'needCount': len(needs), 'questionBankVersion': bank.version,
                'qualificationStatus': 'hypothetical_only',
                'hashes': {name: hashlib.sha256(content.encode('utf-8')).hexdigest()
                           for name, content in paths.items()}}
    paths['manifest.v1.json'] = _json(manifest)+'\n'
    for name, content in paths.items():
        (root / name).write_text(content, encoding='utf-8')
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(_json(generate(args.out)))


if __name__ == '__main__':
    main()
