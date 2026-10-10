# Недельный план разработки для junior-команды

> **Как работать:** задача берётся только после зависимостей. Один человек — один небольшой результат за раз. После каждой задачи: запустить указанную проверку, показать результат другому участнику, сделать маленький commit. Не начинать Redis, ML, вакансии и парсинг PDF до закрытия P0.

## Общие правила

- Рабочая ветка: `feature/<номер>-<краткое-имя>`.
- Сообщение commit: `feat: ...`, `fix: ...`, `test: ...`, `docs: ...`.
- Backend: `cd services/api && uv run pytest`; frontend: `cd apps/web && npm run lint && npm run build`.
- Никаких секретов в Git: только `.env.example`.
- Для любой формы: состояние загрузки, понятная ошибка, disabled submit при невалидных обязательных полях.
- Прежде чем назвать задачу готовой: выполните все пункты её DoD, а не только «страница открывается».

## Порядок и роли

| Поток | Ответственный тип задачи | Результат к концу дня |
|---|---|---|
| A — основа | backend/DevOps | Compose, БД, seed, Swagger |
| B — кандидат | frontend + backend | профиль → тест → category |
| C — работодатель | frontend + backend | need → shortlist → reasons |
| D — приватность | backend + тестировщик | invitation → accept → contacts |
| E — доказательства | вся команда | E2E, validation, docs, pitch |

---

## День 1. Запускаемый каркас

### 1.1 Создать структуру и Compose
**Зависит от:** ничего.  
**Файлы:** создать `apps/web/`, `services/api/`, `infra/docker-compose.yml`, `.env.example`, `README.md`.

**Шаги:**
1. Инициализировать Next.js TypeScript в `apps/web`.
2. Инициализировать FastAPI с `GET /health/live` → `{"status":"ok"}`.
3. В Compose описать `web`, `api`, `postgres`, `mailpit`; задать имена контейнеров, ports, volumes, healthchecks.
4. Добавить `.env.example` с `POSTGRES_*`, `JWT_SECRET=change-me`, без реальных паролей.
5. В README написать ровно одну команду запуска и адреса Web/API/Swagger/Mailpit.

**DoD:** `docker compose -f infra/docker-compose.yml up --build` поднимает все 4 сервиса; `/health/live` возвращает 200; `/docs` открывается.

**Проверка:** остановить Compose, удалить volumes, повторить запуск с нуля.  
**Commit:** `chore: add compose development environment`.

### 1.2 Подключить PostgreSQL, Alembic и seed command
**Зависит от:** 1.1.  
**Файлы:** `services/api/app/shared/db/{session,base}.py`, `alembic/`, `app/commands/seed_demo.py`, `scripts/demo-reset.sh`.

**Шаги:**
1. Добавить database URL из env и `GET /health/ready`, который проверяет `SELECT 1`.
2. Инициализировать Alembic; создать пустую первую migration.
3. Добавить команду `python -m app.commands.seed_demo` с временным print `seed completed`.
4. `demo-reset.sh`: migrations → seed. Не писать SQL в shell script.

**DoD:** `alembic upgrade head` работает на пустой БД и второй запуск не падает; `/health/ready` не 200 без БД.

**Проверка:** `pytest tests/integration/test_migrations.py -v`.  
**Commit:** `feat: add database migrations and demo reset`.

### 1.3 Создать базовые модели и демонстрационные данные
**Зависит от:** 1.2.  
**Файлы:** `modules/*/models.py`, migration `0002_domain.py`, `seed/catalog.json`, `seed/candidates.json`, `seed/fsp_evidence.json`.

**Шаги:** создать только таблицы `users`, `consents`, `candidate_profiles`, `companies`, `hiring_needs`, `test_attempts`, `competency_scores`, `fsp_links`, `fsp_achievements`, `recommendation_snapshots/items`, `invitations`, `contact_disclosures`, `audit_events`.

**Данные seed:** 8–12 кандидатов, Backend Python и Frontend React, Junior/Middle; минимум один `no_history`, один с достижением ФСП, 2 работодателя.

**DoD:** seed идемпотентен; не создаёт второго пользователя с тем же email; есть demo candidate и employer.

**Проверка:** test после seed считает ожидаемые записи, включая `no_history`.  
**Commit:** `feat: add core domain models and demo seed`.

---

## День 2. Вход, роли и профиль кандидата

### 2.1 Регистрация, вход и RBAC
**Зависит от:** 1.3.  
**Файлы:** `modules/identity/{router,service,schemas}.py`, `shared/auth/{passwords,jwt,dependencies}.py`, `tests/test_auth.py`.

**Шаги:**
1. Хэшировать пароль Argon2id; никогда не сохранять plaintext.
2. `POST /auth/register` принимает role только `candidate` или `employer`.
3. `POST /auth/login` возвращает access JWT; dependency `current_user` валидирует его.
4. `require_role("candidate")` / `require_role("employer")` возвращает 403 для неверной роли.
5. Добавить verification token и Mailpit письмо; в крайнем случае seed accounts помечены verified, но route остаётся рабочим.

