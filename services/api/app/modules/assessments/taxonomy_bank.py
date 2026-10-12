"""Read fixed A/B/C question forms from PostgreSQL. No question generation here."""
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
import hashlib
import json

from sqlalchemy import select

from app.models import TaxonomyQuestionForm
from app.modules.recommendations.taxonomy_filter import load_runtime

DATA = Path(__file__).resolve().parents[2] / 'data' / 'taxonomy'


@dataclass(frozen=True)
class Option:
    id: str
    text: str


@dataclass(frozen=True)
class Question:
    id: str
    skillTags: tuple[str, ...]
    prompt: str
    options: tuple[Option, ...]
    answerKey: str


@dataclass(frozen=True)
class Form:
    id: str
    questions: tuple[Question, ...]


@dataclass(frozen=True)
class Cell:
    role: str
    grade: str
    skillIds: tuple[str, ...]
    forms: tuple[Form, ...]
    version: str = ''


@dataclass(frozen=True)
class Bank:
    cells: dict[tuple[str, str], Cell]
    version: str

    def cell(self, role, grade) -> Cell:
        return self.cells[(role, grade)]


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':')).encode()


def public_form(form: Form) -> list[dict]:
    return [{'id': q.id, 'prompt': q.prompt,
             'options': [{'id': o.id, 'text': o.text} for o in q.options]} for q in form.questions]


def _bank(rows):
    taxonomy, _ = load_runtime()
    skills = json.loads((Path(__file__).resolve().parents[1] / 'recommendations/config/skills.v1.json').read_text())['skills']
    core = json.loads((Path(__file__).resolve().parents[1] / 'recommendations/config/assessment-core.v1.json').read_text())
    if set(core['roles']) != set(taxonomy.role_edges):
        raise ValueError('Invalid assessment scope')
    wanted = {role: tuple(core['roles'][role]) for role in taxonomy.role_edges}
    linked = {role: {s['id'] for s in skills if role in s['role_ids']} for role in taxonomy.role_edges}
    if any(len(ids) != 5 or len(set(ids)) != 5 or not set(ids) <= linked[role] for role, ids in wanted.items()):
        raise ValueError('Core assessment skills must be five distinct role skills')
    expected = {(role, grade) for role in taxonomy.role_edges for grade in taxonomy.grade_fit}
    grouped = {}
    version = None
    for row in rows:
        role, grade, variant = row['role'], row['grade'], row['variant']
        if (role, grade) not in expected or variant not in ('A','B','C'):
            raise ValueError('Question row outside active taxonomy or unapproved status')
        if version is not None and version != row['version']:
            raise ValueError('Mixed bank versions')
        version = row['version']
        if hashlib.sha256(_json(row['questions'])).hexdigest() != row['checksum']:
            raise ValueError('Question row checksum mismatch')
        skill_ids = tuple(row['skillIds'])
        if len(skill_ids) != len(set(skill_ids)) or skill_ids != wanted[role]:
            raise ValueError('Wrong skill coverage for role')
        questions = []
        for q in row['questions']:
            options = tuple(Option(o['id'], o['text']) for o in q['options'])
            if (not q['prompt'].strip() or len(options) != 4 or len({o.id for o in options}) != 4
                    or len({o.text for o in options}) != 4 or q['answerKey'] not in {o.id for o in options}
                    or len(q['skillTags']) != 1 or q['skillTags'][0] not in wanted[role]):
                raise ValueError('Invalid question/options/tags')
            questions.append(Question(q['id'], tuple(q['skillTags']), q['prompt'], options, q['answerKey']))
        if len({q.id for q in questions}) != len(questions):
            raise ValueError('Duplicate question ID')
        if Counter(q.skillTags[0] for q in questions) != {skill:4 for skill in skill_ids}:
            raise ValueError('Four observations required for each skill')
        group = grouped.setdefault((role,grade), {})
        if variant in group:
            raise ValueError('Duplicate form variant')
        group[variant] = (skill_ids, Form(variant, tuple(questions)))
    if set(grouped) != expected or any(set(forms) != {'A','B','C'} for forms in grouped.values()):
        raise ValueError('Incomplete fixed bank')
    cells = {}
    for (role, grade), forms in grouped.items():
        if len({tuple(forms[v][0]) for v in 'ABC'}) != 1:
            raise ValueError('Form skill lists differ')
        cells[(role, grade)] = Cell(role, grade, forms['A'][0], tuple(forms[v][1] for v in 'ABC'), version=version)
    return Bank(cells, version)


def load_seed_rows():
    """Administrative import only; not used by request handling."""
    raw = (DATA / 'questions.v4.jsonl').read_bytes()
    manifest = json.loads((DATA / 'manifest.v4.json').read_text(encoding='utf-8'))
    if hashlib.sha256(raw).hexdigest() != manifest['sha256']:
        raise ValueError('Static bank manifest mismatch')
    source = [json.loads(line) for line in raw.splitlines()]
    if len(source) != manifest['cellCount'] or any(r['version'] != manifest['version'] for r in source):
        raise ValueError('Static bank metadata mismatch')
    return [dict(role=row['role'], grade=row['grade'], variant=form['id'], version=row['version'],
                 skillIds=row['skillIds'], questions=form['questions'],
                 checksum=hashlib.sha256(_json(form['questions'])).hexdigest())
            for row in source for form in row['forms']]


def load_seed_bank():
    return _bank(load_seed_rows())


def load_bank(session):
    """Runtime reads PostgreSQL only; missing/incomplete/modified rows fail closed."""
    rows = session.scalars(select(TaxonomyQuestionForm).where(TaxonomyQuestionForm.active.is_(True))).all()
    if not rows:
        raise ValueError('Question forms not imported into database')
    return _bank([dict(role=r.role_id, grade=r.grade_id, variant=r.variant, version=r.version,
                       skillIds=r.skill_ids, questions=r.questions, checksum=r.checksum)
                  for r in rows])


def score_form(cell: Cell, form: Form, answers: dict[str, str | None]) -> dict:
    expected = {q.id for q in form.questions}
    if set(answers) != expected:
        raise ValueError('Answers must cover each question exactly once')
    correct = Counter()
    count = Counter()
    total = 0
    for question in form.questions:
        answer = answers[question.id]
        if answer is not None and answer not in {o.id for o in question.options}:
            raise ValueError('Unknown option')
        success = int(answer == question.answerKey)
        total += success
        for tag in question.skillTags:
            count[tag] += 1
            correct[tag] += success
    n = len(form.questions)
    pass_count = (72 * n + 99) // 100
    high_count = (89 * n + 99) // 100
    outcome = 'high' if total >= high_count else 'pass' if total >= pass_count else 'fail'
    return dict(subscores={tag: 100 * correct[tag] / count[tag] for tag in cell.skillIds},
                evidenceCounts=dict(count), correctTechnical=total, technicalTotal=100 * total / n,
                totalScore=100 * total / n, outcome=outcome,
                passCorrect=pass_count, highCorrect=high_count)
