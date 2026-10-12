> **Исторический снимок.** Этот документ отражает состояние до удаления разделения demo/real/test
> (флаги `DEMO`/`APPROVED`/`content_status` удалены, миграция `0012`, квалификация — по баллу).
> Актуальное состояние — в [`README.md`](../../README.md) и [`docs/JURY.md`](../../docs/JURY.md).

# Контракт тестирования и категоризации (SPR-14 / SPR-15, редакция для финала)

> Статус: **LOCKED v3 business rules; question content pending expert review**. v2 не применять для новых blueprint:
> она недостаточно надёжно измеряет technical skills (всего шесть technical questions). Веса, thresholds,
> `skillTags`, grade transitions, cooldown и matching policy ниже фиксированы; expert review может менять только
> item content через новую immutable версию, не меняя эти правила без отдельного решения.
> Редакция основана на ТЗ ФСП (разд. 2, 2.1, 2.2, 3.3–3.4, 6) и ответах организаторов PR.1, VS.1, VS.5,
> FTT.3–FTT.4, WA.1.
> Любое изменение опубликованного контента/порогов/весов = новая версия blueprint, а не правка на месте.

---

## 0. TL;DR — зафиксированные значения

| Параметр | Значение |
|---|---|
| Специализации | `backend` (Backend Python), `frontend` (Frontend React) |
| Грейды (тестируемые) | `junior` (Junior), `middle` (Middle). `senior` есть в таксономии профиля, но **без blueprint** → `/assessments/start` на senior возвращает `422` |
| Навыков на ячейку | **4**: 3 technical + `teamwork` diagnostic |
| Вопросов на форму | **20**: 18 technical + 2 teamwork diagnostic |
| Теги вопроса | `skillTags`: 1–3 canonical skills; один правильный ответ даёт evidence каждому тегу |
| Варианты blueprint | **A/B** — две обязательные изоморфные формы; форма **C** — резерв пула для retest/ротации и публикуется той же immutable версией |
| Формат ответа | только `single_choice`, 4 опции, ровно 1 верная |
| Макс. балл вопроса | `1.0` |
| Rubric | `single_choice_exact`: верно=1.0, неверно=0.0, без ответа=0.0 |
| Формула итога | `weighted_normalized_sum`, шкала 0–100 |
| Вес для технического грейда | равный: 3 technical skills × 2 слота × weight 1.0 → по 33.3%; teamwork считается отдельно |
| `passScore` | **13/18 technical = 72.2222%**, плюс не менее 50% evidence по каждому core skill |
| `highScore` | **16/18 technical = 88.8889%**, плюс не менее 70% evidence по каждому core skill |
| Skill subscore | 0–100: `correct tagged / all tagged`; multi-tag item даёт один evidence каждому своему тегу |
| Cooldown | `cooldownDays = 90` (env; выбранный командой интервал) — после успешного присвоения/повышения категории; fail не понижает грейд |

---

## 1. Специализации и допустимые грейды

- `backend` — **Backend Python**
- `frontend` — **Frontend React**

Грейды для тестирования: `junior`, `middle`. `senior` присутствует в `catalog.json` (таксономия профиля/будущее),
но **не тестируется** в MVP: нет blueprint → попытка старта теста на `senior` даёт `422 "no blueprint for grade"`.

Инвариант: **один и тот же набор навыков** на `junior` и `middle` внутри специализации. Грейд отличает
только сложность вопросов, не список навыков (это нужно для сопоставимости вариантов и разделяющей силы).

## 2. Навыки на ячейку (4, фиксировано, совпадает с catalog)

| Специализация | Skill IDs (порядок слотов) |
|---|---|
| backend | `python`, `sql`, `api`, `teamwork` |
| frontend | `javascript`, `typescript`, `react`, `teamwork` |

`teamwork` — вспомогательный soft-skill. Он показывается в профиле как отдельный сигнал, но **не участвует в
автоматическом присвоении технического грейда**: единичный тест с «правильным поведением» не даёт достаточно
объективного доказательства уровня. Технический итог и eligibility строятся по `python/sql/api` либо
`javascript/typescript/react`; `teamwork` остаётся диагностическим subscore.

## 3. Структура blueprint (20 questions, multi-tag evidence)

Каждая форма содержит 18 technical и 2 teamwork questions. Technical blueprint обязан дать каждому core skill
не менее 8 tagged observations: 12 single-tag questions (по 4 с primary tag на core skill), 3 two-tag
integration questions (по одной на пару skills) и 3 three-tag integration questions. Такая матрица даёт ровно
9 observations на каждый core skill. Multi-tag question — одно наблюдение для total и по одному observation
для каждого skill tag.

```
slots = [
  { id: "python-1",   skillTags: ["python"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "sql-1",      skillTags: ["sql"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "api-1",      skillTags: ["api"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "integration-1", skillTags: ["python", "sql"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "teamwork-1", skillTags: ["teamwork"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "integration-2", skillTags: ["python", "sql", "api"], weight: 1.0, maxScore: 1.0, rubricId: "exact" },
  { id: "teamwork-2", skillTags: ["teamwork"], weight: 1.0, maxScore: 1.0, rubricId: "exact" }
]
```

