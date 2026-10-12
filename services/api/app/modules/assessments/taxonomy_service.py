"""Isolated taxonomy diagnostic attempts. DEMO results never certify a role/grade."""
import hashlib
import json
import secrets
from dataclasses import asdict
from datetime import datetime, timezone

from fastapi import HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select

from app.models import CandidateProfile, TestAttempt
from app.modules.assessments.schemas import StartRequest, SubmitDTO, SubmitRequest, ResultDTO
from app.modules.assessments.taxonomy_bank import (
    Cell, Form, Option, Question, load_bank, public_form, score_form,
)


class PublicOption(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    text: str


class PublicQuestion(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: str
    prompt: str
    options: list[PublicOption]


class DiagnosticAssessment(BaseModel):
    model_config = ConfigDict(extra='forbid')
    version: str
    role: str
    grade: str
    variant: str
    skillIds: list[str]
    passCorrect: int
    highCorrect: int
    questions: list[PublicQuestion]


class DiagnosticAttempt(BaseModel):
    model_config = ConfigDict(extra='forbid')
    id: int
    status: str
    assessment: DiagnosticAssessment


def _raw(snapshot):
    return json.dumps(snapshot, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode()


def _owned(session, user_id, attempt_id, *, lock=False):
    statement = select(TestAttempt).join(CandidateProfile, TestAttempt.candidate_id == CandidateProfile.id).where(
        TestAttempt.id == attempt_id, CandidateProfile.user_id == user_id)
    if lock:
        statement = statement.with_for_update(of=TestAttempt)
    attempt = session.scalar(statement)
    if not attempt or attempt.snapshot_schema_version != 2:
        raise HTTPException(404, 'Diagnostic attempt not found')
    return attempt


def _unpack(attempt):
    snapshot = attempt.snapshot
    if not isinstance(snapshot, dict) or hashlib.sha256(_raw(snapshot)).hexdigest() != attempt.blueprint_checksum:
        raise HTTPException(503, 'Pinned diagnostic unavailable')
    try:
        form_data = snapshot['form']
        form = Form(form_data['id'], tuple(Question(q['id'], tuple(q['skillTags']), q['prompt'],
            tuple(Option(o['id'], o['text']) for o in q['options']), q['answerKey'])
            for q in form_data['questions']))
        cell = Cell(snapshot['role'], snapshot['grade'], tuple(snapshot['skillIds']), (form,), version=snapshot['version'])
        if (snapshot['schemaVersion'] != 2 or not cell.version.startswith(
                ('taxonomy-recognition-demo-v', 'taxonomy-static-demo-v3-', 'taxonomy-curated-demo-v4-'))
                or (attempt.specialization, attempt.requested_grade, attempt.variant) !=
                   (cell.role, cell.grade, form.id)):
            raise ValueError('Diagnostic metadata mismatch')
        return cell, form
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(503, 'Pinned diagnostic unavailable') from exc


def _dto(attempt):
    cell, form = _unpack(attempt)
    n = len(form.questions)
    return DiagnosticAttempt(id=attempt.id, status=attempt.status,
        assessment=DiagnosticAssessment(version=cell.version,
            role=cell.role, grade=cell.grade, variant=form.id, skillIds=list(cell.skillIds),
            passCorrect=(72*n+99)//100, highCorrect=(89*n+99)//100,
            questions=[PublicQuestion.model_validate(q) for q in public_form(form)]))


def start_diagnostic(session, user_id, request):
    try:
        profile = session.scalar(select(CandidateProfile).where(CandidateProfile.user_id == user_id).with_for_update())
        if profile is None or profile.specialization != request.specialization:
            raise HTTPException(409, 'Save the chosen role in your profile first')
        active = session.scalar(select(TestAttempt).where(
            TestAttempt.candidate_id == profile.id, TestAttempt.status == 'active'))
        if active:
            if active.snapshot_schema_version == 2 and (active.specialization, active.requested_grade) == (request.specialization, request.grade):
                response = _dto(active)
                session.commit()
                return response, False
            raise HTTPException(409, 'Another assessment is active')
        try:
            cell = load_bank(session).cell(request.specialization, request.grade)
        except KeyError:
            raise HTTPException(422, 'Unknown role or grade') from None
        except ValueError:
            raise HTTPException(503, 'Question bank unavailable') from None
        seen = set(session.scalars(select(TestAttempt.variant).where(
            TestAttempt.candidate_id == profile.id, TestAttempt.snapshot_schema_version == 2,
            TestAttempt.blueprint_version == cell.version,
            TestAttempt.specialization == request.specialization, TestAttempt.requested_grade == request.grade)))
        unseen = [form for form in cell.forms if form.id not in seen]
        if not unseen:
            raise HTTPException(409, 'Diagnostic pool exhausted')
        chosen = secrets.choice(unseen)
        questions = list(chosen.questions)
        secrets.SystemRandom().shuffle(questions)
        form = Form(chosen.id, tuple(questions))
        snapshot = dict(schemaVersion=2, version=cell.version, role=cell.role,
                        grade=cell.grade, skillIds=list(cell.skillIds), form=asdict(form))
        attempt = TestAttempt(candidate_id=profile.id, test_id=f'taxonomy-demo-{cell.role}-{cell.grade}',
            specialization=cell.role, requested_grade=cell.grade, variant=form.id,
            blueprint_version=cell.version, catalog_version='talent-taxonomy-v2',
            blueprint_checksum=hashlib.sha256(_raw(snapshot)).hexdigest(),
            snapshot_schema_version=2, snapshot=snapshot,
            status='active', submitted_at=None)
        session.add(attempt)
        session.flush()
        response = _dto(attempt)
        session.commit()
        return response, True
    except Exception:
        session.rollback()
        raise


def read_diagnostic(session, user_id, attempt_id):
    return _dto(_owned(session, user_id, attempt_id))


def submit_diagnostic(session, user_id, attempt_id, request: SubmitRequest):
    try:
        session.execute(select(CandidateProfile.id).join(TestAttempt, TestAttempt.candidate_id == CandidateProfile.id).where(
            TestAttempt.id == attempt_id, CandidateProfile.user_id == user_id).with_for_update(of=CandidateProfile)).first()
        attempt = _owned(session, user_id, attempt_id, lock=True)
        cell, form = _unpack(attempt)
        if attempt.status == 'active':
            answers = {a.questionId: a.optionId for a in request.answers}
            if len(answers) != len(request.answers):
                raise HTTPException(422, 'Duplicate question ID')
            try:
                scored = score_form(cell, form, answers)
            except ValueError:
                raise HTTPException(422, 'Invalid answers') from None
            result = ResultDTO.model_validate({k: v for k, v in scored.items() if k not in ('passCorrect','highCorrect')})
            attempt.result = result.model_dump(mode='json')
            attempt.answers = [a.model_dump(mode='json') for a in request.answers]
            attempt.score = result.totalScore
            attempt.status = 'submitted'
            attempt.submitted_at = datetime.now(timezone.utc)
            # Never call apply_result or write CompetencyScore for synthetic recognition questions.
        if attempt.status != 'submitted' or not attempt.result or not attempt.submitted_at:
            raise HTTPException(409, 'Result unavailable')
        response = SubmitDTO(id=attempt.id, status='submitted', submittedAt=attempt.submitted_at,
                             result=ResultDTO.model_validate(attempt.result))
        session.commit()
        return response
    except Exception:
        session.rollback()
        raise
