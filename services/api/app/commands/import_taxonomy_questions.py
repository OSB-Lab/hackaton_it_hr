"""Idempotently import fixed DEMO forms into an already migrated database."""
import json
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import TaxonomyQuestionForm
from app.modules.assessments.taxonomy_bank import load_seed_rows, load_seed_bank, load_bank


def seed_bank(session: Session):
    expected = load_seed_rows()
    load_seed_bank()  # validate completeness/keys/coverage before any DB writes
    existing = {(r.role_id, r.grade_id, r.variant, r.version): r for r in
                session.scalars(select(TaxonomyQuestionForm).with_for_update())}
    for row in expected:
        key = (row['role'], row['grade'], row['variant'], row['version'])
        found = existing.get(key)
        if found:
            if (found.checksum != row['checksum'] or found.questions != row['questions']
                    or found.skill_ids != row['skillIds'] or not found.active):
                raise ValueError('Existing question form differs; refusing overwrite')
        else:
            session.add(TaxonomyQuestionForm(role_id=row['role'], grade_id=row['grade'],
                variant=row['variant'], version=row['version'],
                skill_ids=row['skillIds'], questions=row['questions'], checksum=row['checksum'], active=True))
    session.flush()
    loaded = load_bank(session)
    if loaded.version != expected[0]['version']:
        raise ValueError('Unexpected active bank version')
    return {'version': loaded.version, 'forms': len(expected), 'cells': len(loaded.cells)}


def main():
    with SessionLocal.begin() as session:
        print(json.dumps(seed_bank(session), sort_keys=True))


if __name__ == '__main__':
    main()
