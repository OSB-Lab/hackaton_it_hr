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
