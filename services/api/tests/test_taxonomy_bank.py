from collections import Counter
from app.modules.assessments.taxonomy_bank import load_seed_bank, score_form, public_form
from app.modules.recommendations.taxonomy_filter import load_runtime


def test_every_taxonomy_role_grade_has_three_balanced_forms_and_all_skills():
    taxonomy, _ = load_runtime()
    bank = load_seed_bank()
    assert len(bank.cells) == len(taxonomy.role_edges) * len(taxonomy.grade_fit) == 15
    import json
    from pathlib import Path
    core = json.loads((Path(__file__).resolve().parents[1]/'app/modules/recommendations/config/assessment-core.v1.json').read_text())['roles']
    for (role, grade), cell in bank.cells.items():
        assert tuple(cell.skillIds) == tuple(core[role])
        assert {form.id for form in cell.forms} == {'A', 'B', 'C'}
        sizes = {len(form.questions) for form in cell.forms}
        assert sizes == {20}
        for form in cell.forms:
            assert Counter(tag for question in form.questions for tag in question.skillTags) == {
                skill: 4 for skill in cell.skillIds}
            assert all(len(q.options) == 4 and q.answerKey in {o.id for o in q.options}
                       for q in form.questions)
            assert all('нужна технология класса' not in q.prompt for q in form.questions)
            assert all('answerKey' not in str(q) for q in public_form(form))
            assert all('skillTags' not in q for q in public_form(form))
            assert all(not any(skill in q['id'] for skill in cell.skillIds) for q in public_form(form))
    assert bank.cell('fullstack', 'senior').skillIds == tuple(core['fullstack'])


def test_reuses_existing_substantive_mvp_items_when_available():
    from app.modules.catalog.repository import CatalogRepository
    bank = load_seed_bank()
    repo = CatalogRepository()
    source = next(repo.blueprint(key).document for key in repo.manifest.activeBlueprints
                  if (loaded := repo.blueprint(key)).document.specialization == 'backend'
                  and loaded.document.grade == 'junior')
    authored = {q.prompt for q in source.variants[0].questions if q.skillTags == ('python',)}
    generated = {q.prompt for q in bank.cell('backend','junior').forms[0].questions if q.skillTags == ('python',)}
    # The authored v3 junior content was refreshed (grade-separated banks); the
    # taxonomy bank still reuses whatever substantive items remain shared.
    assert len(authored & generated) >= 1
    assert len(generated) == 4
    assert any('a=[1]; b=a' in prompt for prompt in generated)


def test_static_questions_do_not_print_correct_option_in_prompt():
    bank = load_seed_bank()
    leaked = [q.id for cell in bank.cells.values() for form in cell.forms for q in form.questions
              if 'нужна технология класса' in q.prompt
              and q.skillTags[0] in q.prompt.casefold()]
    assert not leaked, f'Generated prompts leak answer tags: {leaked[:3]}'


def test_score_counts_tags_and_missing_answers_without_certification():
    cell = load_seed_bank().cell('data_engineer', 'junior')
    form = cell.forms[0]
    correct: dict[str, str | None] = {q.id: q.answerKey for q in form.questions}
    result = score_form(cell, form, correct)
    assert result['outcome'] == 'high' and result['technicalTotal'] == 100
    assert set(result['subscores']) == set(cell.skillIds)
    assert all(v == 100 for v in result['subscores'].values())
    one_wrong = dict(correct)
    one_wrong[form.questions[0].id] = None
    partial = score_form(cell, form, one_wrong)
    tag = form.questions[0].skillTags[0]
    assert partial['subscores'][tag] == 75
    assert partial['evidenceCounts'][tag] == 4
    missing = {q.id: None for q in form.questions}
    assert score_form(cell, form, missing)['outcome'] == 'fail'
