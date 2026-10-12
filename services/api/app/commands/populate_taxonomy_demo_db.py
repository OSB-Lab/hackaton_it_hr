"""Seed an EMPTY, migrated project DB with fixed question forms and synthetic people/needs.

Does not delete schemas, create qualification claims, or generate question text.
"""
import hashlib
import json
import os
from pathlib import Path

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app import models
from app.core.config import get_settings
from app.db.base import Base
from app.db.session import SessionLocal
from app.modules.auth.security import hash_password
from app.modules.recommendations.taxonomy_filter import load_runtime
from app.commands.import_taxonomy_questions import seed_bank

DATA = Path(__file__).resolve().parents[2] / 'tests/fixtures/taxonomy'


def _fixtures(root):
    manifest = json.loads((root/'manifest.v1.json').read_text(encoding='utf-8'))
    raw_candidates = (root/'candidates.v1.jsonl').read_bytes()
    raw_needs = (root/'needs.v1.json').read_bytes()
    for name, raw in (('candidates.v1.jsonl',raw_candidates),('needs.v1.json',raw_needs)):
        if hashlib.sha256(raw).hexdigest() != manifest['hashes'][name]:
            raise ValueError('Synthetic fixture checksum mismatch')
    candidates = [json.loads(line) for line in raw_candidates.splitlines()]
    needs = json.loads(raw_needs)['needs']
    if len(candidates) != 1000 or len(needs) != 50 or manifest['qualificationStatus'] != 'hypothetical_only':
        raise ValueError('Unexpected synthetic fixture population')
    return candidates, needs, manifest


def populate(session: Session, password: str, fixture_dir=DATA):
    if len(password) < 12:
        raise ValueError('Synthetic password must be at least 12 characters')
    if session.scalar(text('SELECT version_num FROM alembic_version')) != '0012':
        raise ValueError('Expected migrated schema 0012')
    # Never merge into pre-existing accounts, companies, needs or attempts.
    for table in Base.metadata.tables.values():
        if table.name != 'taxonomy_question_forms' and session.scalar(select(table.c.id).limit(1)) is not None:
            raise ValueError('Seed requires an empty application database')
    all_candidates, all_needs, manifest = _fixtures(Path(fixture_dir))
    # Small live demo, large reproducible 1000/50 fixtures remain for offline evaluation.
    candidates = all_candidates[:30]
    needs = [all_needs[i] for i in (0, 11, 22, 33, 44)]
    taxonomy, _ = load_runtime()
    role_ids = set(taxonomy.role_edges)
    grade_ids = set(taxonomy.grade_fit)
    if (any({c['roleId'],c['selfDeclaredRoleId']} - role_ids or
            {c['gradeId'],c['selfDeclaredGradeId']} - grade_ids for c in candidates)
            or any(n['roleId'] not in role_ids or n['gradeId'] not in grade_ids for n in needs)):
        raise ValueError('Fixture contains deleted role or grade')
    bank = seed_bank(session)
    if manifest['questionBankVersion'] != bank['version']:
        raise ValueError('Fixture and imported question bank versions disagree')
    shared_hash = hash_password(password)
    users = [models.User(email=f"{c['candidateId']}@demo.example.com", password_hash=shared_hash,
                         role='candidate', is_verified=c['emailVerified']) for c in candidates]
    session.add_all(users)
    session.flush()
    profiles = [models.CandidateProfile(user_id=u.id, full_name=f"Синтетический кандидат {i+1:04}",
        specialization=c['selfDeclaredRoleId'], self_declared_grade=c['selfDeclaredGradeId'],
        professional_role=c['selfDeclaredRoleId'], stack=c['selfDeclaredSkillIds'],
        experience_months=c['experienceYears']*12, soft_skills=[],
        privacy_settings={'publish_profile': c['publicationConsent'], 'show_contacts': False})
        for i,(u,c) in enumerate(zip(users,candidates))]
    session.add_all(profiles)
    session.add_all(models.Consent(user_id=u.id,kind=kind,granted=value)
        for u,c in zip(users,candidates) for kind,value in
        (('privacy',True),('publish_profile',c['publicationConsent'])))
    employer_users = [models.User(email=f"{n['needId']}-employer@demo.example.com",
        password_hash=shared_hash, role='employer', is_verified=True) for n in needs]
    session.add_all(employer_users)
    session.flush()
    companies = [models.Company(user_id=u.id, name=f"Synthetic {n['needId']}",
        description='Изолированный синтетический запрос; не реальный работодатель')
        for u,n in zip(employer_users,needs)]
    session.add_all(companies)
    session.flush()
    session.add_all(models.HiringNeed(company_id=company.id, title=f"Synthetic need {need['needId']}",
        team_description='Синтетическая потребность; квалификация кандидатов не подтверждена',
        specialization=need['roleId'], grade=need['gradeId'], min_grade=need['gradeId'],
        stack=need['requiredSkills'], optional_skills=need['optionalSkills'])
        for company,need in zip(companies,needs))
    session.flush()
    return {'candidates': len(candidates), 'employers': len(needs), 'needs': len(needs),
            'questionForms': bank['forms']}


def main():
    # Explicitly restricted to the known local Compose demo DB. No automatic reset.
    settings = get_settings()
    if os.environ.get('CONFIRM_SYNTHETIC_RESET') != 'RESET_FSP_DEMO_ONLY' or settings.POSTGRES_DB != 'fsp' or settings.POSTGRES_HOST != 'postgres':
        raise SystemExit('Refusing non-demo database or missing confirmation')
    password = os.environ.get('SYNTHETIC_PASSWORD', '')
    with SessionLocal.begin() as session:
        print(json.dumps(populate(session,password),sort_keys=True))


if __name__ == '__main__':
    main()
