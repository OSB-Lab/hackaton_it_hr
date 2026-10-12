# Функциональный аудит MVP «ФСП | ИТ-подбор»

Дата: 2026-10-10. Проверенный checkout: `feat/spr-18`, HEAD `e56b833`
(`Merge remote-tracking branch 'origin/main' into feat/spr-18`). Предыдущие commits:
`db368de` — workspace components; `5ff40e8` — merge frontend-auth.
Это снимок состояния, а не сертификат production readiness.

> **Позже состояние изменилось.** Разделение demo/real/test удалено (нет флагов
> `DEMO`/`APPROVED`/`content_status`), миграция `0012` убрала колонки статуса,
> подтверждающий v3-трек расширен до `backend/frontend/fullstack × junior/middle/senior`
> (9 ячеек, 540 вопросов), квалификация определяется баллом (13/18 + per-skill gate).
> Актуальное состояние — в [`README.md`](../README.md) и [`docs/JURY.md`](JURY.md).

## 1. Резюме и границы доказательств

Backend основных сценариев реализован и проверен существующими API-тестами на
временных БД. Frontend уже содержит формы и вызовы реального API, проходит typecheck
и production build; страницы доступны по HTTP. **Ни одна интерактивная браузерная
цепочка в этом аудите не подтверждена**: подключённых браузеров нет
(`cua.listBrowsers() → []`), Playwright dependency/config/spec отсутствуют.
HTTP 200 страницы означает доставку HTML, не исполнение формы, React effects или navigation.

Полный положительный сценарий на текущих рабочих данных заблокирован:

- все активные вопросы DEMO; они намеренно не присваивают verified qualification;
- в dev-БД 0 attempts, 0 достоверных qualification, 0 snapshots и 0 invitations;
- все 4 существующие needs не заполнены для ranking: отсутствует minGrade и/или specialization;
- подтверждённая интеграция ФСП отсутствует, production FSP bonus = 0.

**Оригинал ТЗ организаторов в проверенном репозитории не найден.** Поиск имён
Markdown/PDF/DOCX/TXT выполнен без захода в `backups/`. Есть внутренний нормативный
`services/api/docs/v3/business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md` (LOCKED v3),
TEAM_QA, USE_CASES_AND_MECHANISMS, README модулей и tests. Ссылки внутреннего документа
на ТЗ не заменяют оригинал. Требования ниже не приписываются организаторам.

Код, бизнес-логика и рабочие данные не изменялись. Создан только этот отчёт.
Миграции dev-БД не применялись; `current/check` являются проверками, не upgrade.
Существующие integration fixtures создавали/мигрировали/удаляли только собственные
`fsp_test_<uuid>` базы. `seed/reset`, очистка volumes, commit/push не выполнялись;
`backups/` не читалась и не менялась. Frontend build выполнялся в `/tmp` web-контейнера.

## 2. Матрица функций

Итог по 44 строкам аудита: **24 работают на указанном слое, 5 частично,
4 отсутствуют, 10 не проверены, 1 проверка не работает**. Доля непроверенных
строк — **10/44 = 22,7%**. Это не процент обязательного MVP: оригинал ТЗ
не найден, а API и браузерные сценарии здесь оцениваются отдельно.

Статусы: ✅ РАБОТАЕТ — фактически проверен указанный в строке слой;
🟡 ЧАСТИЧНО — известное функциональное ограничение;
❌ НЕ РАБОТАЕТ — воспроизведённый провал проверки;
⚪ ОТСУТСТВУЕТ — нет реализации;
❓ НЕ ПРОВЕРЕНО — недостаточно фактических проверок.

В колонке ТЗ `Н/У` = обязательность по ТЗ организаторов **не установлена**.
`К:да` означает наличие во внутреннем контракте/документации, а не внешнее требование.
`UI есть` означает код, **не browser PASS**. Строки явно разделяют API и UI; их нельзя
использовать как процент сквозной готовности.

Сокращения путей: **B**=`services/api/app/modules/`, **W**=`apps/web/app/`,
**T**=`services/api/tests/integration/`. Доказательства H/B/D/T/R описаны ниже.

