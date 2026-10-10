# Бизнес-логика — пакет для команды и интеграции

## Канонические файлы

| Файл | Назначение | Потребитель |
|---|---|---|
| `ASSESSMENT_AND_MATCHING_CONTRACT.md` | Полный v3 контракт: scoring, category, retest, cooldown, ranking | backend, product, QA |
| `TEAM_QA.md` | Краткие ответы команды с ссылками на развёрнутые правила | вся команда |
| `questions-v3.json` | Импортируемый question pool: 4 ячейки × A/B/C × 20 вопросов | backend seed / assessment service |
| `USE_CASES_AND_MECHANISMS.md` | Сквозные use cases, автоматы состояний, eligibility и privacy | frontend, backend, QA |

## Интеграция question pool

`questions-v3.json` имеет верхний ключ `<specialization>-<grade>`, например `backend-middle`, затем формы `A/B/C`.

Каждый question содержит:

```json
{
  "id": "backend-middle-A-python-1",
  "skillTags": ["python"],
  "type": "single_choice",
  "prompt": "...",
  "options": [{"id": "o1", "text": "..."}],
  "answerKey": {"optionId": "o3"},
  "maxScore": 1.0
}
```

`answerKey` — server-only поле. Публичный DTO удаляет его до отправки кандидату.

## Инварианты импорта

Для каждой `specialization-grade-form`:

- 20 questions, включая 18 technical и 2 diagnostic teamwork;
- каждый technical core skill встречается ровно в 9 tagged questions;
- `skillTags` содержит 1–3 canonical IDs;
- ответные позиции детерминированно перемешаны; нельзя предполагать, что верный ответ всегда `o1`;
- перед публикацией проверить expert-review content и создать immutable blueprint version + manifest checksum.

## Статус

Business rules v3 зафиксированы. Question content — candidate pool до domain expert review. Нельзя заявлять его как психометрически калиброванный без pilot/labelled validation.
