# Фиксированный диагностический банк: пять ролей × три грейда

**Роли:** Backend, Frontend, Fullstack, ML-инженер, Data Engineer. **Грейды:** Junior, Middle, Senior. Широкая таксономия технологий остаётся для поиска, но диагностический тест теперь проверяет ровно [пять ключевых навыков на роль](../app/modules/recommendations/config/assessment-core.v1.json).

| Роль | Пять навыков |
|---|---|
| Backend | Python, SQL, API/HTTP, PostgreSQL, Docker |
| Frontend | JavaScript, TypeScript, React, HTML, CSS |
| Fullstack | JavaScript, React, Node.js, API/HTTP, Docker |
| ML-инженер | Python, NumPy, pandas, scikit-learn, PyTorch |
| Data Engineer | Python, SQL, PostgreSQL, Kafka, Airflow |

[Статический банк полных вопросов и вариантов](../app/data/taxonomy/questions.v4.jsonl), [манифест SHA-256](../app/data/taxonomy/manifest.v4.json) и [авторские предметные карточки](../app/data/taxonomy/curated_cards.v1.json): **15** ячеек, **45** форм A/B/C, **900** вопросов-экземпляров. Каждая форма содержит 20 вопросов, по четыре на навык. 684 экземпляра опираются на новые grade-specific сценарии, 216 — на содержательные MVP-вопросы. Четыре наблюдения по навыку пока не всегда независимы: в ряде ячеек одна карточка перефразирована несколько раз. Разделения demo/approved у форм нет (статусная колонка удалена миграцией `0012`).

## Хранение и выдача

Миграция `0011` создаёт `taxonomy_question_forms`; `python -m app.commands.import_taxonomy_questions` идемпотентно импортирует 45 неизменяемых форм из статического источника. Сервер получает вопросы **только из БД**. При старте случайно выбирается ещё не использованная A/B/C и случайно меняется порядок уже заготовленных вопросов; порядок и ключи пинуются в попытке. В публичном API нет `answerKey`/`skillTags`. Дефектная или неполная БД даёт 503, не скрытый fallback к файлу.

`GET /assessments/taxonomy/catalog`, `POST /assessments/taxonomy/start`, `GET /assessments/taxonomy/{id}`, `POST /assessments/taxonomy/{id}/submit`. Итог и доли ответов по тегам видны как `diagnosticSkills`; грейд/роль **не подтверждаются** (это диагностический трек). В ранжирование попадают `verifiedSkills` из подтверждающего v3-трека, который покрывает `backend/frontend/fullstack × junior/middle/senior`.

## Данные и проверка разделения

[1000 синтетических кандидатов](../tests/fixtures/taxonomy/candidates.v1.jsonl), [50 запросов](../tests/fixtures/taxonomy/needs.v1.json) — гипотетические данные, не истинные грейды и не реальные вакансии.

[Негативный контроль: агенты по публичному тексту](validation/visible_grade_agents_v1.md): прежний обход «подсказка-категория» позволял Junior пройти **все** формы Junior/Middle/Senior. На новом банке этот агент не имеет категорийной подсказки и не проходит ни одну форму. Это устраняет конкретную утечку, **но не доказывает**, что специалист нужного грейда пройдёт тест: простой rule-agent без предметного знания тоже не проходит. [Модельная симуляция](validation/taxonomy_simulation_v2.md) даёт pass своего грейда 65,9%, соседнего выше 3,33%, одинаковое решение A/B/C лишь **58,5%**. Вероятности ответа и дополнительная сложность грейда заданы моделью, не измерены у людей. Следовательно, стабильность неудовлетворительна и содержательная разделяющая сила **не установлена**. Для подтверждающего трека требуются независимые сценарии в каждой форме, ревью ключей и слепой пилот Junior/Middle/Senior.

## Воспроизведение

```sh
SYNTHETIC_PASSWORD='<пароль от 12 символов>' bash demo-reset.sh --purge
docker compose -f infra/docker-compose.yml run --rm --no-deps api pytest -q
docker compose -f infra/docker-compose.yml exec -T web npm run typecheck
```

`demo-reset.sh --purge` удаляет только Compose-БД проекта и заново создаёт 30 кандидатов, 5 работодателей/потребностей и 45 новых вопросных форм. Большие файлы 1000/50 сохраняются отдельно для офлайн-анализа. Это нельзя делать на БД с реальными пользователями.
