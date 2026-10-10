# Генератор синтетических данных (MVP)

`generate_synthetic.py` создаёт **100 синтетических аккаунтов** (98 кандидатов + 2 работодателя)
для демонстрации и тестирования MVP «ФСП | ИТ-подбор».

## Что создаётся

- **98 кандидатов** в 7 группах состояний (сумма групп = 98):

| Группа | Кол-во | Отклонение (reasonCode) |
|---|---|---|
| `ready_except_qualification` | 20 | только `QUALIFICATION_UNCONFIRMED` |
| `specialization` | 10 | `SPECIALIZATION_MISMATCH` |
| `grade` | 10 | `GRADE_BELOW_MINIMUM` |
| `required_skills` | 10 | пустой `stack` |
| `publication` | 12 | `PUBLICATION_NOT_ALLOWED` |
| `email` | 12 | `EMAIL_UNVERIFIED` |
| `qualification` | 24 | только `QUALIFICATION_UNCONFIRMED` |

- **2 работодателя** — компании и потребности с `requiredSkills` и `optionalSkills`.
- **Обогащённые профили**: профессиональная роль, опыт (месяцы), телефон, soft skills,
  специализация/грейд/стек (детерминированно, без персональных данных реальных людей).
- **6 DEMO-попыток теста** (3 активные + 3 завершённые с DEMO-результатом). DEMO-контент
  **никогда не подтверждает квалификацию** (`verified_grade`/`verified_attempt_id` остаются `NULL`).

> Ни один синтетический кандидат не получает подтверждённой квалификации и фиктивных
> APPROVED-результатов. Положительный сценарий eligibility покрывается отдельными test-only
> фикстурами (см. `tests/integration/test_synthetic_generator.py::test_positive_eligibility_ranking_invitation`).

## Требования к окружению

1. **Изолированная БД** (не production/dev): имя должно соответствовать
   `fsp_(synthetic|test)_[0-9a-f]{32}`. Генератор отказывается работать на любой другой БД.
2. **Миграции уже применены** до `0010` (генератор **не** запускает миграции, только проверяет
   `alembic_version == "0010"`).
3. **Каталог `DEMO`** (активный каталог `v3-demo`), минимум 2 специализации, 2 грейда и 3 технических навыка.
4. **Пустые доменные таблицы** — генератор отказывается работать при наличии существующих данных.

## Команда запуска

```sh
SYNTHETIC_DATABASE_URL="postgresql+psycopg://USER:PASS@localhost/fsp_synthetic_<32-hex>" \
SYNTHETIC_PASSWORD="<пароль ≥ 12 символов>" \
python -m app.commands.generate_synthetic \
  --confirm-isolated ISOLATED_SYNTHETIC_DATABASE_ONLY \
  --manifest /path/to/fixture.json \
  --batch mvp100
```

Параметры:
- `SYNTHETIC_DATABASE_URL` — строка подключения к изолированной БД (обязательно).
- `SYNTHETIC_PASSWORD` — общий пароль всех синтетических аккаунтов, ≥ 12 символов (обязательно).
- `--confirm-isolated` — ровно `ISOLATED_SYNTHETIC_DATABASE_ONLY` (явное подтверждение).
- `--manifest` — путь к JSON-манифесту (создаётся эксклюзивно, `x`-режим).
- `--batch` — префикс email-аккаунтов (по умолчанию `mvp100`).

## Идемпотентность и безопасность

- Повторный запуск с тем же манифестом возвращает сохранённый результат без дублей
  (сверка версии/БД/каталога/политики и контрольной суммы всей БД).
- Любое изменение данных после генерации (`drift`) прерывает повторный запуск.
- Пароли — Argon2id; секреты и персональные данные не попадают в манифест и логи.

## Тесты

```sh
docker compose -f infra/docker-compose.yml run --rm api pytest tests/integration/test_synthetic_generator.py -v
```