| № | Функция / слой | ТЗ / контракт | Backend | Frontend | Статус | Доказательство, реализация, что нужно |
|---|---|---|---|---|---|---|
| 01 | Главная: доставка страницы | Н/У / К:да | — | Есть | ✅ РАБОТАЕТ | H: `/` 200; W`page.tsx`. Интерактивность отдельно не проверена |
| 02 | Регистрация candidate/employer, API | Н/У / К:да | Есть | Есть, UI не проверен | ✅ РАБОТАЕТ | T`test_auth_registration.py`; B`auth/router.py`, W`register/page.tsx` |
| 03 | Verify-email: token/expiry/idempotency, API | Н/У / К:да | Есть | Есть, UI не проверен | ✅ РАБОТАЕТ | T`test_auth_registration.py`; B`auth/service.py`, W`verify-email/page.tsx` |
| 04 | Login обеих ролей, API | Н/У / К:да | Есть | Есть, UI не проверен | ✅ РАБОТАЕТ | T`test_auth_login.py`; B`auth/router.py`, W`login/page.tsx` |
| 05 | Выход из кабинета | Н/У / К:да | Logout/revoke нет, access JWT истекает | Очистка localStorage + redirect | ❓ НЕ ПРОВЕРЕНО | W`_components/CabinetStub.tsx`; нужен browser smoke; не обещать server-side revoke |
| 06 | Сессия после reload/повторного входа | Н/У / К:да | `/auth/me` есть | localStorage, guard есть | ❓ НЕ ПРОВЕРЕНО | W`_lib/api.ts`, `CabinetStub.tsx`; нужен reload/expiry/browser test |
| 07 | RBAC, 401/403, чужие объекты | Н/У / К:да | Есть | Guard есть, UI не проверен | ✅ РАБОТАЕТ | H: anonymous 401; T auth/company/needs/profile/invitations/ranking; B`auth/dependencies.py` |
| 08 | Создать/читать/редактировать профиль, API/БД | Н/У / К:да | Есть | Есть, UI не проверен | ✅ РАБОТАЕТ | T`test_candidate_profile.py`; B`candidate/service.py`; W`CandidateWorkspace.tsx` |
| 09 | Имя, specialization, skills, опыт, role, контакты | Н/У / К:да | Поля и PATCH | Форма есть | ✅ РАБОТАЕТ | T candidate_profile; PostgreSQL asserts, не только response. Email read-only; role профессиональная |
| 10 | processing/publication/showContacts | Н/У / К:да | Раздельные Consent + privacy JSON | Переключатели есть | ✅ РАБОТАЕТ | T candidate_profile/invitation_privacy; B`candidate/service.py`; актуальные gates disclosure |
| 11 | Собственный PDF, API | Н/У / К:да | Есть, no-store | Blob download есть | ✅ РАБОТАЕТ | T`test_profile_pdf.py`: извлечение текста, Unicode, PII scans; W`_lib/platform.ts` |
| 12 | Редактирование профиля/PDF в браузере | Н/У / К:да | Готов | Есть | ❓ НЕ ПРОВЕРЕНО | H `/candidate/profile` 200 + B build, но заполнение формы/скачивание в браузере не выполнялись |
| 13 | Versioned банк A/B/C и checksum | Н/У / К:да | Есть | Выбор из catalog | ✅ РАБОТАЕТ | R: validate_all; 4 blueprint × 3 × 20 = 240 активных вопросов; B`catalog/repository.py` |
| 14 | Start, ownership, выдача вопросов без keys | Н/У / К:да | Есть | Есть | ✅ РАБОТАЕТ | T`test_assessment_v3_lifecycle.py`, unit `test_assessment_v3.py`; B`assessments/service.py` |
| 15 | Выбор/отправка ответов через браузер | Н/У / К:да | Есть | Radio forms, confirm submit | ❓ НЕ ПРОВЕРЕНО | W`CandidateWorkspace.tsx`; H route 200 не проверяет клики/отправку |
| 16 | Scorer, сохранение answers/result, atomic submit | Н/У / К:да | Есть | Result view есть | ✅ РАБОТАЕТ | T assessment_v3_lifecycle + unit assessment_v3; 12/13/16, core gates, idempotency/rollback |
| 17 | Подтверждённые grade/specialization в обычном сценарии | Н/У / К:да | APPROVED gate реализован | Статус честно показан | 🟡 ЧАСТИЧНО | APPROVED test-fixture проверена T; реальные активные artifacts DEMO, D: valid qualification=0 |
| 18 | Technical skillTags evidence, teamwork отдельно | Н/У / К:да | Есть | Итог/diagnostic видны; подробный skills result UI ограничен | ✅ РАБОТАЕТ | Unit `test_assessment_v3.py`, B`assessments/scoring_v3.py`; не claim об UI |
| 19 | История попыток | Н/У / К:да | GET по ID, list нет | Возврат по ID/localStorage | 🟡 ЧАСТИЧНО | OpenAPI, W`CandidateWorkspace.tsx`; нужен список истории, если обязателен |
| 20 | Cooldown/retest/защита от подмены | Н/У / К:да | Есть | Обработка 409, результат | ✅ РАБОТАЕТ | T assessment_v3_lifecycle; B`assessments/qualification.py`; не бессрочный запрет |
| 21 | Компания own GET/PUT, API/БД | Н/У / К:да | Есть | Есть | ✅ РАБОТАЕТ | T`test_employer_company.py`; B`employer/service.py`; W`EmployerWorkspace.tsx` |
| 22 | Need create/list/read/PATCH, catalog validation | Н/У / К:да | Есть | Есть | ✅ РАБОТАЕТ | T`test_employer_needs.py`; wrong IDs/grades/skills 422, ownership; W EmployerWorkspace |
| 23 | Закрытие/удаление need | Н/У / К:не найдено | Нет DELETE/status | Нет | ⚪ ОТСУТСТВУЕТ | OpenAPI/model HiringNeed; сначала уточнить обязательность, не добавлять произвольно |
| 24 | Форма компании/потребности в браузере | Н/У / К:да | Есть | Есть | ❓ НЕ ПРОВЕРЕНО | H routes 200 + B; submit и сохранение через browser не проверены |
| 25 | Eligibility до ranking | Н/У / К:да | Есть | Пустые состояния есть | ✅ РАБОТАЕТ | T`test_ranking_create.py`; B`recommendations/service.py`; email/privacy/proof/spec/minGrade |
| 26 | Required/optional coverage | Н/У / К:да | Есть, временная normalization policy | Компонент score виден в коде | ✅ РАБОТАЕТ | Unit `test_ranking.py`, T ranking_create; не требует всех skills как hard filter |
| 27 | TestStrength из квалифицирующей attempt | Н/У / К:да | Есть | assessmentStrength | ✅ РАБОТАЕТ | T ranking_create: later attempt/изменённый cache не заменяют proof result |
| 28 | Подтверждённый FSPBonus | Н/У / К:да | Формула есть; production всегда 0 | Показывает компонент | 🟡 ЧАСТИЧНО | B`recommendations/ranking.py`, service не передаёт confirmed_fsp=True; нужен trusted provider |
| 29 | Snapshot create/read, empty, stable sort, reasons | Н/У / К:да | Есть | Есть | ✅ РАБОТАЕТ | T ranking_create/recommendations, unit ranking; исторические rank/score не пересчитываются |
| 30 | Talent Bank filters + reset | Н/У / К:да | spec/grade/stack/FSP; category 422 | Формы есть | 🟡 ЧАСТИЧНО | T`test_talent_bank.py`; B`recommendations/talent_service.py`; category catalog отсутствует |
| 31 | Явное «не подходит» и причины исключения | Н/У / К:не установлено | Нет отдельного результата исключения | Нет | ⚪ ОТСУТСТВУЕТ | Eligibility отбрасывает; reasons относятся только к допущенным items |
| 32 | Ranking/cards/filter/offer в браузере | Н/У / К:да | Есть | Есть | ❓ НЕ ПРОВЕРЕНО | W EmployerWorkspace; положительной рабочей выборки нет, browser недоступен |
| 33 | Достижения ФСП в БД и верификация | Н/У / К:да | Таблицы/FK есть; статуса подтверждения нет | Информационный экран | 🟡 ЧАСТИЧНО | D: 4 achievements; `app/models/fsp.py`; seed/linked не proof |
| 34 | FSP link/import/confirm API | Н/У / К:обсуждалось | Нет маршрутов | Нет формы | ⚪ ОТСУТСТВУЕТ | OpenAPI; W`FspInfo` прямо сообщает недоступность |
| 35 | Invitation create/list/view/accept/decline | Н/У / К:да | Есть | Есть | ✅ РАБОТАЕТ | T invitations/contact_disclosure; salary/RBAC/terminal/duplicate/concurrency; B`invitations/service.py` |
| 36 | Disclosure origin employer + отзыв согласия | Н/У / К:да | Есть | Только detail.contacts | ✅ РАБОТАЕТ | T contact_disclosure/invitation_privacy; принятие+grant+актуальные consent/privacy |
| 37 | Inbox/accept/contacts в браузере | Н/У / К:да | Есть | Есть | ❓ НЕ ПРОВЕРЕНО | W`InvitationsWorkspace.tsx`; backend тест не проверяет UI |
| 38 | Authenticated `/catalog` для UI | Н/У / К:интеграция | Новый endpoint есть | Загрузка есть | ❓ НЕ ПРОВЕРЕНО | H anonymous 401, repository R PASS; успешный authenticated HTTP этого нового endpoint не проверен |
| 39 | Единый frontend E2E/Playwright | Н/У / К:validation | API tests есть | Browser suite нет | ⚪ ОТСУТСТВУЕТ | Нет config/spec/dependency в apps/web |
| 40 | Compose/proxy/readiness/Mailpit | Н/У / К:да | Есть | `/api` работает | ✅ РАБОТАЕТ | H/D: 4 healthy, health/Mailpit 200, protected 401 |
| 41 | Frontend typecheck и build | Н/У / К:да | — | Есть | ✅ РАБОТАЕТ | B exit 0, все routes в build; ESLint отдельно не настроен |
| 42 | Воспроизводимость смешанного pytest запуска | Н/У / К:validation | Есть тесты, есть setup-проблема | — | ❌ НЕ РАБОТАЕТ | T1: 211 passed, 155 errors `migrated_engine not found`; T2 отдельно 156 passed |
| 43 | Сохранность рабочей БД после restart | Н/У / К:да | pgdata volume есть | — | ❓ НЕ ПРОВЕРЕНО | Compose volume подтверждён; restart намеренно не выполнялся |
| 44 | Независимая оценка accuracy / Precision@3 | Н/У / К:да | Evaluator interface | Нет | ❓ НЕ ПРОВЕРЕНО | `commands/evaluate.py`, docs/validation; независимых labels и опубликованного результата нет |