Для frontend слоты `api-*` заменяются на `typescript-*`/`react-*`-аналогично (см. §11).

**Важно для backend:** текущую схему `catalog/schemas.py` нужно расширить с `skillId` до `skillTags: list[ID]`.
Валидатор A/B/C проверяет одинаковую tag-incidence matrix, а scorer группирует questions по каждому тегу для
подсчёта skill evidence (см. §5).

## 4. Схема вопроса (фиксированные поля)

```json
{
  "id": "backend-junior-a-python-1",
  "slotId": "python-1",
  "skillTags": ["python"],
  "type": "single_choice",
  "prompt": "...",
  "options": [ {"id":"o1","text":"..."}, {"id":"o2","text":"..."}, {"id":"o3","text":"..."}, {"id":"o4","text":"..."} ],
  "answerKey": { "optionId": "o2" }
}
```

Правила:
- `id` глобально уникален внутри blueprint (валидатор уже проверяет).
- 4 опции, ровно одна верная; `answerKey.optionId` ссылается на существующую опцию.
- `skillTags` — непустой уникальный список canonical IDs, длиной 1–3. Они принадлежат одной specialization;
  `teamwork` не смешивается с technical tags в одном question.
- **Ответ на сервере:** `GET /assessments/{id}` **не отдаёт** `answerKey` (тест на утечку ключей обязателен).
- `type` на MVP — только `single_choice`. Открытые ответы/код — вне MVP (их оценивает работодатель, не система).

## 5. Rubric и подсчёт баллов

### 5.1 Оценка вопроса (rubric `single_choice_exact`)

| Событие | Доля от maxScore |
|---|---|
| выбран верный `optionId` | `1.0` |
| выбран неверный | `0.0` |
| вопрос пропущен (нет ответа) | `0.0` |

### 5.2 Skill evidence subscore (0–100)

Для каждого skill `s`: `subscore_s = correct questions tagged s / all questions tagged s × 100`.
Один верный multi-tag question повышает subscore каждого своего тега; неверный не повышает ни один. Это не
«двойные баллы»: total ниже считает каждый question один раз.

Technical subscores записываются в `competency_scores` с `source='test'`, `score = subscore_s`, `evidence_count`
и `blueprint_version`; teamwork — с `source='assessment_diagnostic'`. Self-declared skills не удаляются
автоматически: низкий/отсутствующий evidence создаёт status `unverified` или `discrepancy`, пригодный для UI и
очистки после явного review кандидата.

### 5.3 Технический total score (0–100) и диагностический teamwork

```
technicalTotal = (sum(weight_i × slotScore_i / maxScore_i for i in technical)
                  / sum(weight_i for i in technical)) × 100
```
В `technical` входят первые шесть слотов: `python/sql/api` или `javascript/typescript/react`.
При всех `weight=1.0` это `technicalTotal = correctTechnical / 18 × 100` с шагом 5.56.
Именно `technicalTotal` определяет PASS/HIGH, `verified_grade`, eligibility и силу теста в matching.

Два слота `teamwork` считаются отдельно и сохраняются как `teamworkSubscore`/объясняющий сигнал. Они не
могут ни повысить, ни понизить технический грейд. Это сохраняет их полезность для профиля, но не выдаёт
субъективное SJT-задание за объективную квалификационную проверку.

`formula = "weighted_normalized_sum"`, `scaleMin = 0`, `scaleMax = 100`.

## 6. Пороги и поведение на границах

| Диапазон | Итог | Точное правило |
|---|---|---|
| `< 13/18` либо core skill <50% | **FAIL** | 0–12 верных или явная core-skill gap |
| `13–15/18` и каждый core skill ≥50% | **PASS** | 72.2–83.3% |
| `16–18/18` и каждый core skill ≥70% | **HIGH** | 88.9–100% |

- В JSON хранить `passCorrect=13`, `highCorrect=16`, `minimumCoreSkillPass=50`,
  `minimumCoreSkillHigh=70`; UI показывает 72.2/88.9. Сравнение идёт по integer count и exact subscore,
  не по float epsilon.
- Пороги одинаковы для всех ячеек: тест подтверждает выбранный грейд, поэтому барьер одинаков и объясним.
- Старые 6-question/8-question totals не использовать: они давали слишком мало evidence на отдельный skill.

## 7. Эквивалентность форм пула (инвариант)

Формы пула (`A`, `B`, `C` и последующие) считаются эквивалентными, если выполнено **всё**:
1. одинаковая tag-incidence matrix: те же `skillTags`, `weight`, `maxScore`, `rubricId` и распределение сложности;
2. одинаковое число вопросов на слот (ровно 1);
3. каждая пара вопросов из пула в одном слоте тестирует **тот же навык и ту же подтему на том же уровне сложности**,
   отличаясь только формулировкой/данными (изоморфизм);
4. скоррер не читает `variantId` — он работает только от `questionId → skillTags`, поэтому итог по всем формам сопоставим.

