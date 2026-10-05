# Архитектура недельного MVP ФСП

## 1. Цель и границы

Решение — самостоятельная веб-платформа для обратного ИТ-подбора: **работодатель ищет подтверждённого кандидата и отправляет ему персональное предложение с зарплатой**, а не кандидат только откликается на вакансию.

За неделю строим **модульный монолит**: Next.js + FastAPI + PostgreSQL + Docker Compose. Разделяем домены в коде, но не поднимаем отдельные DS/FSP/Redis-сервисы. Это уменьшает риск интеграционных ошибок и не противоречит ТЗ.

### Входит в финальный обязательный объём

- два кабинета: кандидат и работодатель;
- email-регистрация, согласия, роли и приватность;
- ручное резюме/профиль; генерация стандартизированного PDF-профиля;
- 2 специализации × 2 грейда; вариативные тесты, история, higher/lower retest и cooldown;
- ФСП fixture: достижения либо `no_history`;
- потребность работодателя, банк кандидатов и фильтры;
- объяснимый ranking, immutable snapshot выдачи;
- invitation со salary в RUB, статусами и раскрытием контакта только после accept;
- Swagger/OpenAPI, seed, тесты, документация, запуск через Compose.

### Явно не входит в недельную реализацию

Парсинг PDF-резюме, вакансии/отклики, регулярные задания, реальный API ФСП/Keycloak, ATS, Redis/EDA, мобильная версия, антифрод. В документации они описываются только как дальнейшее развитие.

## 2. Контейнеры и ответственность

| Контейнер | Технология | Ответственность | Не делает |
|---|---|---|---|
| `web` | Next.js, TypeScript | страницы, формы, маршрут по роли, запросы к API, отображение статусов | не принимает решения о доступе к ПДн |
| `api` | FastAPI, SQLAlchemy, Alembic | бизнес-правила, RBAC, тесты, ranking, invitations, PDF, Swagger | не отдаёт PII в общих DTO |
| `postgres` | PostgreSQL | все бизнес-данные, audit, seed | не хранит пароли в открытом виде |
| `mailpit` | Mailpit | локальная проверка email/уведомлений | не является production-почтой |

```text
Кандидат ─┐                 ┌─ POST /assessments/{id}/submit
          ├─ Next.js ─REST─►├─ FastAPI ─SQLAlchemy─► PostgreSQL
Работодатель┘               ├─ PDF profile
                            ├─ FSP fixture provider
                            └─ Mailpit background task
```

## 3. Структура репозитория

```text
apps/
  web/
    app/(public)/login/page.tsx
    app/(candidate)/candidate/{profile,assessment,history,invitations}/page.tsx
    app/(employer)/employer/{company,needs,talent,invitations}/page.tsx
    components/  lib/api.ts  types/
services/
  api/
    app/
      main.py  api/router.py
      shared/{config,db,auth,errors,audit}.py
      modules/
        identity/ candidates/ employers/ assessments/
        fsp/ matching/ invitations/ documents/
    alembic/  tests/
infra/docker-compose.yml
seed/{catalog,blueprints,candidates,needs,relevance_labels,fsp_evidence}.json
docs/{validation,demo-script,runbook}.md
```

**Правило зависимостей:** `router → service → repository`. Роутер валидирует HTTP-ввод, service реализует правило, repository делает SQL. Нельзя писать SQL в роутере или решать доступы только в Next.js.

## 4. Домены и модели

| Домен | Главные сущности | Инварианты |
|---|---|---|
| Identity | `User`, `Consent`, `RefreshToken` | email уникален; пароль — Argon2id hash; verified email обязателен для публикации |
| Candidate | `CandidateProfile`, `Skill`, `DocumentProfile` | контакты не входят в `HiringCandidateDTO`; privacy/publication consent обязателен |
| Assessment | `AssessmentBlueprint`, `TestAttempt`, `CompetencyScore` | submitted attempt неизменяем; variant хранит blueprint version; grade не понижается автоматически |
| FSP | `FspLink`, `FspAchievement` | `no_history` — допустимое состояние, не ошибка |
| Employer | `Company`, `EmployerProfile`, `HiringNeed` | employer меняет только свою company/need |
| Matching | `RecommendationSnapshot`, `RecommendationItem` | snapshot неизменяем; ranking не основан только на CV |
| Invitation | `Invitation`, `ContactDisclosure` | только accept создаёт disclosure; salary/company/offer/contact method обязательны |
| Audit | `AuditEvent` | фиксируются invitation, decision, contact disclosure, consent и значимые изменения |