## 3. Backend: фактический контракт

Live `/api/openapi.json` → 200, **22 paths**. Вызовы frontend используют существующий
`/api` proxy и следующие маршруты (совпадение проверено по коду, не по browser network):

- POST `/auth/register`, `/auth/login`, `/auth/verify-email`; GET `/auth/me`.
  JWT `Authorization: Bearer`, login response `access_token`, `token_type= bearer`;
  roles candidate/employer. current_user читает актуального User из БД.
- GET/PATCH `/me/candidate-profile`, GET `/me/profile-pdf`, GET `/catalog`.
- POST `/assessments/start`, GET `/assessments/{attempt_id}`,
  POST `/assessments/{attempt_id}/submit`.
- GET/PUT `/employer/company`; GET/POST `/employer/needs`, GET/PATCH `/{need_id}`.
- POST `/employer/needs/{need_id}/recommendations`, GET `/{snapshot_id}`,
  GET `/{snapshot_id}/items` с query filters.
- POST/GET `/invitations`; GET `/{invitation_id}`; POST `/{id}/accept|decline`.
- GET `/health/live`, `/health/ready`.

Отдельных endpoints списка assessment history, списка snapshots, закрытия need,
FSP linking/import/verification нет. GET конкретного invitation кандидатом **меняет**
sent→viewed, поэтому такой GET в рабочей БД при аудите не выполнялся.
Endpoint `/catalog` отдаёт allowlist taxonomy + доступные specialization/grade/status/version;
не сериализует blueprint/questions/keys. Отдельного response_model и endpoint-теста у него
пока нет; это пробел проверки, а не доказанная утечка.

