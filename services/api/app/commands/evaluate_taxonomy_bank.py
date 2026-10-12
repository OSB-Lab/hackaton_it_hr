"""Model-based diagnostic, NOT evidence that generated questions measure human skill."""
import argparse
import hashlib
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

from app.modules.assessments.taxonomy_bank import load_seed_bank, score_form
from app.commands.generate_taxonomy_fixtures import DEFAULT_OUT as FIXTURES

DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'docs' / 'validation'
GRADES = ('junior', 'middle', 'senior')


def _draw(seed, question_id):
    return int.from_bytes(hashlib.sha256(f'{seed}|{question_id}'.encode()).digest()[:8], 'big') / 2**64


def _answers(candidate, cell, form):
    target = GRADES.index(cell.grade)
    actual = GRADES.index(candidate['gradeId'])
    answers = {}
    for q in form.questions:
        ability = candidate['skillLevels'].get(q.skillTags[0], 0)
        # Explicit modelling assumption: higher-grade material has additional
        # complexity NOT present in the current DEMO recognition question text.
        probability = max(.05, min(.98, .78 + (ability - (19 + 13*target)) / 100
                                       - .20 * max(0, target-actual)))
        if _draw(candidate['responseSeed'], q.id) < probability:
            answers[q.id] = q.answerKey
        else:
            answers[q.id] = next(o.id for o in q.options if o.id != q.answerKey)
    return answers


def evaluate(out=DEFAULT_OUT, fixture_dir=FIXTURES):
    root = Path(out)
    root.mkdir(parents=True, exist_ok=True)
    bank = load_seed_bank()
    cards=json.loads((Path(__file__).resolve().parents[1]/'data/taxonomy/curated_cards.v1.json').read_text())
    authored_prompts={values[0] for grades in cards.values() for values in grades.values()}
    manifest = json.loads((Path(fixture_dir) / 'manifest.v1.json').read_text())
    if manifest['questionBankVersion'] != bank.version:
        raise ValueError('Fixture/question bank version mismatch; regenerate fixtures')
    candidates = [json.loads(row) for row in (Path(fixture_dir) / 'candidates.v1.jsonl').read_text().splitlines()]
    same, adjacent, decisions, spreads = [], [], [], []
    strong_junior, middle = [], []
    by_grade = defaultdict(list)
    answer_position = Counter()
    leaked, ambiguous = [], []
    shortcut_count, reused_count, curated_count = 0, 0, 0
    for cell in bank.cells.values():
        for form in cell.forms:
            for q in form.questions:
                if 'нужна технология класса' in q.prompt:
                    shortcut_count += 1
                elif any(q.prompt.endswith(stem) for stem in authored_prompts):
                    curated_count += 1
                else:
                    reused_count += 1
                answer_position[q.answerKey] += 1
                if 'нужна технология класса' in q.prompt and re.search(
                    r'(?<![a-z0-9])'+re.escape(q.skillTags[0])+r'(?![a-z0-9])', q.prompt.casefold()):
                    leaked.append(q.id)
                if len({o.text for o in q.options}) != 4 or q.answerKey not in {o.id for o in q.options}:
                    ambiguous.append(q.id)
    for c in candidates:
        actual = GRADES.index(c['gradeId'])
        for target in (actual, actual+1):
            if target >= len(GRADES):
                continue
            cell = bank.cell(c['roleId'], GRADES[target])
            results = [score_form(cell, form, _answers(c, cell, form)) for form in cell.forms]
            passed = [r['outcome'] != 'fail' for r in results]
            if target == actual:
                same.extend(passed)
                by_grade[c['gradeId']].extend(passed)
                decisions.append(len(set(passed)) == 1)
                spreads.append(max(r['technicalTotal'] for r in results) - min(r['technicalTotal'] for r in results))
                if c['gradeId'] == 'middle' and c['personaStrength'] == 'typical':
                    middle.extend(passed)
            else:
                adjacent.extend(passed)
                if c['gradeId'] == 'junior' and c['personaStrength'] == 'strong':
                    strong_junior.extend(passed)
    ratio = lambda values: round(sum(values) / len(values), 4) if values else 0
    report = dict(model='hypothetical_response_probability_v1', semanticStatus='NOT_VALIDATED',
        candidateCount=len(candidates), cellCount=len(bank.cells), formCount=sum(len(c.forms) for c in bank.cells.values()),
        questionBankVersion=bank.version, fixtureVersion=manifest['version'],
        sameGradePassRate=ratio(same), adjacentLowerPassRate=ratio(adjacent),
        strongJuniorOnMiddlePassRate=ratio(strong_junior), typicalMiddlePassRate=ratio(middle),
        formDecisionStability=ratio(decisions), meanScoreSpreadAcrossForms=round(sum(spreads)/len(spreads), 2),
        byGradePassRate={g:ratio(by_grade[g]) for g in GRADES},
        lexicalAnswerLeaks=len(leaked), duplicateOrAmbiguousOptions=len(ambiguous),
        categoryShortcutItemFraction=round(shortcut_count / (shortcut_count + reused_count + curated_count), 4),
        reusedMvpItems=reused_count, curatedScenarioItems=curated_count, generatedRecognitionItems=shortcut_count,
        answerPositionCounts=dict(sorted(answer_position.items())),
        formIndependence='NOT_ESTABLISHED: same concept and answer across A/B/C',
        gradeDiscriminationByContent='UNREVIEWED: grade-specific scenarios, no external calibration',
        caveat='Response probabilities assume grade difficulty without independent human validation; simulated separation is not empirical validity.')
    (root / 'taxonomy_simulation_v2.json').write_text(json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True)+'\n')
    lines = ['# Синтетическая проверка таксономического банка', '',
        f"Банк: `{bank.version}`; кандидатов: {len(candidates)}. **Семантическая валидность: НЕ УСТАНОВЛЕНА.**", '',
        '| Метрика | Результат |', '|---|---:|']
    for key in ('sameGradePassRate','adjacentLowerPassRate','strongJuniorOnMiddlePassRate',
                'typicalMiddlePassRate','formDecisionStability','meanScoreSpreadAcrossForms',
                'lexicalAnswerLeaks','duplicateOrAmbiguousOptions','categoryShortcutItemFraction',
                'reusedMvpItems','curatedScenarioItems','generatedRecognitionItems'):
        lines.append(f'| `{key}` | {report[key]} |')
    lines += ['', 'Модель ответов использует латентные проценты навыков и **заданную извне**',
        'вероятность ошибки по грейду. Она не выводится из ответов независимых людей.',
        'Поэтому её цифры не доказывают разделяющую силу банка на реальной аудитории.',
        'A/B/C часто повторяют одну и ту же идею; четыре вопроса на навык могут сводиться',
        'к одной предметной карточке с разными формулировками.',
        'Негативный агент, выбирающий единственный инструмент названной категории, теперь не имеет shortcut.',
        'Но без отдельной экспертной разметки и пилота банк остаётся DEMO.', '']
    (root / 'taxonomy_simulation_v2.md').write_text('\n'.join(lines), encoding='utf-8')
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()
    print(json.dumps(evaluate(args.out), ensure_ascii=False, sort_keys=True))


if __name__ == '__main__':
    main()
