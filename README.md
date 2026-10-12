# ФСП · IT-подбор (демо)

## Сброс и запуск

Скопируйте `.env.example` в `.env`. **Следующая команда безвозвратно удаляет только Docker Compose volume PostgreSQL этого проекта**, затем создаёт актуальную схему (head, миграция `0012`) и заполняет БД фиксированными вопросами и новой синтетикой:

```sh
SYNTHETIC_PASSWORD='<свой пароль минимум 12 символов>' bash demo-reset.sh --purge
```

Скрипт отказывается работать без `--purge` и пароля. Результат: **30** синтетических кандидатов, **5** работодателей с 5 потребностями и **45** неизменяемых A/B/C форм вопросов. Существующие квалификации новым кандидатам **не присваиваются**. Вопросы доступны только из таблицы `taxonomy_question_forms`; при запросе сервер случайно выбирает ещё не показанный вариант и перемешивает порядок уже сохранённых вопросов. Исходный статический JSON в `services/api/app/data/taxonomy/` нужен для воспроизводимого импорта при следующем развёртывании, но **не** используется как runtime-БД вопросов. Генератора текста вопросов нет.

Адреса: Web http://localhost:3000 · API http://localhost:8000 · Swagger http://localhost:8000/docs · Mailpit http://localhost:8025.

Без пересоздания БД:

```sh
docker compose -f infra/docker-compose.yml up -d
```

## Активная область

Два трека тестирования:

- **Подтверждающий v3** (`POST /assessments/*`) — `backend`, `frontend`, `fullstack` × `junior`, `middle`, `senior` (9 ячеек). 20 вопросов на форму (18 technical + 2 teamwork), 9 наблюдений на каждый core-навык. Подтверждает грейд **по баллу**: 13/18 pass + per-skill ≥50%, 16/18 high + ≥70%. Разделения demo/real/test нет — весь контент равноценен.
- **Диагностический taxonomy** (`/assessments/taxonomy/*`) — 5 ролей (добавлены `ml_engineer`, `data_engineer`) × 3 грейда, 45 форм A/B/C, 900 вопросов. Даёт `diagnosticRole/Grade/Skills` в профиль, грейд **не** подтверждает. (Остаточный дубль — планируется сведение к единому треку на 3 ролях.)

Достижения ФСП — демонстрационный реестр [`demo_registry.v1.json`](services/api/app/modules/fsp/demo_registry.v1.json) (источник `fsp`), учитывается как ограниченный boost внутри подтверждённой категории.

[Документация для жюри](docs/JURY.md) · [Контракт вопросов и ограничения](services/api/docs/TAXONOMY_ASSESSMENT_DEMO.md) · [Таксономия и поиск похожих](services/api/docs/SIMILAR_TAXONOMY_V4.md) · [Синтетическая проверка](services/api/docs/validation/taxonomy_simulation_v2.md).

## Проверка

```sh
docker compose -f infra/docker-compose.yml run --rm api pytest -q
docker compose -f infra/docker-compose.yml exec -T web npm run typecheck
curl http://localhost:8000/health/ready
```

Тесты создают отдельные временные БД `fsp_test_<uuid>`; рабочую `fsp` они не очищают. При ручной сборке пустой БД: `alembic upgrade head`, затем `python -m app.commands.populate_taxonomy_demo_db` с `SYNTHETIC_PASSWORD` и `CONFIRM_SYNTHETIC_RESET=RESET_FSP_DEMO_ONLY`. Команда наполнения требует **пустые** доменные таблицы и отказывается объединять синтетику с существующими аккаунтами.