## 4. Frontend

Есть реальные компоненты:

- W`_lib/api.ts`: auth, JWT localStorage, ApiError, 401 redirect для auth requests.
- W`_lib/platform.ts`: типы DTO, get/send, PDF blob, хранение только ID попытки/snapshot.
- W`_components/CabinetStub.tsx`: несмотря на имя, уже рабочая навигация, role guard,
  auth/me, загрузка catalog; это не текущая заглушка.
- W`CandidateWorkspace.tsx`: профиль/consents/privacy, start/questions/submit/result/PDF.
- W`EmployerWorkspace.tsx`: company, need create/edit, snapshot/read/filter/reset/offer.
- W`InvitationsWorkspace.tsx`: list/detail/transition, contacts только из detail response.
- `/candidate/[section]`: profile, assessment, invitations, fsp;
  `/employer/[section]`: company, needs, talent, invitations.

401/403/404/409/422/503 обрабатываются ApiError, есть loading/empty/error блоки.
Часть сообщений generic: 409 по умолчанию «Такая запись уже существует», что не точно
для любого conflict. UI результата показывает DEMO отдельно. Salary передаётся строками,
не float; IDs company/candidate проверяются сервером. Ответы — questionId/optionId|null.
Повторный просмотр submitted result использует идемпотентный POST submit с answers=[]
только после GET status=submitted; это соответствует текущей реализации backend.

Найдены заглушки/иллюстрации и ограничения:

- Главная W`page.tsx`: массив `ROWS`, «128 кандидатов · пример подборки», статические
  баллы/соревнования. Это **маркированная иллюстрация**, не живая статистика.
  «Отправить предложение» внутри этой иллюстрации — `<span>`, а не рабочая кнопка.
- «Достижения ФСП» — честный информационный экран, без API-действия.
- UI category filter отсутствует с пояснением; backend отвергает любой category.
- Серверного списка history/snapshots нет: сохранённый ID в localStorage — не история.
- `catalog/README.md` содержит DS TODO. Название CabinetStub и устаревший комментарий
  «будущие кабинеты» не означают, что весь компонент остался пустым.
- Ни responsive layout, ни доступность с клавиатуры, ни фактический logout/reload,
  ни обработка browser network ошибок интерактивно не проверены.

В безопасности frontend сохраняет текущий MVP-подход localStorage JWT: он доступен
JavaScript и не является HttpOnly cookie. Признаков вывода JWT/answer keys в UI по коду
не найдено, но это не полный security audit. Разрешённые contacts уже полученного ответа
не могут быть «отозваны из памяти пользователя»; новые обращения контролирует backend.
UI очищает detail при blur и предлагает повторную проверку доступа.

## 5. PostgreSQL и реальные таблицы

D: live dev-БД, read-only transaction, только COUNT/метаданные/агрегаты, без PII.
`alembic current` → `0010 (head)`; `alembic check` → `No new upgrade operations detected`.
В public нет `NOT VALID` constraints (0). У всех 14 доменных таблиц PK `id`;
FK ниже подтверждены SQLAlchemy inspector. Это не полная проверка всех семантических
инвариантов данных и не disaster-recovery/restart test.

