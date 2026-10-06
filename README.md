Запуск (перед первым запуском скопируйте `.env.example` в `.env`):

```sh
docker compose -f infra/docker-compose.yml up --build
```

- Web: http://localhost:3000 — Next.js 14, TypeScript, Tailwind CSS; заглушка и прокси `/api/*`.
- API: http://localhost:8000 — FastAPI; `GET /health/live` возвращает `{"status":"ok"}`.
- Swagger: http://localhost:8000/docs — документация API.
- Mailpit UI: http://localhost:8025 — просмотр писем; SMTP на порту 1025.
- PostgreSQL 16 — база данных на порту 5432; данные в volume `pgdata`.

Остановка:

```sh
docker compose -f infra/docker-compose.yml down
```

Удаление volumes:

```sh
docker compose -f infra/docker-compose.yml down -v
```

База данных и миграции:

```sh
docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head
docker compose -f infra/docker-compose.yml run --rm api python -m app.commands.seed_demo
```

`GET /health/ready` проверяет БД: HTTP 200 с `{"status":"ok","db":"ok"}` или HTTP 503 с `{"status":"error","db":"unavailable"}`. Проверка ограничена таймаутом 0,8 секунды. `/health/live` не зависит от доступности БД.

Подготовка демо (Git Bash, WSL или Linux):

```sh
bash demo-reset.sh
```

Для полного сброса с удалением данных используйте `bash demo-reset.sh --purge`. Скрипт ждёт PostgreSQL healthy, собирает образ API, применяет миграции и запускает seed. Остальные сервисы после сброса запускаются обычной командой Compose.

Тесты внутри Docker:

```sh
docker compose -f infra/docker-compose.yml run --rm api pytest tests/integration/test_migrations.py -v
docker compose -f infra/docker-compose.yml run --rm api pytest -v
```

Интеграционные тесты создают отдельные временные БД `fsp_test_<uuid>` и удаляют их после проверки; пользователь PostgreSQL должен иметь право `CREATEDB` (пользователь образа `postgres:16` имеет его). Тест миграций проверяет точный список таблиц и колонок, согласованность с ORM, повторный `upgrade head`, `downgrade base` и восстановление схемы. После downgrade остаётся только пустая таблица `alembic_version`.

Доменные таблицы (миграции `17dada67f98e` → `0002`):

- `users`, `consents`, `candidate_profiles`, `companies`, `hiring_needs`;
- `test_attempts`, `competency_scores`, `fsp_links`, `fsp_achievements`;
- `recommendation_snapshots`, `recommendation_items`, `invitations`, `contact_disclosures`, `audit_events`.

Демо-данные: 10 кандидатов (5 Backend Python и 5 Frontend React), грейды junior/middle, 2 работодателя и 4 потребности в найме. У 7 кандидатов статус ФСП `no_history`; у 3 — `linked`, всего 4 достижения. Также создаются 34 согласия и 30 оценок компетенций. Остальные доменные таблицы пока пустые. Все имена, контакты и достижения синтетические.

Фикстуры находятся в `services/api/app/commands/seed/`: `catalog.json`, `candidates.json`, `employers.json`, `fsp_evidence.json`. Демо-аккаунты: `candidate1@demo.example` … `candidate10@demo.example`, `employer1@demo.example`, `employer2@demo.example`. Демонстрационный пароль и готовый bcrypt-хеш находятся в JSON-фикстурах; в БД сохраняется только хеш. Auth-модуль ещё не реализован.

Проверка идемпотентности:

```sh
docker compose -f infra/docker-compose.yml run --rm api alembic upgrade head
docker compose -f infra/docker-compose.yml run --rm api python -m app.commands.seed_demo
docker compose -f infra/docker-compose.yml run --rm api python -m app.commands.seed_demo
docker compose -f infra/docker-compose.yml run --rm api pytest tests/integration/test_seed.py -v
```

Оба запуска выводят `seed completed`. Тест запускает тот же `main()` дважды на временной БД и сравнивает количество записей во всех таблицах, включая `alembic_version`. Дополнительно проверяются отсутствие дублей, демо-сценарии ФСП, сохранение пользовательских правок и откат транзакции при ошибке.

Seed пропускает существующие записи: ключи — email пользователя, user_id профиля/компании, `(user_id, kind)` согласия, `(company_id, title)` потребности, `(candidate_id, competency, source)` оценки, candidate_id ссылки ФСП и `(candidate_id, discipline, competition)` достижения. Уникальность защищена БД; nullable-части составных ключей используют `NULLS NOT DISTINCT` в PostgreSQL 16. Изменённые пользователем данные повторный seed не перезаписывает. Справочники из JSON не создают дополнительных таблиц.

Для локального запуска тестов из `services/api` установите зависимости из `requirements.txt`, задайте `POSTGRES_HOST=localhost` и выполните `pytest tests/integration/test_migrations.py -v`. Остальные настройки читаются из корневого `.env`; переменные окружения имеют приоритет.

Если запуск не работает:

- Убедитесь, что Docker Desktop запущен и `.env` создан из `.env.example`.
- После изменения зависимостей выполните сборку API: `docker compose -f infra/docker-compose.yml build api`.
- Для диагностики БД используйте `docker compose -f infra/docker-compose.yml logs postgres api` и `docker compose -f infra/docker-compose.yml ps`.
- HTTP 503 на `/health/ready` означает, что БД недоступна, настройки подключения неверны или проверка превысила таймаут. После остановки PostgreSQL запустите его командой `docker compose -f infra/docker-compose.yml start postgres`.
- Ошибка `permission denied to create database` в тесте требует роли с правом `CREATEDB`; тест не использует рабочую БД для downgrade.
- Если seed сообщает `relation ... does not exist`, сначала выполните `alembic upgrade head` через сервис api. Команда `docker compose -f infra/docker-compose.yml run --rm api alembic current` должна показать `0002 (head)`.
- Если миграция не найдена, проверьте наличие обоих файлов в `services/api/alembic/versions/`. Не исправляйте это через `stamp head`: он не создаёт таблицы. Проверка `docker compose -f infra/docker-compose.yml run --rm api alembic check` выявляет расхождения ORM и схемы.
- При ошибке seed вся его транзакция откатывается. Исправьте данные фикстур или причину ошибки и повторите команду; существующие записи сохранятся.
- Изменение `POSTGRES_USER`, `POSTGRES_PASSWORD` или `POSTGRES_DB` в `.env` не меняет уже инициализированный volume. Для демо с новыми настройками используйте `bash demo-reset.sh --purge`, учитывая удаление данных.
