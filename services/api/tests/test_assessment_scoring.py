import json

import pytest

from app.modules.assessments.schemas import AttemptSnapshot, SubmitRequest
from app.modules.assessments.service import score_answers
from app.modules.catalog.repository import CatalogRepository, decode


@pytest.mark.parametrize('pass_score,high_score,outcome', [(60, 80, 'pass'), (40, 60, 'high'), (60.01, 80, 'fail'), (40, 60.01, 'pass')])
@pytest.mark.parametrize('same_skill', [False, True])
def test_weighted_rubric_manual_calculation(pass_score, high_score, outcome, same_skill):
    repo = CatalogRepository()
    blueprint = repo.blueprint('backend-junior-v1-demo').document.model_dump(mode='json')
    first, second = blueprint['slots']
    first.update(weight=2, maxScore=10)
    second.update(weight=3, maxScore=40)
    if same_skill:
        second['skillId'] = first['skillId']
    blueprint['rubric'][0].update(incorrectFraction=0.25, unansweredFraction=0.5)
    blueprint['scoring']['thresholds'].update(passScore=pass_score, highScore=high_score)
    snapshot = decode(AttemptSnapshot, json.dumps({'schemaVersion': 1, 'blueprint': blueprint,
                      'catalog': repo.catalog().document.model_dump(mode='json')}))
    questions = snapshot.blueprint.variants[0].questions
    body = SubmitRequest(answers=[{'questionId': questions[0].id,
                                  'optionId': next(o.id for o in questions[0].options if o.id != questions[0].answerKey.optionId)},
                                 {'questionId': questions[1].id, 'optionId': questions[1].answerKey.optionId}])
    # Awarded points 2.5/10 and 40/40: 100*(2*0.25+3*1)/5 = 70.
    result = score_answers(snapshot, 'A', body)
    expected = {first['skillId']: 70} if same_skill else {first['skillId']: 25, second['skillId']: 100}
    assert result.totalScore == 70 and result.subscores == expected
    body.answers[0].optionId = None
    body.answers[1].optionId = next(o.id for o in questions[1].options if o.id != questions[1].answerKey.optionId)
    # Unanswered 5/10 and incorrect 10/40: 100*(2*0.5+3*0.25)/5 = 35.
    assert score_answers(snapshot, 'A', body).totalScore == 35
    body.answers[0].optionId = next(o.id for o in questions[0].options if o.id != questions[0].answerKey.optionId)
    body.answers[1].optionId = None
    # 100*(2*0.25+3*0.5)/5 = 40; select a 60-point boundary case below.
    assert score_answers(snapshot, 'A', body).totalScore == 40
    body.answers[0].optionId = questions[0].answerKey.optionId
    body.answers[1].optionId = next(o.id for o in questions[1].options if o.id != questions[1].answerKey.optionId)
    assert score_answers(snapshot, 'A', body).totalScore == 55
    body.answers[0].optionId = None
    body.answers[1].optionId = questions[1].answerKey.optionId
    assert score_answers(snapshot, 'A', body).totalScore == 80
    # Exact 60 using both unanswered fractions set by this fixture.
    blueprint['rubric'][0]['unansweredFraction'] = 0.6
    snapshot = decode(AttemptSnapshot, json.dumps({'schemaVersion': 1, 'blueprint': blueprint,
                      'catalog': repo.catalog().document.model_dump(mode='json')}))
    for answer in body.answers:
        answer.optionId = None
    result = score_answers(snapshot, 'A', body)
    assert result.totalScore == 60 and result.outcome == outcome