Сервер случайно выбирает форму только при первом `start`, хранит `variantId` в immutable attempt и не позволяет
клиенту выбирать её. Канонический пул A/B/C — `questions-v3.json`; генератор и validation лежат в `../arch/`.

Защита от распространения ответов: (1) для retest выбирать форму, которую candidate ещё не видел в той же
ячейке; (2) если все формы показаны, блокировать старт до cooldown либо публиковать новую immutable версию
пула; (3) не показывать answer key, rubric, другие формы или внутренние weights; (4) помечать форму как
compromised и исключать её только новой версией blueprint. Документация хранит размер пула и историю версий.

## 8. Версионирование blueprint

- Каждый blueprint имеет `schemaVersion`, `version` (напр. `v1`), `catalogVersion` (напр. `v1-demo`).
- Артефакты уже пинтуются в `manifest.json` по ключу `<id>-<version>` с `sha256` и списком `activeBlueprints`
  (механизм есть в репозитории — используем его как есть).
- **Правило:** blueprint иммутабелен после публикации. Любое изменение контента/порогов/весов/слотов →
  новая версия (`v1` → `v2`): новый файл `v2.json`, новый `sha256` в manifest, обновление `activeBlueprints`.
- `TestAttempt` в момент `start` сохраняет `blueprintVersion` + `variantId` (см. §12), поэтому отправленная попытка
  всегда считается по той версии blueprint, по которой была начата, даже если позже вышла `v2`.
- `status` blueprint: `DEMO` → `APPROVED` (с `approval`) только после: (a) независимой проверки вопросов,
  (b) заполнения минимального пула, (c) прогона test-retest и discrimination validation из §15. Этот документ
  сам по себе не является доказательством финализации.

## 9. Поведение грейда при fail / pass / high

Поля кандидата: `self_declared_grade` (заявляет сам), `verified_grade` (подтверждён тестом, **нужна миграция** — сейчас в `candidate_profiles` его нет).

При submit попытки на выбранный кандидатом грейд `G`:

| Результат | `verified_grade` | Предлагаемый ретест | `last_grade_change_at` |
|---|---|---|---|
| **FAIL** (`<13/18` или core skill <50%) | остаётся прежний; если его не было — статус `unverified` | `lower_retest_offered` только при отсутствии подтверждённого грейда и наличии `gradeBelow(G)` | **не трогается** |
| **PASS** (`13–15/18`, каждый core ≥50%) | `verified_grade = max(previous, G)` | нет | `= now` только если категория впервые присвоена или повышена |
| **HIGH** (`16–18/18`, каждый core ≥70%) | `verified_grade = max(previous, G)` | `higher_retest_offered`, `retest_target_grade = gradeAbove(G)` при наличии | `= now` только если категория впервые присвоена или повышена |

Правила:
- **Грейд никогда не понижается автоматически.** FAIL оставляет прежний `verified_grade` (или `null`, если ещё не было).
- `verified_grade` меняется только при PASS/HIGH и только вверх; повторное подтверждение того же грейда не меняет дату.
- `retest_target_grade` — это **предложение**, а не автопереход: кандидат сам решает, идти ли на ретест.
- Кандидат без подтверждённого грейда видит статус «грейд не подтверждён». В выдачу работодателя он не попадает,
  потому что организаторы требуют формировать выдачу из категорий, присвоенных по тесту, а не из самоописания.
- Кандидат с уже подтверждённым junior, не сдавший middle, **остаётся junior**; ему не предлагается искусственно
  «понижаться» до junior. Lower-retest нужен для первого неуспешного выбора middle.

## 10. Правило 90-дневного cooldown

- **Событие, запускающее cooldown:** успешная первичная категоризация или повышение — PASS/HIGH, изменивший
  `verified_grade`. Фиксируется `last_grade_change_at = now (UTC)`.
- **Что блокируется:** старт теста на тот же или более высокий грейд, пока
  `now < last_grade_change_at + cooldownDays` → backend возвращает `409` с `retest_available_at`.
- **Что НЕ блокируется (разрешено всегда):**
  - первая попытка (`verified_grade == null`, `last_grade_change_at == null`);
  - lower-retest после первого FAIL без подтверждённой категории;
  - повтор после **FAIL** (провал не ставит `last_grade_change_at` и не тратит попытку — можно пересдать тот же грейд сразу).
- `cooldownDays = 90` берётся из env (по умолчанию 90); демо-сценарий при необходимости может его переопределить.
- При переходе с уже подтверждённого грейда доступен только `gradeAbove(verified_grade)`; так нельзя перепрыгнуть
  Junior → Senior. Для первого теста кандидат по ТЗ вправе сам выбрать предполагаемый грейд.

---

## 11. v3 question pool и архив v2

Исполняемый источник v3 pool: [`questions-v3.json`](questions-v3.json), генератор:
[`../arch/build_assessment_v3.py`](../arch/build_assessment_v3.py). Он создаёт 4 ячейки × A/B/C × 20 questions и проверяется
на 18 technical questions, 2 teamwork questions и 9 tagged observations каждого core skill. До публикации
предметный эксперт обязан проверить сложность, однозначность и эквивалентность форм.