| Таблица | COUNT | Назначение и основные поля | Связи |
|---|---:|---|---|
| users | 15 | email, password_hash, role, is_verified | Родитель профиля/компании/consents |
| consents | 34 | kind, granted, granted_at | user_id → users; unique user/kind |
| candidate_profiles | 10 | full_name, stack, specialization, grade, self_declared_grade, verified_grade/specialization, privacy_settings, phone, experience_months | user_id → users unique; verified_attempt_id → test_attempts |
| companies | 2 | name, description, contacts | user_id → users unique |
| hiring_needs | 4 | title, team_description, specialization, min_grade, grade(target), stack(required), optional_skills | company_id → companies; unique company/title |
| test_attempts | 0 | snapshot, versions/checksums, variant, status, answers, result, score, submitted_at | candidate_id → candidate_profiles; partial unique active candidate |
| competency_scores | 30 | competency, score, source, evidence_count, blueprint_version | candidate_id → profile; attempt_id → test_attempts |
| fsp_links | 10 | fsp_id, status, linked_at | candidate_id → profile unique |
| fsp_achievements | 4 | discipline, competition, result, role, rank | candidate_id → profile |
| recommendation_snapshots | 0 | algorithm_version, weights, ordered_items | need_id → hiring_needs |
| recommendation_items | 0 | score, rank, reason | snapshot_id → snapshots; candidate_id → profile |
| invitations | 0 | title(offerDescription), salary_from/to, contact_method, currency, status | company_id → companies; candidate_id → profile; **need_id нет** |
| contact_disclosures | 0 | invitation_id, revealed_at | invitation_id → invitations unique |
| audit_events | 0 | user_id, action, payload, created_at | user_id → users |

Служебная `alembic_version`: 0010. История файлов:
`17dada67f98e_init` → 0002 domain → 0003 profile → 0004 needs → 0005 attempt lifecycle
→ 0006 result → 0007 snapshot → 0008 invitation lifecycle → 0009 salary checks → 0010 v3.
Рабочую БД мы не прогоняли через upgrade/downgrade. Временные тестовые БД прогоняются
существующими fixtures до head; соответствующие API-тесты проверяют реальные записи.

Дополнительные агрегаты D: `verified_attempt_id IS NOT NULL` = 0;
`qualification(...) is not None` = 0; attempt groups пусты.
Все 4 needs имеют отсутствующий minGrade и/или specialization и не проходят текущую
валидацию ranking. Их нельзя использовать как готовые positive ranking fixtures.
Наличие 30 competency rows без attempts **не является подтверждённой квалификацией**.

## 6. Assessment v3

R: `CatalogRepository().validate_all()` прошёл checksum/reference/schema validation.
Активны backend-junior, backend-middle, frontend-junior, frontend-middle, все `v3-demo`,
все DEMO. У каждого A/B/C по 20 вопросов: **240 активных question records**, 20 на попытку,
18 technical + 2 teamwork diagnostic. Это размер пула, не 240 независимых экспертно
апробированных заданий. Исторический v1-demo остаётся для совместимости, не считается активным.

Технический total = correctTechnical / 18 × 100. Evidence навыка = correctTagged /
totalTagged × 100; multi-tag question влияет на каждый свой skill, но один раз на total.
Teamwork отдельно и не подтверждает technical grade.

- FAIL: correctTechnical <13 либо любой core skill <50%.
- PASS: выполнен pass gate; HIGH: correctTechnical ≥16 и каждый core ≥70%.
- Если ≥16, но core ≥50 и <70, результат PASS, не HIGH.
- Только успешная submitted APPROVED v3 attempt с согласованными catalog/blueprint/status
  устанавливает/повышает verified_grade и verified_specialization; DEMO не делает этого.
- Grade не понижается после fail; retest/cooldown 90 дней по текущему контракту,
  отдельная ротация A/B/C; senior в taxonomy есть, активного senior blueprint нет.
- Есть versioned approval metadata (`provenance=DS`, explicit approval), нет автоматического
  продвижения DEMO. Экспертное одобрение реального контента в этом checkout не обнаружено.

Ключи хранятся внутри backend artifacts/snapshot; public_variant публикует вопросы и
варианты ответа без answerKey/rubric/scoring. Это подтверждают существующие тесты.
Неизменяемость обеспечена сервисом/тестами, не DB trigger.

## 7. Matching / ranking

Фактический `B recommendations/ranking.py`, `ALGORITHM_VERSION=v3-mvp-coverage-1`:

```text
requiredCoverage = mean(certifyingAttempt.result.subscores[skill] / 100)
optionalCoverage = аналогично; absent evidence = 0; empty required = 0
skillFit = 0.80 * requiredCoverage + 0.20 * optionalCoverage
если optional пуст: skillFit = requiredCoverage
testStrength = certifyingAttempt.result.technicalTotal / 100
rankScore = 0.50 * skillFit + 0.35 * testStrength + 0.15 * fspBonus
```

