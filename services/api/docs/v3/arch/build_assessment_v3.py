#!/usr/bin/env python3
"""Build a reviewable v3 multi-tag assessment pool (4 cells × A/B/C × 20)."""
from __future__ import annotations
import hashlib
import json
from pathlib import Path

FORMS = "ABC"
SPECS = {
 "backend": ["python","sql","api"],
 "frontend": ["javascript","typescript","react"],
}
# Each tuple is prompt, correct answer, three plausible distractors. Items are reviewed content, not LLM at runtime.
ITEMS = {
 "python":[("Какой тип Python неизменяем?","tuple","list","dict","set"),("Что возвращает list.pop()?","последний элемент и удаляет его","индекс","копию списка","ничего"),("Зачем используют context manager?","гарантировать cleanup ресурса","ускорить GC","создать поток","сериализовать объект"),("Что делает generator?","выдаёт значения лениво","всегда создаёт list","параллелит CPU","компилирует код"),("Почему mutable default опасен?","один объект разделяется вызовами","он неизменяем","ломает typing","нельзя передать list"),("Что ограничивает GIL?","CPU-bound параллелизм потоков","async I/O","память процесса","HTTP timeout")],
 "sql":[("Что фильтрует строки до агрегации?","WHERE","HAVING","ORDER BY","LIMIT"),("Какой JOIN требует совпадения с обеих сторон?","INNER JOIN","LEFT JOIN","CROSS JOIN","FULL JOIN"),("Почему лишние индексы вредны?","замедляют запись","ломают SELECT","удаляют дубликаты","делают таблицу readonly"),("Что делает ROW_NUMBER?","нумерует строки в окне","удаляет строки","создаёт индекс","группирует таблицу"),("Для чего transaction?","атомарность согласованных изменений","форматирование SQL","кэширование","сжатие данных"),("Что предотвращает unique constraint?","дубликаты ключа","NULL","slow query","deadlock")],
 "api":[("Какой статус означает Not Found?","404","201","302","500"),("Для чего Idempotency-Key?","безопасно повторить POST","зашифровать body","заменить auth","ускорить DNS"),("Какой статус rate limit?","429","401","503","204"),("Где передают bearer token?","Authorization header","URL path","response body","cookie name"),("Зачем HTTP timeout клиенту?","ограничить зависшее ожидание","увеличить payload","выбрать status","создать JWT"),("Что означает 204?","успех без тела","ресурс создан","ошибка схемы","redirect")],
 "javascript":[("Что возвращает Array.filter?","новый массив прошедших predicate","первый элемент","исходный массив","Promise"),("Почему === предпочтительнее ==?","нет неявного приведения","быстрее сеть","создаёт type","меняет scope"),("Что раньше: Promise.then или setTimeout?","Promise.then","setTimeout","всегда одновременно","зависит от CSS"),("Что делает spread для массива?","создаёт поверхностную копию","сортирует","замораживает","удаляет null"),("Что такое closure?","доступ функции к внешнему scope","глобальная переменная","class","HTTP cookie"),("Что делает Promise.all при reject?","reject всего результата","игнорирует ошибку","повторяет запрос","возвращает null")],
 "typescript":[("Какой тип отключает проверку любого значения?","any","unknown","never","void"),("Как сделать поле необязательным?","name?: string","name: optional<string>","optional name","name!: string"),("Что даёт keyof T?","union ключей типа","массив значений","число полей","runtime object"),("Чем unknown безопаснее any?","требует narrowing","быстрее","запрещает null","создаёт class"),("Что делает Partial<T>?","делает свойства optional","делает readonly","удаляет keys","создаёт enum"),("Для чего generics?","сохранять типы в reusable code","обфусцировать","ускорять сеть","заменять tests")],
 "react":[("Какой hook хранит локальный state?","useState","useEffect","useMemo","useContext"),("Зачем key в списке?","сопоставить элементы при reconciliation","задать CSS","создать DOM id","кэшировать fetch"),("Когда useEffect запускается снова?","при изменении dependencies","при CSS change","только на click","никогда"),("Что memoизирует useCallback?","ссылку на функцию","значение","state","HTTP response"),("Почему index плохой key в изменяемом списке?","state может перейти не тому item","index не number","React не рендерит list","ломает TypeScript"),("Что такое controlled input?","value управляется state","input без value","browser cache","server component")],
}

def q(qid,tags,item):
 p,ok,*bad=item; opts=[ok,*bad]
 # Stable per-question shuffle: answer position cannot leak the key, while a
 # rebuild preserves immutable bytes for the same authored item.
 order=sorted(range(4), key=lambda i: hashlib.sha256(f"{qid}:{i}".encode()).hexdigest())
 opts=[opts[i] for i in order]
 correct=f"o{opts.index(ok)+1}"
 return {"id":qid,"skillTags":tags,"type":"single_choice","prompt":p,"options":[{"id":f"o{i+1}","text":x} for i,x in enumerate(opts)],"answerKey":{"optionId":correct},"maxScore":1.0}

def build_cell(spec,grade,form):
 skills=SPECS[spec]; shift=FORMS.index(form)+(0 if grade=="junior" else 2); questions=[]
 for skill in skills:
  for n in range(4): questions.append(q(f"{spec}-{grade}-{form}-{skill}-{n+1}",[skill],ITEMS[skill][(n+shift)%6]))
 # One for each pair, three all-skill integrations. Item wording makes integrative evidence explicit.
 for i,(a,b) in enumerate(((skills[0],skills[1]),(skills[0],skills[2]),(skills[1],skills[2]))):
  questions.append(q(f"{spec}-{grade}-{form}-pair-{i+1}",[a,b],("В интеграционном кейсе какой подход сохраняет корректность обоих слоёв?","явно валидировать контракт и данные на границе","игнорировать ошибки","хранить ключи в UI","повторять запрос бесконечно")))
 for i in range(3): questions.append(q(f"{spec}-{grade}-{form}-all-{i+1}",skills,("Какое решение помогает безопасно связать компоненты системы?","явный контракт, валидация и тесты","глобальная mutable переменная","отключить типы","скрыть ошибку")))
 for i in range(2): questions.append(q(f"{spec}-{grade}-{form}-teamwork-{i+1}",["teamwork"],("Как корректно сообщить о блокере?","сразу: контекст, влияние и следующий шаг","молчать до дедлайна","обвинить коллегу","удалить задачу")))
 return questions

def main():
 pool={f"{s}-{g}":{v:build_cell(s,g,v) for v in FORMS} for s in SPECS for g in ("junior","middle")}
 (Path(__file__).parent.parent / "business-logic" / "questions-v3.json").write_text(json.dumps(pool,ensure_ascii=False,indent=2),encoding="utf-8")
if __name__=="__main__": main()