### 11.1 Архив v2 bank (не использовать для v3)

> Эти 8-question A/B формулировки сохранены только как исторический reference. Они не соответствуют v3
> multi-tag evidence model и не должны переноситься в новые blueprint. Новый 20-question pool создаётся по
> matrix §3; устаревший v2 item-pool удалён.

Легенда: **✓** — верный вариант. `oN` — id опции для `answerKey`.

### 11.1 Backend · Junior

**Variant A**

- `backend-junior-a-python-1` · python · *«Какой тип в Python неизменяем?»*
  - o1 `list` · o2 `dict` · **o3 `tuple` ✓** · o4 `set`
- `backend-junior-a-python-2` · python · *«Какой метод удаляет и возвращает последний элемент списка?»*
  - o1 `remove()` · **o2 `pop()` ✓** · o3 `shift()` · o4 `delete()`
- `backend-junior-a-sql-1` · sql · *«Какая конструкция фильтрует строки до агрегации?»*
  - **o1 `WHERE` ✓** · o2 `HAVING` · o3 `ORDER BY` · o4 `GROUP BY`
- `backend-junior-a-sql-2` · sql · *«Какой JOIN вернёт только строки с совпадением в обеих таблицах?»*
  - o1 `LEFT JOIN` · **o2 `INNER JOIN` ✓** · o3 `CROSS JOIN` · o4 `FULL JOIN`
- `backend-junior-a-api-1` · api · *«Какой HTTP-метод идемпотентен и безопасен?»*
  - o1 `POST` · o2 `PATCH` · **o3 `GET` ✓** · o4 `DELETE`
- `backend-junior-a-api-2` · api · *«Какой код состояния означает «Не найдено»?»*
  - o1 `201` · **o2 `404` ✓** · o3 `500` · o4 `302`
- `backend-junior-a-teamwork-1` · teamwork · *«Коллега просит отревьюить его PR. Лучший первый шаг?»*
  - o1 сразу аппрувнуть · **o2 разобраться в изменении и дать конкретный конструктивный фидбек ✓** · o3 отмолчаться · o4 переписать код самому
- `backend-junior-a-teamwork-2` · teamwork · *«Как лучше сообщить о блокере?»*
  - o1 ждать до конца спринта · o2 «ничего не работает» · **o3 сразу и с контекстом: что пробовал, ожидание vs факт ✓** · o4 никому не говорить

**Variant B**

- `backend-junior-b-python-1` · python · *«Какой тип в Python изменяем?»*
  - **o1 `list` ✓** · o2 `tuple` · o3 `str` · o4 `int`
- `backend-junior-b-python-2` · python · *«Какой метод добавляет элемент в конец списка?»*
  - o1 `push()` · **o2 `append()` ✓** · o3 `add()` · o4 `insert()` (вставляет по индексу)
- `backend-junior-b-sql-1` · sql · *«Какая конструкция сортирует результат?»*
  - o1 `WHERE` · o2 `GROUP BY` · **o3 `ORDER BY` ✓** · o4 `LIMIT`
- `backend-junior-b-sql-2` · sql · *«Какой JOIN вернёт все строки левой таблицы + совпадения справа?»*
  - **o1 `LEFT JOIN` ✓** · o2 `INNER JOIN` · o3 `RIGHT JOIN` · o4 `CROSS JOIN`
- `backend-junior-b-api-1` · api · *«Какой HTTP-метод создаёт ресурс?»*
  - **o1 `POST` ✓** · o2 `GET` · o3 `PUT` · o4 `HEAD`
- `backend-junior-b-api-2` · api · *«Какой код состояния означает «Создано»?»*
  - **o1 `201` ✓** · o2 `200` · o3 `204` · o4 `400`
- `backend-junior-b-teamwork-1` · teamwork · *«Как воспринимать комментарии к своему PR?»*
  - o1 игнорировать · o2 спорить до конца · **o3 как предложения к обсуждению, отвечать уважительно ✓** · o4 удалить ветку
- `backend-junior-b-teamwork-2` · teamwork · *«Как лучше описать техническую проблему?»*
  - o1 «сломалось» · **o2 что пробовал + ожидаемый vs фактический результат ✓** · o3 только стектрейс без контекста · o4 не описывать

### 11.2 Backend · Middle

**Variant A**

- `backend-middle-a-python-1` · python · *«Что делает `yield`?»*
  - o1 завершает функцию · o2 возвращает значение и завершает · **o3 приостанавливает функцию, возвращая значение, и продолжает при `next()` ✓** · o4 то же, что `return`
- `backend-middle-a-python-2` · python · *«Что в основном ограничивает GIL?»*
  - o1 скорость ввода-вывода · **o2 истинный параллелизм CPU-bound потоков ✓** · o3 объём памяти · o4 размер стека