Continuous mean coverage — явно документированная временная MVP-policy, а не
доказанная DS calibration. Диапазон компонентов 0..1, невалидные numeric evidence
отклоняются. `testStrength` в API называется `assessmentStrength` для совместимости.
Evidence берётся из immutable результата attempt, установившей текущую qualification:
mutable CompetencyScore может быть перезаписан пересдачей и здесь не источник истины.

Eligibility **до** расчёта: candidate role, verified email, publication consent,
privacy publish_profile, авторитетная qualification, matching specialization/minGrade.
Самозаявленный grade/stack и seed rows не qualify. Обязательные skills — фактор coverage,
**не отдельное правило «все навыки обязаны быть подтверждены»**. Не добавлять такой gate
без продуктового решения. Отсутствие ФСП не исключает кандидата.

Порядок: score DESC → technical strength DESC → candidate_id ASC. Snapshot сохраняет
weights/components/rank/reasons и ordered_items; GET не пересчитывает рейтинг, но
актуальные privacy restrictions могут запретить раскрытие всего snapshot с 409.
Talent filters — AND, сохраняют исходные rank/score; reset — тот же ID без query.
Stack-фильтр Talent Bank читает catalog-valid `CandidateProfile.stack`, не обязательно
подтверждённый evidence; это важно не называть verified skills в UI.

Ниже **иллюстрация формы ответа**, не ответ рабочей БД и не созданные для аудита данные:

```json
{
  "id": 1,
  "needId": 1,
  "createdAt": "2026-10-10T00:00:00Z",
  "algorithmVersion": "v3-mvp-coverage-1",
  "weights": {"skillFit": 0.5, "assessmentStrength": 0.35, "fspBonus": 0.15},
  "items": [{
    "candidate": {"id": 1}, "rank": 1, "score": 0.85,
    "components": {"skillFit": 1, "assessmentStrength": 1, "fspBonus": 0},
    "reasons": ["Required skill evidence: 100.0%", "Technical test: 100.0%", "Verified FSP bonus: 0.0%"]
  }]
}
```

Тесты: unit `test_ranking.py`; integration `test_ranking_create.py`,
`test_recommendations.py`, `test_talent_bank.py`. Проверены ручные значения, determinism,
gates, DEMO exclusion, saved replay, legacy data, rollback, RBAC, safe DTO.
Независимые relevance labels/Precision@3 отсутствуют; внутренние fixtures не доказывают accuracy.
MVP сканирует и блокирует User/profile кандидатов: приемлемость на большой нагрузке не проверена.

## 8. ФСП

Есть FspLink и FspAchievement, связи и 4 сохранённых достижения. `result` — свободная
строка; нет enum «победитель/призёр/...», verified flag, audited provenance, trusted provider
или API подтверждения. Шкала **1/.75/.50/.15/0 не реализована** и не считается утверждённой.
Чистый calculate поддерживает binary confirmed bonus 1/0, но production create_snapshot
не передаёт confirmed=True: **FSPBonus всегда 0**, максимум текущего production rankScore 0.85.
Talent `hasFspAchievements` означает linked+fsp_id+linked_at+achievement row, не экспертное
подтверждение. Seed/linked история не повышает grade и не даёт bonus.

## 9. Приглашения и contacts

Backend: employer owner company; candidate searchable; salary positive Decimal,
salaryMax≥salaryMin, RUB; DB CHECK + partial unique active `(company_id,candidate_id)`.
Sent→viewed→accepted/declined и прямой sent→terminal; DB хранит rejected, API declined.
Terminal immutable, повторные действия идемпотентны. AuditEvent содержит actor/action/
invitation/status transition. Accept + ContactDisclosure + audit атомарны, уникальность
grant — по invitation_id. Concurrent и rollback случаи покрыты tests.

Контакты: только origin employer, accepted invitation, соответствующий disclosure,
verified email, действующие processing/publication, publish_profile/show_contacts.
Чужой invitation скрыт 404; другой employer не получает контакты по чужому grant.
Lists/ranking/Talent DTO не раскрывают contacts; historical free-text reason скрыт.
PDF никогда не экспортирует email/phone. Принятие при showContacts=false **не гарантирует**
раскрытие — это правило приватности, не техническая ошибка. UI об этом сообщает.
В dev-БД нет invitations/disclosures: положительный browser-flow на этих данных не проверялся.

## 10. Выполненные проверки и воспроизведение

### H — инфраструктура и HTTP (read-only)

`docker compose -f infra/docker-compose.yml ps`: api/web/postgres/mailpit healthy.
GET через `http://localhost:3000`:

```text
/ /login /register /verify-email                         200
/candidate/profile /candidate/assessment /candidate/invitations 200
/employer/company /employer/needs /employer/talent /employer/invitations 200
/api/health/live /api/health/ready                       200
/api/catalog /api/auth/me (без token)                   401
/api/openapi.json                                      200, 22 paths
mailpit:8025/readyz                                     200
```