**DoD:** повторный email → 409; bad password → 401; без token → 401; wrong role → 403.

**Проверка:** table-driven pytest для всех четырёх ошибок.  
**Commit:** `feat: add authentication and role access control`.

### 2.2 Ручной профиль, consent и privacy
**Зависит от:** 2.1.  
**Файлы:** `modules/candidates/*`, `apps/web/app/(candidate)/candidate/profile/page.tsx`, `components/ProfileForm.tsx`.

**Шаги:**
1. Форма: ФИО, email, phone, stack, role, experienceMonths, softSkills, specialization, selfDeclaredGrade.
2. Два отдельных checkbox: обработка и публикация для работодателей.
3. `GET/PATCH /me/candidate-profile` доступен только владельцу.
4. Создать два DTO: `SelfCandidateDTO` (может содержать контакты) и `HiringCandidateDTO` (не содержит).
5. В Next.js добавить candidate layout, форму, success/error state.

**DoD:** отсутствие publication consent исключает из поиска; API работодателя никогда не отдаёт phone/email.

**Проверка:** JSON-string scan response на `email`/`phone`, ownership test, ручная проверка формы.  
**Commit:** `feat: add candidate profile and privacy settings`.

### 2.3 Компания и ролевые маршруты Next.js
**Зависит от:** 2.1.  
**Файлы:** `modules/employers/*`, `app/(employer)/employer/company/page.tsx`, `middleware.ts`.

**DoD:** employer создаёт/редактирует только свою компанию; candidate не открывает employer pages; employer не открывает candidate pages.

---

## День 3. Тестирование и категория

### 3.1 Зафиксировать каталог и blueprints
**Зависит от:** 1.3.  
**Файлы:** `seed/catalog.json`, `seed/assessment_blueprints.json`, `modules/assessments/domain.py`.

**Шаги:**
1. Выбрать 2 специализации: например Backend Python и Frontend React; грейды Junior/Middle.
2. Для каждой ячейки задать 3–5 навыков, pass/high thresholds, две обязательные эквивалентные формы A/B и резервную C для retest/ротации.
3. Каждая форма отличается параметрами/кейсом/порядком, но имеет одинаковые skill slots и rubric; точные значения брать только из `business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md`.
4. Написать 1 страницу `docs/assessment-method.md`: почему варианты сопоставимы.

**DoD:** schema отказывает blueprint без двух variants, rubric или thresholds.

**Проверка:** `pytest tests/assessments/test_blueprints.py -v`.  
**Commit:** `feat: add versioned assessment blueprints`.

### 3.2 Запуск, отправка и scoring
**Зависит от:** 3.1, 2.2.  
**Файлы:** `variant_generator.py`, `scoring.py`, `grade_policy.py`, router/tests.

**Шаги:**
1. `POST /assessments/start` выбирает variant и сохраняет immutable attempt.
2. `GET /assessments/{id}` не отправляет answer key.
3. `POST /submit` принимает ответы один раз, считает subscore/total score, сохраняет category.
4. При fail сохранить `lower_retest_offered`; при high — `higher_retest_offered`; не менять current verified grade вниз.
5. `retestAvailableAt` = now + 90 days после решения о смене грейда.

**DoD:** submit повторно не меняет attempt; другой пользователь получает 403/404; cooldown блокирует новый grade-change тест.

**Проверка:** pass/fail/high/cooldown/answer-key-leak tests.  
**Commit:** `feat: score assessments and assign candidate category`.

### 3.3 UI теста, результата и истории
**Зависит от:** 3.2.  
**Файлы:** `features/assessment/*`, `candidate/assessment/page.tsx`, `candidate/history/page.tsx`.

**DoD:** candidate проходит test, видит category/strong skills/retest date; history содержит дату, specialization, result, category.  
**Проверка:** Playwright candidate completes one seeded variant.

---

## День 4. Подбор работодателя

### 4.1 Потребность работодателя
**Зависит от:** 2.3.  
**Файлы:** `modules/employers/hiring_needs.*`, `employer/needs/page.tsx`.

**Шаги:** реализовать title, teamDescription, specialization, minGrade, targetGrade, requiredSkills, optionalSkills. Использовать select из catalog, не произвольные строки.

**DoD:** employer не читает/меняет чужую need; invalid grade/skill → 422.

### 4.2 Ranking и snapshot
**Зависит от:** 3.2, 4.1.  
**Файлы:** `modules/matching/{eligibility,scoring,reasons,service}.py`, tests.