- `backend-middle-a-sql-1` · sql · *«Минус избыточного числа индексов на таблице?»*
  - o1 быстрее чтение · **o2 медленнее запись/вставка ✓** · o3 меньше памяти · o4 нет минусов
- `backend-middle-a-sql-2` · sql · *«Что делает `ROW_NUMBER() OVER (ORDER BY salary DESC)`?»*
  - **o1 нумерует строки без пропусков в заданном порядке ✓** · o2 то же, что `GROUP BY` · o3 удаляет дубликаты · o4 сортирует саму таблицу
- `backend-middle-a-api-1` · api · *«Зачем нужен заголовок `Idempotency-Key`?»*
  - o1 ускоряет ответ · o2 шифрует запрос · **o3 позволяет безопасно повторить неидемпотентную операцию (напр. POST) ✓** · o4 заменяет авторизацию
- `backend-middle-a-api-2` · api · *«Какой код означает превышение rate limit?»*
  - o1 `404` · o2 `503` · **o3 `429` ✓** · o4 `401`
- `backend-middle-a-teamwork-1` · teamwork · *«Бизнес требует фичу, а вы видите критический техдолг. Как поступить?»*
  - o1 сделать фичу молча · o2 игнорировать техдолг · **o3 зафиксировать риски и варианты, согласовать приоритет на данных ✓** · o4 отказаться от фичи
- `backend-middle-a-teamwork-2` · teamwork · *«Как правильно провести разбор инцидента?»*
  - o1 найти и наказать виновного · o2 списать на «случайность» · **o3 blameless-разбор: причины и процессы, а не поиск виноватых ✓** · o4 не разбирать

**Variant B**

- `backend-middle-b-python-1` · python · *«Что делает `@staticmethod`?»*
  - o1 привязывает к экземпляру · o2 автоматически вызывает `super()` · **o3 объявляет метод без `self`/`cls` ✓** · o4 кэширует результат
- `backend-middle-b-python-2` · python · *«Чем корректно параллелить CPU-bound код в CPython?»*
  - o1 `threading` для вычислений · **o2 `multiprocessing` ✓** · o3 `asyncio` для CPU · o4 `yield`-цикл
- `backend-middle-b-sql-1` · sql · *«Чем `RANK()` отличается от `DENSE_RANK()`?»*
  - **o1 `RANK` оставляет пропуски при ничьих, `DENSE_RANK` — нет ✓** · o2 наоборот · o3 они идентичны · o4 `DENSE_RANK` только в PostgreSQL
- `backend-middle-b-sql-2` · sql · *«Какой уровень изоляции исключает non-repeatable reads?»*
  - o1 Read Uncommitted · o2 Read Committed · **o3 Repeatable Read ✓** · o4 все три
- `backend-middle-b-api-1` · api · *«Какие HTTP-методы идемпотентны по спецификации?»*
  - o1 только `GET` · o2 `POST` и `PATCH` · **o3 `GET`, `PUT`, `DELETE` ✓** · o4 все методы
- `backend-middle-b-api-2` · api · *«Что даёт HATEOAS в REST API?»*
  - o1 сжатие ответов · o2 авторизацию · **o3 ссылки в ответах для навигации по ресурсам ✓** · o4 кэширование
- `backend-middle-b-teamwork-1` · teamwork · *«Как убедить команду принять ваше архитектурное решение?»*
  - o1 настоять, потому что вы опытнее · **o2 оформить RFC с trade-off и данными, обсудить открыто ✓** · o3 решить единолично · o4 проигнорировать возражения
- `backend-middle-b-teamwork-2` · teamwork · *«Junior регулярно срывает сроки. Что делать?»*
  - o1 перестать давать задачи · o2 делать за него · **o3 выяснить причину (навыки/процесс/оценка) и выстроить план ✓** · o4 просто чаще напоминать

### 11.3 Frontend · Junior

**Variant A**

- `frontend-junior-a-javascript-1` · javascript · *«Какое ключевое слово объявляет блочную переменную?»*
  - **o1 `let` ✓** · o2 `var` · o3 `def` · o4 `int`
- `frontend-junior-a-javascript-2` · javascript · *«Какой метод возвращает новый массив из прошедших проверку элементов?»*
  - o1 `map` · o2 `forEach` · **o3 `filter` ✓** · o4 `reduce`
- `frontend-junior-a-typescript-1` · typescript · *«Какой тип — «строка или undefined»?»*
  - o1 `string | null` · **o2 `string | undefined` ✓** · o3 `string?` · o4 `optional<string>`
- `frontend-junior-a-typescript-2` · typescript · *«Что делает `interface`?»*
  - o1 копирует объект · **o2 описывает форму объекта, допускает расширение/слияние ✓** · o3 создаёт класс · o4 валидирует рантайм
- `frontend-junior-a-react-1` · react · *«Какой хук хранит локальное состояние?»*
  - **o1 `useState` ✓** · o2 `useEffect` · o3 `useMemo` · o4 `useContext`
- `frontend-junior-a-react-2` · react · *«Зачем нужен `key` в списках?»*
  - o1 для CSS · o2 это id DOM-узла · **o3 React использует его для эффективного reconciliation ✓** · o4 не нужен
