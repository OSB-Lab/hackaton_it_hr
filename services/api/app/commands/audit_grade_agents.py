"""Public-text-only rule agents: negative control, not human validation."""
import json
import re
from pathlib import Path

from app.modules.assessments.taxonomy_bank import load_seed_bank, public_form, score_form
from app.modules.recommendations.taxonomy_filter import load_runtime

DEFAULT_OUT = Path(__file__).resolve().parents[2] / 'docs/validation'
CATEGORY_PHRASES = {
 'анализа':'analysis','программных интерфейсов':'api','серверных фреймворков':'backend_framework',
 'серверных сред':'backend_runtime','непрерывной интеграции и доставки':'ci_cd',
 'облачной инфраструктуры':'cloud','контейнеризации':'containers',
 'машинного обучения':'data_ml','платформ данных':'data_platform',
 'баз данных':'database','языков запросов к данным':'database_language',
 'клиентской разработки':'frontend','клиентских фреймворков':'frontend_framework',
 'управления состоянием интерфейса':'frontend_state','языков программирования':'language',
 'очередей сообщений':'messaging','эксплуатации моделей':'mlops',
 'оркестрации':'orchestration','операционных систем':'os',
 'поисковых технологий':'search','безопасности':'security',
 'инженерных практик':'technical_skill','тестирования':'testing','контроля версий':'vcs',
}
# Independently specified knowledge rules on public text, never answerKey/skillTags.
BASIC = {'неизменяем':'tuple','not found':'404','list.pop':'удаляет последний'}
INTERMEDIATE = {'context manager':'cleanup ресурса','лишние индексы':'замедляют запись',
                'idempotent':'повтор','изоляци':'транзакц'}
ADVANCED = {'race condition':'синхрон','deadlock':'цикл','replication lag':'отставан',
            'rollback':'откат','backpressure':'огранич'}


def _choose(public_question, grade, label_to_category):
    prompt = public_question['prompt'].casefold()
    options = public_question['options']
    match = re.search(r'класса «([^»]+)»',prompt)
    if match and match.group(1) in CATEGORY_PHRASES:
        category = CATEGORY_PHRASES[match.group(1)]
        matching = [o for o in options if label_to_category.get(o['text'].casefold()) == category]
        if len(matching) == 1:
            return matching[0]['id'], True
    rules = dict(BASIC)
    if grade in ('middle','senior'): rules.update(INTERMEDIATE)
    if grade == 'senior': rules.update(ADVANCED)
    for clue,answer in rules.items():
        if clue in prompt:
            matches = [o for o in options if answer in o['text'].casefold()]
            if len(matches)==1: return matches[0]['id'],False
    return options[0]['id'],False


def audit(out=DEFAULT_OUT):
    out=Path(out);out.mkdir(parents=True,exist_ok=True)
    bank=load_seed_bank()
    skills=json.loads((Path(__file__).resolve().parents[1]/'modules/recommendations/config/skills.v1.json').read_text())['skills']
    lookup={s['label'].casefold():s['category'] for s in skills}
    results={}
    for agent in ('junior','middle','senior'):
        grades={'junior':[],'middle':[],'senior':[]}
        grade_scores={'junior':[],'middle':[],'senior':[]}
        visible=0
        for cell in bank.cells.values():
            for form in cell.forms:
                answers={}
                for q in public_form(form):
                    option,shortcut=_choose(q,agent,lookup)
                    answers[q['id']]=option
                    visible+=int(shortcut)
                grade_result=score_form(cell,form,answers)
                grades[cell.grade].append(grade_result['outcome']!='fail')
                grade_scores[cell.grade].append(grade_result['technicalTotal'])
        results[agent]={g+'PassRate':round(sum(values)/len(values),4) for g,values in grades.items()}
        results[agent].update({g+'MeanScore':round(sum(values)/len(values),2) for g,values in grade_scores.items()})
        results[agent]['answeredUsingVisibleCategory']=visible
    report={'bankVersion':bank.version,'forms':sum(len(c.forms) for c in bank.cells.values()),
            'agents':results,'semanticStatus':'NOT_VALIDATED',
            'method':'Rules see public question text/options and taxonomy label/category; never hidden key/tag. This is a shortcut negative control, not an LLM or expert human.'}
    (out/'visible_grade_agents_v1.json').write_text(json.dumps(report,ensure_ascii=False,indent=2,sort_keys=True)+'\n')
    (out/'visible_grade_agents_v1.md').write_text(
        '# Публичные агенты Junior/Middle/Senior (негативный контроль)\n\n'
        'Агенты используют только видимый текст и варианты, без ключа. Это НЕ реальные квалификационные эксперты.\n\n'
        '| Агент | Junior pass | Middle pass | Senior pass | Вопросов по подсказке-категории |\n|---|---:|---:|---:|---:|\n'+
        ''.join(f'| {a} | {r["juniorPassRate"]} | {r["middlePassRate"]} | {r["seniorPassRate"]} | {r["answeredUsingVisibleCategory"]} |\n'
                for a,r in results.items())+
        '\nЕсли Junior проходит Senior по подсказке-категории, содержательное разделение грейдов не доказано.\n')
    return report


if __name__=='__main__':
    print(json.dumps(audit(),ensure_ascii=False,sort_keys=True))
