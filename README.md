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

Тест миграций создаёт отдельную временную БД `fsp_test_<uuid>` и удаляет её после проверки; пользователь PostgreSQL должен иметь право `CREATEDB` (пользователь образа `postgres:16` имеет его). Выполняются два `upgrade head` и `downgrade base`; после downgrade таблица `alembic_version` остаётся пустой. Прикладных таблиц пока нет.

Для локального запуска тестов из `services/api` установите зависимости из `requirements.txt`, задайте `POSTGRES_HOST=localhost` и выполните `pytest tests/integration/test_migrations.py -v`. Остальные настройки читаются из корневого `.env`; переменные окружения имеют приоритет.

Если запуск не работает:

- Убедитесь, что Docker Desktop запущен и `.env` создан из `.env.example`.
- После изменения зависимостей выполните сборку API: `docker compose -f infra/docker-compose.yml build api`.
- Для диагностики БД используйте `docker compose -f infra/docker-compose.yml logs postgres api` и `docker compose -f infra/docker-compose.yml ps`.
- HTTP 503 на `/health/ready` означает, что БД недоступна, настройки подключения неверны или проверка превысила таймаут. После остановки PostgreSQL запустите его командой `docker compose -f infra/docker-compose.yml start postgres`.
- Ошибка `permission denied to create database` в тесте требует роли с правом `CREATEDB`; тест не использует рабочую БД для downgrade.
- Изменение `POSTGRES_USER`, `POSTGRES_PASSWORD` или `POSTGRES_DB` в `.env` не меняет уже инициализированный volume. Для демо с новыми настройками используйте `bash demo-reset.sh --purge`, учитывая удаление данных.