- `frontend-junior-a-teamwork-1` · teamwork · *«Коллега просит отревьюить его PR. Лучший первый шаг?»* — как backend-junior-a-teamwork-1
- `frontend-junior-a-teamwork-2` · teamwork · *«Как лучше сообщить о блокере?»* — как backend-junior-a-teamwork-2

**Variant B**

- `frontend-junior-b-javascript-1` · javascript · *«Какое ключевое слово НЕ блочное и допускает переприсвоение?»*
  - o1 `let` · **o2 `var` ✓** · o3 `const` · o4 `static`
- `frontend-junior-b-javascript-2` · javascript · *«Какой метод применяет функцию к каждому элементу и возвращает новый массив?»*
  - **o1 `map` ✓** · o2 `filter` · o3 `forEach` · o4 `some`
- `frontend-junior-b-typescript-1` · typescript · *«Какой тип отключает проверку типов для любого значения?»*
  - **o1 `any` ✓** · o2 `unknown` · o3 `never` · o4 `void`
- `frontend-junior-b-typescript-2` · typescript · *«Что задаёт `type`?»*
  - o1 создаёт интерфейс · **o2 объявляет псевдоним типа ✓** · o3 импортирует модуль · o4 объявляет переменную
- `frontend-junior-b-react-1` · react · *«Какой хук выполняет side effects после рендера?»*
  - o1 `useState` · **o2 `useEffect` ✓** · o3 `useRef` · o4 `useCallback`
- `frontend-junior-b-react-2` · react · *«Как обновить состояние, зависящее от предыдущего значения, корректно?»*
  - o1 `setCount(count + 1)` всегда · **o2 `setCount(prev => prev + 1)` ✓** · o3 менять переменную напрямую · o4 `useEffect`
- `frontend-junior-b-teamwork-1` · teamwork · *«Как воспринимать комментарии к своему PR?»* — как backend-junior-b-teamwork-1
- `frontend-junior-b-teamwork-2` · teamwork · *«Как лучше описать техническую проблему?»* — как backend-junior-b-teamwork-2

### 11.4 Frontend · Middle

**Variant A**

- `frontend-middle-a-javascript-1` · javascript · *«Что такое замыкание (closure)?»*
  - o1 функция без имени · **o2 функция с доступом к внешней области видимости после возврата ✓** · o3 цикл · o4 класс
- `frontend-middle-a-javascript-2` · javascript · *«В стрелочной функции `this` …»*
  - o1 динамический, от вызова · **o2 лексический, из внешней области ✓** · o3 всегда `window` · o4 всегда `undefined`
- `frontend-middle-a-typescript-1` · typescript · *«Зачем нужны generics `<T>`?»*
  - o1 ускорить компиляцию · **o2 переиспользуемый код с сохранением типов ✓** · o3 обфусцировать · o4 заменить any
- `frontend-middle-a-typescript-2` · typescript · *«Что даёт `Partial<T>`?»*
  - **o1 все свойства необязательные ✓** · o2 только выбранные ключи · o3 readonly-версию · o4 объединение типов
- `frontend-middle-a-react-1` · react · *«Что делает `useMemo`?»*
  - o1 мемоизирует функцию · **o2 мемоизирует вычисленное значение ✓** · o3 создаёт состояние · o4 подписку
- `frontend-middle-a-react-2` · react · *«Что такое «prop drilling» и как его избежать?»*
  - o1 передача стилей через props · **o2 проброс props через много уровней; решается Context/композицией ✓** · o3 ошибка типов · o4 мемоизация
- `frontend-middle-a-teamwork-1` · teamwork · *«Бизнес требует фичу, а вы видите критический техдолг. Как поступить?»* — как backend-middle-a-teamwork-1
- `frontend-middle-a-teamwork-2` · teamwork · *«Как правильно провести разбор инцидента?»* — как backend-middle-a-teamwork-2

**Variant B**

- `frontend-middle-b-javascript-1` · javascript · *«Что выполнится раньше: `setTimeout` или `Promise.then`?»*
  - o1 `setTimeout` всегда · **o2 microtask `Promise.then` раньше timer ✓** · o3 зависит от браузера · o4 одновременно
- `frontend-middle-b-javascript-2` · javascript · *«Хойстятся ли `let`/`const`?»*
  - o1 нет, вообще · **o2 да, но в temporal dead zone до инициализации (ReferenceError) ✓** · o3 да, как `var` · o4 только `const`
- `frontend-middle-b-typescript-1` · typescript · *«Что возвращает `keyof T`?»*
  - o1 массив значений · **o2 объединение ключей типа ✓** · o3 количество ключей · o4 строку
- `frontend-middle-b-typescript-2` · typescript · *«Что даёт `Pick<T, K>`?»*
  - o1 все ключи · **o2 тип только с выбранными ключами ✓** · o3 исключает ключи · o4 readonly