Requests выполнены `node fetch` внутри web-контейнера. Same-origin `/api` rewrite
на `http://api:8000` проверен фактически; отдельный browser CORS test не выполнялся.
Последние 200 строк логов каждого api/web: Traceback=0, ERROR/Unhandled/Failed compile=0,
HTTP 500=0. Выводились только количества, не сырые строки с потенциальными PII.
Ограниченное окно логов не доказывает отсутствие ошибок вообще.

### B — frontend

В web-контейнере скопированы app и build configs в `mktemp -d /tmp/fsp-audit.XXXXXX`,
подключён существующий node_modules. Выполнены `npm run typecheck` и
`NEXT_TELEMETRY_DISABLED=1 npm run build`: **exit 0**. Next 14.2.35, статические auth/home
страницы и динамические `/candidate/[section]`, `/employer/[section]` присутствуют.
Рабочий `.next` не перезаписывался production build.
Отдельный ESLint не выполнен: нет lint script/config/dependency. Строка Next
«Linting and checking validity of types» не объявляется полноценным ESLint PASS.

### D — dev DB

```sh
docker compose -f infra/docker-compose.yml exec -T api alembic current
docker compose -f infra/docker-compose.yml exec -T api alembic check
```

Результаты: 0010 head, No new upgrade operations detected. COUNT/PK/FK/qualification/
needs aggregates через SQLAlchemy connection после `SET TRANSACTION READ ONLY`.
Connection URL/password и данные пользователей не выводились.

### R — published artifacts

Через API python: `CatalogRepository().validate_all()`; для каждого activeBlueprint
прочитаны только id/version/status и количества questions в variants. PASS, 240.

### T — существующие pytest, без записи в dev-БД

Первый запуск (важен порядок файлов для воспроизведения setup-проблемы):

```sh
docker compose -f infra/docker-compose.yml exec -T api pytest -q tests/integration/test_auth_registration.py tests/integration/test_auth_login.py tests/integration/test_candidate_profile.py tests/integration/test_employer_company.py tests/integration/test_employer_needs.py tests/integration/test_assessment_v3_lifecycle.py tests/test_assessment_v3.py tests/test_ranking.py tests/integration/test_ranking_create.py tests/integration/test_recommendations.py tests/integration/test_talent_bank.py tests/integration/test_invitations.py tests/integration/test_contact_disclosure.py tests/integration/test_invitation_privacy.py tests/integration/test_profile_pdf.py
```

**211 passed, 155 errors, 1 warning, 266.69s, exit 1.** Ошибки setup:
`fixture 'migrated_engine' not found`, начиная с test_ranking_create после unit files.
Это подтверждённая проблема запуска выбранной комбинации, не 155 подтверждённых API-дефектов.
Root cause окончательно не установлен; fixture/import collection требует отдельного исправления.

Для отделения этой проблемы от API повторена только упавшая integration-группа:

```sh
docker compose -f infra/docker-compose.yml exec -T api pytest -q --tb=short tests/integration/test_ranking_create.py tests/integration/test_recommendations.py tests/integration/test_talent_bank.py tests/integration/test_invitations.py tests/integration/test_contact_disclosure.py tests/integration/test_invitation_privacy.py tests/integration/test_profile_pdf.py
```

**156 passed, 1 warning, 155.83s, exit 0.** Числа двух запусков не суммируются как
уникальные tests: есть пересечение. Warning — существующий Starlette/httpx deprecation.
Полный pytest сейчас не запускался. Предыдущие 601 passed относятся к более раннему
состоянию и не выдаются за полный зелёный прогон текущего checkout.

## 11. Сквозной сценарий: что доказано

1. Открытие сайта — H 200, browser rendering не проверен.
2–7. Register → verify → login → profile → start → answers: есть код frontend,
   API-составляющие проверены T на изолированных данных. Единая browser-цепочка **не проверена**.
8. «Получить подтверждённый grade после обычного теста» — **первый гарантированно
   заблокированный бизнес-шаг**: активный DEMO не имеет права это делать. Обычный score/result
   получить можно по коду и API-тестам, но не подтверждённую квалификацию.
9–10. Employer/company/need — API T PASS, UI не проверен. Для текущих 4 legacy needs
   потребуется корректно заполнить минимум minGrade/specialization и canonical skills.
11–13. Ranking — пустая валидная cohort поддержана; текущие legacy needs сначала дают 422.
   Новая валидная need при 0 квалификаций должна дать пустой snapshot; такой рабочий POST
   не выполнялся, чтобы не записывать данные. Поведение подтверждено T, не dev-операцией.
14–17. Invitation/accept/status — API подтверждены T с test-only fixtures, реального browser
   прогона/положительной выдачи нет. Не обходить gates для демонстрации.

