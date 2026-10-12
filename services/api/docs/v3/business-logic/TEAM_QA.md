> **Исторический снимок.** Этот документ отражает состояние до удаления разделения demo/real/test
> (флаги `DEMO`/`APPROVED`/`content_status` удалены, миграция `0012`, квалификация — по баллу).
> Актуальное состояние — в [`README.md`](../../README.md) и [`docs/JURY.md`](../../docs/JURY.md).

# Зафиксированные решения по тестированию — для команды

> Статус: **DRAFT v3**. Это быстрый вопрос–ответ для согласования новой multi-tag модели. Нормативный источник —
> [`ASSESSMENT_AND_MATCHING_CONTRACT.md`](ASSESSMENT_AND_MATCHING_CONTRACT.md); если этот файл и контракт расходятся, верен контракт.

| № | Вопрос команды | Зафиксированный ответ | Развёрнуто |
|---:|---|---|---|
| 1 | Какие specialization и grades? | `backend` / Backend Python и `frontend` / Frontend React. Тестируемые grades: `junior`, `middle`. `senior` присутствует в таксономии, но blueprint для него нет: start → `422`. | [§1](ASSESSMENT_AND_MATCHING_CONTRACT.md#1-специализации-и-допустимые-грейды) |
| 2 | Какие skill IDs на ячейку? | Backend: `python`, `sql`, `api`, `teamwork`; Frontend: `javascript`, `typescript`, `react`, `teamwork`. Первые три — technical grade; `teamwork` — diagnostic-only. Каждый question содержит 1–3 `skillTags`. | [§2](ASSESSMENT_AND_MATCHING_CONTRACT.md#2-навыки-на-ячейку-4-фиксировано-совпадает-с-catalog), [§3](ASSESSMENT_AND_MATCHING_CONTRACT.md#3-структура-blueprint-20-questions-multi-tag-evidence) |
| 3 | Какие variants нужны? | A/B — две обязательные изоморфные формы blueprint. C — резервная форма пула: используется при retest/ротации, чтобы не показать человеку уже виденную форму. | [§0](ASSESSMENT_AND_MATCHING_CONTRACT.md#0-tldr--зафиксированные-значения), [§7](ASSESSMENT_AND_MATCHING_CONTRACT.md#7-эквивалентность-форм-пула-инвариант), [`questions-v3.json`](questions-v3.json) |
| 4 | Что хранит вопрос? | `id`, `slotId`, `skillTags`, `type=single_choice`, 4 options, ровно один `answerKey.optionId`; `maxScore=1.0`, rubric `exact`. Answer key никогда не отдаётся кандидату. | [§3–§4](ASSESSMENT_AND_MATCHING_CONTRACT.md#3-структура-blueprint-20-questions-multi-tag-evidence) |
| 5 | Как считаются subscores и total? | Skill evidence = `% верных среди всех questions с данным tag`; верный multi-tag item повышает evidence всех его tags. Technical total считает каждый из 18 technical questions один раз. Teamwork diagnostic-only. | [§5](ASSESSMENT_AND_MATCHING_CONTRACT.md#5-rubric-и-подсчёт-баллов) |
| 6 | Какие pass/high thresholds и границы? | `FAIL`: <13/18 либо любой core skill <50%; `PASS`: 13–15/18 и каждый core ≥50%; `HIGH`: 16–18/18 и каждый core ≥70%. Сравнение по integer count и evidence, не с float epsilon. | [§6](ASSESSMENT_AND_MATCHING_CONTRACT.md#6-пороги-и-поведение-на-границах) |
| 7 | Как гарантируем эквивалентность A/B? | Одинакова tag-incidence matrix, weights, maxScore, rubric и сложность; меняются только кейс/данные/формулировка. Scorer не читает variant ID. | [§7](ASSESSMENT_AND_MATCHING_CONTRACT.md#7-эквивалентность-форм-пула-инвариант) |
| 8 | Как версионируем blueprint? | Опубликованный blueprint неизменяем. Любой content/threshold/tag/slot change создаёт `v3+`, новый sha256 и manifest pointer. Started attempt хранит snapshot, version и variant. | [§8](ASSESSMENT_AND_MATCHING_CONTRACT.md#8-версионирование-blueprint) |
| 9 | Что происходит при fail/pass/high? | FAIL не понижает grade; без текущего verified grade на Middle предлагает Junior. PASS подтверждает/повышает выбранный grade. HIGH подтверждает/повышает и предлагает следующий grade. Нельзя перепрыгнуть через соседний grade после подтверждения. | [§9](ASSESSMENT_AND_MATCHING_CONTRACT.md#9-поведение-грейда-при-fail--pass--high) |
| 10 | Как работает 90-day cooldown? | Начинается только когда PASS/HIGH впервые устанавливает или повышает `verified_grade`. До `last_grade_change_at + 90d` блокирует тест на тот же или выше grade (`409` + `retest_available_at`). FAIL cooldown не запускает; первый lower-retest без category разрешён. | [§10](ASSESSMENT_AND_MATCHING_CONTRACT.md#10-правило-90-дневного-cooldown) |

## Перед реализацией

- Backend переносит только значения и transitions из контракта; не копирует v2 total из 6/8 slots или старые пороги.
- Перед публикацией C: экспертный review вопросов → новая immutable версия → `python3 ../arch/validate_v3_skill_agents.py`.
- Для подбора: category — eligibility gate; ФСП — только bonus внутри eligible cohort. См. [§14 контракта](ASSESSMENT_AND_MATCHING_CONTRACT.md#14-контракт-подбора-категория--gate-фсп--только-boost-внутри-неё).