- `frontend-middle-b-react-1` · react · *«Что делает `useCallback`?»*
  - o1 мемоизирует значение · **o2 мемоизирует ссылку на функцию ✓** · o3 вызывает колбэк · o4 подписку на события
- `frontend-middle-b-react-2` · react · *«Что делает `React.memo`?»*
  - **o1 пропускает ре-рендер при shallow-equal пропсах ✓** · o2 мемоизирует состояние · o3 создаёт контекст · o4 кэширует запросы
- `frontend-middle-b-teamwork-1` · teamwork · *«Как убедить команду принять ваше архитектурное решение?»* — как backend-middle-b-teamwork-1
- `frontend-middle-b-teamwork-2` · teamwork · *«Junior регулярно срывает сроки. Что делать?»* — как backend-middle-b-teamwork-2

### 11.5 Teamwork (общий набор)

Идентичный для `backend` и `frontend` (soft-skill не зависит от специализации). Полные формулировки — в §11.1–11.4;
здесь — эталонные ключи:

| id-шаблон | junior | middle |
|---|---|---|
| teamwork-1 (A) | конструктивный фидбек ✓ | техдолг vs фича: риски + приоритет на данных ✓ |
| teamwork-2 (A) | блокер с контекстом ✓ | blameless-разбор инцидента ✓ |
| teamwork-1 (B) | комментарии = обсуждение ✓ | архитектурное решение: RFC + trade-off ✓ |
| teamwork-2 (B) | пробовал + ожидание/факт ✓ | срыв сроков: причина + план ✓ |

---

## 12. Архив v2 JSON (не использовать как эталон v3)

```json
{
  "schemaVersion": 1,
  "version": "v1",
  "status": "APPROVED",
  "provenance": "DS",
  "id": "backend-junior",
  "catalogVersion": "v1-demo",
  "specialization": "backend",
  "grade": "junior",
  "slots": [
    {"id":"python-1","skillId":"python","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"python-2","skillId":"python","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"sql-1","skillId":"sql","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"sql-2","skillId":"sql","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"api-1","skillId":"api","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"api-2","skillId":"api","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"teamwork-1","skillId":"teamwork","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"},
    {"id":"teamwork-2","skillId":"teamwork","questionType":"single_choice","maxScore":1.0,"weight":1.0,"rubricId":"exact"}
  ],
  "rubric": [
    {"id":"exact","kind":"single_choice_exact","correctFraction":1.0,"incorrectFraction":0.0,"unansweredFraction":0.0}
  ],
  "scoring": {
    "formula": "weighted_normalized_sum",
    "scaleMin": 0,
    "scaleMax": 100.0,
    "thresholds": {"passScore":66.6666667,"highScore":83.3333333,"passInclusive":true,"highInclusive":true}
  },
  "variants": [
    {
      "id": "A",
      "questions": [
        {"id":"backend-junior-a-python-1","slotId":"python-1","type":"single_choice",
         "prompt":"Какой тип в Python неизменяем?",
         "options":[{"id":"o1","text":"list"},{"id":"o2","text":"dict"},{"id":"o3","text":"tuple"},{"id":"o4","text":"set"}],
         "answerKey":{"optionId":"o3"}}
      ]
    },
    {"id":"B","questions":[]}
  ]
}
```

Полные 8 вопросов каждого варианта берутся из §11.1; для остальных трёх ячеек — из §11.2–11.4 по той же схеме
(слоты `api-*` у frontend заменяются на `typescript-*` и `react-*`, каждый навык = 2 слота).

---

## 13. Что обязан реализовать backend (SPR-15, v3)

### 13.1 Миграция и неизменяемые данные

- `candidate_profiles.verified_grade` (nullable, `IN ('junior','middle','senior')`) и
  `last_grade_change_at` (`timestamptz`, nullable).
- `test_attempts`: `specialization`, `blueprint_version`, `variant_id`, `technical_score`,
  `teamwork_subscore`, `result` (`fail`/`pass`/`high`), `retest_target_grade`,
  `retest_available_at`, `submitted_at`. Ответы, вариант и snapshot не меняются после start.
- `competency_scores`: три технических score с `source='test'`; teamwork — отдельный `source='assessment_diagnostic'`,
  чтобы диагностический ответ невозможно было случайно использовать как квалификационный.

### 13.2 Скоррер (чистая функция, без I/O)

```text
slotScore = 1.0 if answer.optionId == answerKey.optionId else 0.0
technicalCorrect = count(correct questions where any technical skillTags exist)
technicalTotal = technicalCorrect / 18 * 100
teamworkSubscore = mean(teamwork slotScore) * 100
skillSubscore[tag] = correct(tagged tag) / total(tagged tag) * 100
result = high if correct >= 16 and all(core >= 70) else pass if correct >= 13 and all(core >= 50) else fail
```

Пропуск и неверный ответ равны нулю. В ответе API возвращаются оба сигнала с явными именами; UI не называет
`teamworkSubscore` частью подтверждённого грейда.

### 13.3 Grade policy