**Последний фактически выполненный live UI-related шаг аудита — HTTP GET страницы.**
Нельзя назвать шаг 7 «проверенно работающим в браузере» и притвориться, что прошли 1–7.
Отдельно можно утверждать, что бизнес-правила гарантированно блокируют ожидаемый шаг 8.

## 12. Ошибки и несоответствия

1. Воспроизведённый setup failure смешанного pytest запуска (T1), несмотря на T2 PASS.
2. Все рабочие 4 needs несовместимы с текущими ranking prerequisites; это состояние данных,
   не основание ослаблять validation. Нет automatic backfill, данные не изменены.
3. README устарел: «frontend заглушка», «auth не реализован», bcrypt, head 0002.
   Источником факта были код/live OpenAPI/current/check, не эти утверждения.
4. `docs/validation.md` и сохранённый evaluation report описывают прежний ranking 503;
   сейчас create_snapshot рассчитывает рейтинг. Это исторические отчёты, не текущий status.
5. Новый catalog route не имеет отдельного API regression-test/response_model; successful
   authenticated response не проверен этим аудитом. Отметка НЕ ПРОВЕРЕНО, не утверждение о поломке.
6. History/list snapshots/delete need/FSP API/category filter отсутствуют или ограничены.
   Обязательность части этих функций нужно сверить с оригинальным ТЗ.
7. UI generic 409 и отсутствие browser suite — риск demo, не воспроизведённый UX crash.
8. Отдельные причины недопуска не возвращаются; пользователю доступно
   общее empty state. Требование granular rejection reasons по ТЗ не установлено.

## 13. Критические блокеры демонстрации

- P0: нет APPROVED-контента/реальных квалификаций для положительной цепочки test→ranking→invite.
- P0: нет подтверждённого интерактивного browser E2E текущих новых кабинетов.
- P1: legacy needs в рабочей БД не готовы к ranking; нужна валидная демонстрационная потребность.
- P1: нестабильный способ запуска regression suite, нужен воспроизводимый acceptance command.
- P1: trusted FSP confirmation/provider отсутствует, positive FSP bonus демонстрировать нельзя.

Не считать требование «сделать красивую выдачу» разрешением на присвоение DEMO qualification.

## 14. Приоритетный план и ответы

Первые пять задач с максимальным эффектом:

1. **P0:** согласовать режим показа. Либо настоящая экспертная проверка immutable новой
   APPROVED-версии, либо отдельный изолированный стенд с явными synthetic/test-only fixtures.
   В production/dev не менять DEMO gate и не выдавать тестовое approval за экспертное.
2. **P0:** выполнить browser acceptance двумя contexts (candidate/employer), третьим employer
   проверить masked/404, затем revoke consent и PDF. Записать фактические результаты каждого шага.
   Сначала проверить `/catalog` с настоящим authenticated тестовым session на изолированном стенде.
3. **P1:** подготовить валидную company/need через существующий UI в согласованном тестовом
   окружении, а не seed/reset рабочей БД; повторить save/reload/ranking empty/positive fixture.
4. **P1:** исправить pytest fixture discovery/import reproducibility минимально; повторить
   только affected suite, обновить validation report, README и команды демонстрации.
5. **P1:** зафиксировать границы обещаний: FSP/history/category. Подключать trusted FSP только
   при наличии контракта источника; не реализовывать предложенную шкалу как утверждённую.

P2: отдельные human-readable сообщения conflict/cooldown, история вместо ручных ID,
нагрузка cohort scan/locks, accessibility/mobile browser smoke, lint configuration.
Переписывание архитектуры, микросервисы и замена БД не нужны.

### Пять ответов

1. **Процент обязательного MVP:** не вычисляется — оригинал ТЗ не найден, обязательный
   знаменатель неизвестен. Не заменять его количеством endpoints/tests. Матрица этого аудита
   содержит 44 строки проверок; это перечень аудита, не шкала готовности организаторов.
2. **Можно ли показать жюри:** можно показать интерфейс, инфраструктуру и честный DEMO-сценарий;
   заявлять проверенный полноценный положительный end-to-end пока нельзя.
3. **Первый сломанный шаг:** live browser цепочка не проверена; первый известный бизнес-блокер —
   шаг 8, присвоение verified grade из DEMO. При выборе legacy need дополнительно 422 на ranking.
4. **Пять задач:** перечислены выше, приоритет — правдивый demo-стенд и реальный browser smoke.
5. **Что реально успеть:** проверить UI на существующих API, настроить изолированные fixtures,
   подготовить валидную need, стабилизировать тестовую команду и обновить документы.
   Нельзя обещать независимую DS-валидацию/экспертное approval и trusted FSP «за несколько минут».

Команда запуска существующего MVP (приведена, но повторно аудитом не выполнялась):

```sh
docker compose -f infra/docker-compose.yml up --build
```

Web http://localhost:3000, Swagger http://localhost:8000/docs, Mailpit http://localhost:8025.
Не запускать reset/seed/upgrade ради этого отчёта. Проверенная dev-БД уже на 0010.