### Обязательные поля

- `CandidateProfile`: ФИО, email/телефон, specialization, stack, roles, experienceMonths, softSkills, selfDeclaredGrade, privacy/publication flag.
- `HiringNeed`: companyId, title, teamDescription, specialization, minGrade, targetGrade, requiredSkills, optionalSkills.
- `Invitation`: candidateId, companyId, hiringNeedId nullable, offerDescription, contactMethod, salaryMin, salaryMax, currency=`RUB`, status.

## 5. API-контракт

| Назначение | Методы |
|---|---|
| Доступ | `POST /auth/register`, `/auth/login`, `/auth/verify-email`, `/auth/refresh` |
| Кандидат | `GET/PATCH /me/candidate-profile`, `GET /me/assessment-history`, `GET /me/profile-pdf` |
| Тест | `POST /assessments/start`, `GET /assessments/{id}`, `POST /assessments/{id}/submit` |
| ФСП | `POST /me/fsp-link`, `GET /me/fsp-evidence` |
| Работодатель | `GET/PATCH /me/company`, `POST/GET /hiring-needs` |
| Подбор | `POST /hiring-needs/{id}/recommendations`, `GET /hiring-needs/{id}/recommendations`, `POST /talent-search` |
| Приглашения | `POST /invitations`, `GET /invitations`, `POST /invitations/{id}/view`, `/accept`, `/decline` |
| Служебные | `GET /health/live`, `/health/ready`, `/docs` |

Все endpoints имеют Pydantic request/response schemas, status codes `401/403/404/409/422` и examples в Swagger.

## 6. Алгоритмы

### 6.1 Тестирование и категория

Blueprint содержит: specialization, target grade, skill slots, две parameterized variants, rubric, threshold и high-confidence threshold. При старте создаётся `TestAttempt` с выбранным вариантом. После submit:

```text
score < lower threshold  → lower_retest_offered, verified grade не меняется вниз
pass threshold            → category = specialization × declared/verified grade
high-confidence threshold → higher_retest_offered
```

`retestAvailableAt = lastGradeChangeAt + cooldownDays`; для демо `cooldownDays=90` конфигурируется через env. История показывает дату, результат, категорию и предложенное действие.

### 6.2 Подбор

1. **Eligibility:** verified email, publication consent, category exists, specialization matches, verified grade ≥ minGrade.
2. **Фильтры:** specialization, grade, category, stack, FSP achievements.
3. **Оценка:** `0.50 × соответствие навыкам + 0.35 × сила теста + 0.15 × ФСП-бонус`.
4. **Причины:** 2–3 факта из сохранённых компонент: категория, `N/M` навыков, балл, ФСП-достижение.
5. **Snapshot:** сохраняет algorithmVersion, входные фильтры, порядок и причины. «Сбросить» возвращает base snapshot, не пересчитывая его.

## 7. Приватность и security checklist

- RBAC на FastAPI: `candidate`, `employer`, `admin`; Next.js — только UX-защита.
- `HiringCandidateDTO` до accept не включает email, телефон, приватные документы или raw answers.
- После accept `ContactDisclosure` проверяется по `invitationId + companyId`; другой employer остаётся без контактов.
- Passwords: Argon2id; JWT secret — только env; refresh token хэшируется.
- PDF содержит только поля, разрешённые candidate; выдаётся владельцу по auth check.
- Логи не содержат password, JWT, phone, email, answers.
- Audit: consent, profile publication, invitation create/view/decision, disclosure.

## 8. Запуск и демонстрационные данные

`docker compose -f infra/docker-compose.yml up --build` поднимает четыре контейнера. После `alembic upgrade head` запускается seed: 8–12 кандидатов, 2 specializations, Junior/Middle, 2–3 needs, один candidate с evidence и один `no_history`.

`demo-reset` должен удалить demo rows, применить миграции, заполнить seed и вывести адреса/учётные записи. В документации нужны системные требования, версии библиотек, лицензия, README, URL Swagger и точный demo-script.

## 9. Проверка перед сдачей

- pytest: RBAC, rubric/cooldown, no_history, formula/reasons, filters/reset, salary, invitation transitions, PII before/after accept, PDF owner access.
- Playwright: candidate category → employer shortlist → invitation → accept → contacts; second employer remains masked.
- validation report: `Precision@3`, два варианта одного blueprint, weak/medium/strong fixtures, ограничения synthetic dataset.
- final checklist: `arch/requirements-coverage.md`.