**Шаги:**
1. Отсеять кандидата без verified email, publication consent, category или specialization/minGrade match.
2. Посчитать skill fit, assessment strength, FSP bonus.
3. Сохранить `RecommendationSnapshot` с weights/version/items.
4. Сформировать 2–3 причины из чисел, не сгенерированный текст.

**DoD:** fixed seed даёт ожидаемый top-3; `no_history` получает FSP=0; CV не участвует как единственный фактор.

**Проверка:** hand-calculated fixture and stable tie-breaker.  
**Commit:** `feat: add explainable candidate ranking`.

### 4.3 Банк кандидатов и фильтры
**Зависит от:** 4.2.  
**Файлы:** `modules/matching/router.py`, `employer/talent/page.tsx`, `FilterPanel.tsx`.

**Шаги:** добавить filters: specialization, grade, category, stack, hasFspAchievements. Хранить base snapshot ID; «Сбросить» убирает filters, не создаёт новый ranking.

**DoD:** filters меняют только отображаемые item; reset возвращает исходный order; no PII в карточке.

**Проверка:** API filter/reset tests; component test.  
**Commit:** `feat: add talent bank filters and reset`.

---

## День 5. Приглашение и защита контактов

### 5.1 Invitation API и автомат состояний
**Зависит от:** 4.2.  
**Файлы:** `modules/invitations/{schemas,state_machine,service,router}.py`, tests.

**Шаги:**
1. Create требует company, candidate, offerDescription, contactMethod, `salaryMin`, `salaryMax`, `currency=RUB`.
2. Проверить `min > 0`, `max >= min`, employer owns company, candidate is searchable.
3. Создать `sent`; view переводит в `viewed`; только target candidate может accept/decline.
4. Каждое действие пишет `AuditEvent`.

**DoD:** missing/reversed salary → 422; duplicate active invite → 409; terminal status не меняется.

### 5.2 ContactDisclosure и два интерфейса
**Зависит от:** 5.1.  
**Шаги:** accept в одной DB transaction создаёт `ContactDisclosure`. `HiringCandidateDTO` добавляет contacts только если requesting employer имеет disclosure для invitation. Сделать employer offer form и candidate inbox.

**DoD:** до accept/после decline contacts отсутствуют; accepted видит только origin employer; второй employer всегда masked.

**Проверка:** два browser context в Playwright + API response scan.  
**Commit:** `feat: add private invitation acceptance workflow`.

---

## День 6. PDF, validation и документация

### 6.1 Генерация PDF-профиля
**Зависит от:** 2.2.  
**Файлы:** `modules/documents/profile_pdf.py`, `GET /me/profile-pdf`, `ProfilePdfButton.tsx`.

**Шаги:** использовать простой HTML template → PDF library, либо зафиксированный browser print workflow. Включать только permitted profile fields, category и aggregate achievements; не включать private phone/email, если candidate отключил их.

**DoD:** owner получает PDF; другой user 403; PDF содержит имя, stack, category и без запрещённых полей.

### 6.2 Автоматизированные проверки и validation report
**Зависит от:** 3–5.  
**Файлы:** `tests/`, `apps/web/e2e/primary-flow.spec.ts`, `docs/validation.md`, `commands/evaluate.py`.

**Шаги:** добавить `Precision@3` по relevance labels, прогнать A/B/C на novice/junior/strong-junior/middle/strong-middle fixtures, проверить стабильность verified/unverified category и отсутствие strong-junior false positive на Middle. Написать limitations: synthetic data не доказывает production accuracy.

**DoD:** pytest, frontend lint/build and E2E main flow pass; report reproducible by one command.

### 6.3 Финальная документация и OpenAPI
**Файлы:** `README.md`, `docs/runbook.md`, `docs/demo-script.md`, `docs/fsp-integration.md`, exported `docs/openapi.json`, `LICENSE`.

**DoD:** незнакомый человек запускает demo по README; Swagger содержит implemented endpoints; documentation covers all rows in `arch/requirements-coverage.md`.

---

## День 7. Интеграция и питч

### 7.1 Чистый прогон

1. Clone/clean workspace.
2. `docker compose up --build`.
3. Migrate + seed.
4. Candidate: profile → test → category.
5. Employer: need → filters → invitation with salary.
6. Candidate accepts; employer sees contact; second employer does not.
7. Download PDF; open Swagger.

**DoD:** команда повторяет прогон дважды без ручного SQL и без автора конкретной функции.

### 7.2 Питч и резерв

Подготовить 5–7 минут: проблема → assessment variants → ranking reasons → privacy/salary live demo → validation table → future integrations. Записать fallback video только после живого прогона. Не заявлять отложенные функции реализованными.

## Финальный стоп-лист

Не брать вакансии/отклики, Redis, отдельные DS/FSP-сервисы, парсинг CV, ATS, Keycloak, антифрод или mobile, пока не пройдены: Compose, category, ranking, invitation/privacy, PDF, history/cooldown, filters, E2E и документация.
