"""Pure v3 scorer: integer gates, each technical question counted exactly once."""
from fastapi import HTTPException

from app.modules.assessments.schemas import ResultDTO, SubmitRequest
from app.modules.catalog.v3 import BlueprintV3


def score_v3(blueprint: BlueprintV3, variant: str, request: SubmitRequest) -> ResultDTO:
    questions = next(v.questions for v in blueprint.variants if v.id == variant)
    answers = {a.questionId: a.optionId for a in request.answers}
    if len(answers) != len(request.answers) or set(answers) != {q.id for q in questions}:
        raise HTTPException(422, "Answers must cover each question exactly once")
    correct, counts = {}, {}
    technical = 0
    for question in questions:
        option = answers[question.id]
        if option is not None and option not in {o.id for o in question.options}:
            raise HTTPException(422, "Unknown answer option")
        awarded = int(option == question.answerKey.optionId)
        if question.skillTags != ("teamwork",):
            technical += awarded
        for tag in question.skillTags:
            correct[tag] = correct.get(tag, 0) + awarded
            counts[tag] = counts.get(tag, 0) + 1
    thresholds = blueprint.scoring.thresholds
    core = set(counts) - {"teamwork"}
    high_gate = all(100 * correct[s] >= thresholds.minimumCoreSkillHigh * counts[s] for s in core)
    pass_gate = all(100 * correct[s] >= thresholds.minimumCoreSkillPass * counts[s] for s in core)
    outcome = ("high" if technical >= thresholds.highCorrect and high_gate else
               "pass" if technical >= thresholds.passCorrect and pass_gate else "fail")
    return ResultDTO(subscores={s: 100 * correct[s] / counts[s] for s in counts},
                     evidenceCounts=counts, correctTechnical=technical,
                     totalScore=technical / 18 * 100, technicalTotal=technical / 18 * 100,
                     teamworkSubscore=100 * correct["teamwork"] / counts["teamwork"],
                     outcome=outcome)