- `POST /assessments/start`: кандидат выбирает предполагаемый грейд; backend выбирает форму из пула; для
  следующего повышения разрешён только соседний грейд. Нет blueprint → `422`; активная попытка → `409`;
  cooldown → `409` с `retest_available_at`.
- `GET /assessments/{id}`: только owner; без `answerKey`, rubric, внутренних весов и других форм.
- `POST /assessments/{id}/submit`: атомарно сохраняет результат ровно один раз; повторный submit возвращает
  сохранённый результат, не пересчитывает и не изменяет историю. Обновляет категорию только по §9.
- Кандидат без подтверждённой категории не попадает в employer search. Его UI показывает понятное действие:
  lower-retest либо повтор после доступной даты.

### 13.4 Тесты (обязательные)

- границы `12/18 → fail`, `13/18 → pass`, `16/18 → high`, включая core-skill gates; teamwork не изменяет итог;
- утечка `answerKey`, owner/RBAC, повторный submit, блокировка cooldown, lower-retest, senior без blueprint;
- одна и та же синтетическая персона на всех формах получает одинаковое verified/unverified решение;
- junior-персона не проходит middle, middle-персона проходит middle;
- форма C/item-pool обязателен для strict validation; до него релизный gate не зелёный.

---

## 14. Контракт подбора: категория — gate, ФСП — только boost внутри неё

Это фиксирует требование ТЗ: выдача строится по категории, присвоенной тестом, а не по самоописанию; внутри
категории выше сильный тестовый профиль и подтверждённые достижения ФСП.

### 14.1 Eligibility (до ранжирования)

Кандидат допускается в snapshot только если одновременно: verified email, publication consent, есть
`verified_specialization == need.specialization`, есть `verified_grade >= need.minGrade` и есть submitted attempt,
который зафиксировал эту категорию. Самозаявленный грейд, стек в свободном тексте, наличие ФСП или высокий
score сами по себе не создают eligibility. `no_history` ФСП допустим и даёт `fspScore=0`, а не исключение.

### 14.2 Детерминированный score внутри eligibility cohort

```
rankScore = 0.50 * skillFit + 0.35 * testStrength + 0.15 * fspBonus
```

- `skillFit` — покрытие требуемых/опциональных **канонических технических** навыков из need тестовыми
  competency scores: `0.80 * requiredCoverage + 0.20 * optionalCoverage`. Если optional отсутствуют, их доля
  перераспределяется в requiredCoverage.
- `testStrength` — нормализованный `technical_score` попытки, которая установила текущий verified grade.
  Teamwork не входит.
- `fspBonus` — только подтверждённые достижения; 0 при `no_history`. Может включать опубликованную mapping
  «дисциплина ФСП → специализация» и давность, но fallback без mapping — общий небольшой бонус. Он ограничен 0..1
  и не может преодолеть eligibility gate. Демо-нормализация описана в
  [`../../FSP_DEMO_ACHIEVEMENTS.md`](../../FSP_DEMO_ACHIEVEMENTS.md): синтетический файл,
  явный флаг `FSP_DEMO_MODE`, тип/роль/стек/давность, максимум одного рекорда.
  Это **имитация реестра**, не реальная верификация ФСП; в production бонус отключён.

Tie-breaker: `rankScore DESC`, затем `technical_score DESC`, затем стабильный `candidate_id ASC`. Snapshot хранит
версии алгоритма, исходные компоненты, причины и порядок; фильтры применяются к нему, не создавая новый ranking.

### 14.3 Объяснение работодателю

Карточка выдаёт только вычисленные факты: «подтверждённый Backend Middle», «2/3 требуемых навыка»,
«технический тест 88.9%», «Python evidence 78%», «подтверждённое достижение ФСП: …» либо «истории ФСП нет». Она не раскрывает raw
answers, contacts или неаудированные предположения модели.

---

## 15. Валидация для жюри

[`../arch/validate_v3_skill_agents.py`](../arch/validate_v3_skill_agents.py)
— воспроизводимая question-level проверка synthetic agents с разными profile по skills. Она отделяет:

1. **test–retest:** одна персона проходит все формы своей ячейки; сравнивается verified/unverified category,
   а не требование совпасть до десятых долей score;
2. **discrimination:** junior-персона не проходит middle-формы, middle-персона проходит;
3. **pool completeness:** строгий режим требует минимум три формы на ячейку.

```bash
python3 arch/build_assessment_v3.py
python3 arch/validate_v3_skill_agents.py
```

Первый запуск даёт диагностический отчёт. Второй — тот же отчёт в CI/release flow; при нарушении формы пула,
стабильности категории или разделения он завершится с ошибкой. На текущем стартовом A/B/C-пуле strict gate проходит,
но это ещё не доказательство качества на реальной аудитории.

Ограничение: synthetic agents — проверяемые допущения команды, не доказательство качества на реальной
популяции. В финальной документации нужно приложить таблицу persona × form × decision, экспертную проверку
каждого item и, если успеете, небольшой anonymised pilot/labelled fixture. Аналогично matching валидируется
отдельно на размеченных парах need–candidate через Precision@3 и объяснение top-3.
