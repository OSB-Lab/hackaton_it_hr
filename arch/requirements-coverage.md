# Матрица соответствия ТЗ

> Источник: `materials/ФСП спец. трек ТЗ.pdf`, разделы 2–7. Эта матрица — единый контрольный список: нельзя называть решение соответствующим ТЗ, пока пункт со статусом **обязателен для финала** не имеет проверяемого артефакта.

## Статусы

- **P0 недели** — входит в обязательный сквозной демонстрационный сценарий.
- **Обязателен для финала** — требуется ТЗ, но может быть упрощённо реализован/документирован после P0; не удалять из backlog.
- **Плюс/опционально** — прямо отмечен ТЗ как желательный или вынесенный за MVP.
- **Концепция** — ТЗ требует архитектурного подхода, а не рабочей реализации.

## 1. Продуктовая механика и данные (ТЗ §2, §2.2)

| Требование ТЗ | Статус | Решение и проверка |
|---|---|---|
| Самостоятельная ИТ-платформа, прямое соединение работодателя и кандидата, не парсер вакансий | P0 недели | Нет интеграции с job boards; `Next.js → FastAPI → PostgreSQL`. Проверка: два кабинета и собственные seed-данные. |
| Работодатель сам находит категорию/кандидата и направляет предложение с зарплатой | P0 недели | UC-E01/E02; `HiringNeed → RecommendationSnapshot → Invitation`. E2E демонстрирует весь путь. |
| Категория из отрасли/специализации, заявленного грейда и теста, не из самоописания CV | P0 недели | Candidate onboarding + `AssessmentBlueprint/TestAttempt`; matching допускает только подтверждённую category. Unit test: CV не меняет eligibility. |
| Справочник специализаций и грейдов | P0 недели | Для недели: 2 специализации × Junior/Middle в versioned fixture; в документации перечислить их до seed. |
| Ранжирование внутри категории по тесту и достижениям ФСП | P0 недели | Детерминированная формула и factual reasons; FSP — бонус, не блокирующий фактор. |
| Эквивалентные, устойчивые к распространению задания | P0 недели | ≥2 параметризуемых варианта на ячейку blueprint + общая rubric/threshold; report о стабильности. |
| Не понижать грейд принудительно; lower/higher retest и ограничение частоты | Обязателен для финала | Реализовать `retestTargetGrade` и `retestAvailableAt`; failure предлагает lower, уверенный результат — higher, текущий verified grade не меняется вниз. Проверка clock-based test cooldown. |
| Регулярные короткие задания от работодателя | Плюс/опционально | В недельный MVP не входит. В архитектуре: будущий `Challenge` с rubric, freshness и очередью предложений. |
| Связь профиля с ФСП ID; корректный случай без истории | P0 недели | Fixture `FspRegistryProvider`; состояния `linked/no_history/unavailable`; `no_history` имеет bonus 0 и остаётся в поиске. |
| Собственные/synthetic/open данные и собственная процедура оценки | P0 недели | Versioned seed, ручная relevance-разметка, `Precision@3`, stability/discrimination report. |
| Зарплата обязательна в вакансии и invitation, диапазон RUB; видна до общения | P0 недели | `Invitation.salaryMin/salaryMax/currency=RUB`; API/UI validation and E2E. Для optional vacancy — те же поля. |
| Invitation: предложение, зарплата, компания, способ связи; контакты после accept/отклика | P0 недели | State machine и `ContactDisclosure`; JSON scan до/после accept. |
| Статусы взаимодействия | P0 недели | `sent → viewed → accepted|declined`, обе роли видят свой актуальный статус. |
| Email registration с подтверждением | P0 недели | Mailpit/verification token; если demo использует preverified account, в финальной сдаче требуется показать реальный verification flow. |

## 2. Функциональные требования по ролям (ТЗ §2.1)

| Роль и требование | Статус | Минимальное решение / DoD |
|---|---|---|
| Candidate: ручное заполнение профиля и резюме | P0 недели | Форма: ФИО, контакты, стек, грейд, роли, стаж, soft skills. До дня 2 зафиксировать поля и privacy toggle. |
| Candidate: PDF-resume upload с автораспознаванием **или** ручная форма | P0 недели | Выбирается ручная форма; PDF parsing не обещать. |
| Candidate: стандартизированный PDF-профиль | Обязателен для финала | Простая серверная генерация/print template из согласованных полей; download доступен только владельцу. Не зависит от PDF parsing. |
| Candidate: опрос, специализация, заявленный грейд, тест, category | P0 недели | UC-C01. |
| Candidate: история опросов/тестов/category | Обязателен для финала | Экран history из `TestAttempt`: дата, specialization, declared/verified grade, result, category. |
| Candidate: upper/lower retest с cooldown | Обязателен для финала | См. выше; UI показывает дату следующей доступности. |
| Candidate: invitations accept/decline | P0 недели | UC-E02/UC-C04. |
| Candidate: privacy, consent, FSP ID | P0 недели | Consent + visibility settings + FSP fixture status. |
| Candidate: общий список вакансий, отклики, статусы | Плюс/опционально | Не ядро MVP; реализовать только после Core Gate. |
| Employer: company profile | P0 недели | Название, отрасль, описание, контакты. |
| Employer: описать need (команда, стек, specialization, grade) | P0 недели | Form/API `HiringNeed`. |
| Employer: рекомендованные category/candidates + обоснование | P0 недели | Top-K cards, category, 2–3 factual reasons. |
| Employer: весь банк с фильтрами specialization/grade/category/stack/FSP achievements | Обязателен для финала | Один `/talent-search` или расширенный recommendations UI; все пять фильтров, no PII. |
| Employer: filter refinement без потери полученной подборки | Обязателен для финала | Immutable base `RecommendationSnapshot`; URL/query filter state и «Сбросить». |
| Employer: invitation без обязательной vacancy | P0 недели | Invitation создаётся прямо из hiring view. |
| Employer: publish/edit vacancy и работа с откликами | Плюс/опционально | Не до Core Gate. Если реализуется, обязательны salary/status/contact rules. |

## 3. Технические и нефункциональные требования (ТЗ §3)

| Требование | Статус | Артефакт/проверка |
|---|---|---|
| Обычная машина/недорогой VPS, разумная память | P0 недели | Compose из `web/api/postgres/mailpit`, без Redis/ML-model runtime. README содержит требования. |
| Стек свободный; ML/NLP — преимущество, не обязанность | P0 недели | Объяснимый deterministic matching ценнее недоказуемого ML. |
| Frontend / Backend / storage separation | P0 недели | Next.js, FastAPI, PostgreSQL; модульные boundaries в `architecture.md`. |
| Open source, исходный unobfuscated код | Обязателен для финала | LICENSE, public repository, dependency/license list. |
| Docker желателен, воспроизводимый запуск обязателен | P0 недели | Docker Compose, `.env.example`, migration/seed/reset runbook. |
| Все API в OpenAPI/Swagger с request/response/errors | Обязателен для финала | `/docs`, exported `openapi.json`, examples 401/403/409/422. |
| 152-ФЗ: consent, roles, access security, passwords/tokens | P0 недели | Consent version, RBAC, Argon2id, JWT secret env, no PII logs, disclosure guard. В документации честно обозначить, что это не сертификация. |
| Future Keycloak compatibility | Концепция | `IdentityProvider` interface/ADR; текущая auth не должна закрывать OIDC extension. |
| Desktop web, OS-independent deployment | P0 недели | Browser UI + Compose. |
| Mobile/tablet adaptive | Плюс/опционально | Не блокирует MVP; базовая non-breaking layout только если есть время. |
| Десятки concurrent users, acceptable main operations | Обязателен для финала | Health checks, indexes on category/specialization/grade, demo load/smoke note; не заявлять benchmark без измерения. |
| Code quality, docs match code, jury can run code | P0 недели | lint/type/test + demo-reset + README. |

## 4. Демо, документация и сдача (ТЗ §3.3–§5)

| Требование | Статус | Обязательный артефакт |
|---|---|---|
| Сквозное demo: registration → test → category → employer search → contact | P0 недели | Playwright, `docs/demo-script.md`, запись fallback. |
| Показать/объяснить test and matching mechanics | P0 недели | Слайды + blueprints + report + reasons. |
| Architecture, testing, matching, validation, FSP integration, API, libraries/versions, build/run docs | Обязателен для финала | `docs/`/финальная документация с этими 8 разделами; `arch/` — исходный проектный контекст. |
| Presentation PDF/PPTX, repository, deploy link или video + local instructions | Обязателен для финала | Финальный submission checklist в roadmap. |

## 5. Критерии и трассировка доказательств (ТЗ §6–7)

| Критерий | Вес | Доказательство |
|---|---:|---|
| Новая механика подбора | 35% | UC-E01/E02, top-K fixture, explanation cards, E2E invitation/privacy. |
| Тестирование, validation, categorization | 25% | blueprint variants, rubric, stability/discrimination report, category history/retest. |
| Интерфейс | 10% | two-role guided flow, Russian copy, contrast/keyboard smoke. |
| Pitch | 10% | script, live demo, fallback video, Q&A answers. |
| Доп. функции | 7% | vacancies/applications, challenges, ATS/anti-fraud concept, adaptive layout — only after P0. |
| Техническая проработка | 7% | Compose, Swagger, tests, modular boundaries. |
| Полнота/docs | 6% | final docs checklist and no-history/PDF/history/search coverage. |

## 6. Найденные расхождения и решения

1. В прежнем недельном scope ошибочно были вынесены слишком далеко **PDF-профиль, history/retest cooldown и полный filterable talent bank**. ТЗ относит их к ожидаемой функциональности; они возвращены как обязательные до финала и добавлены в roadmap.
2. PDF parsing не требуется, если реализована ручная форма; автогенерация стандартизированного PDF остаётся отдельной обязательной функцией.
3. Vacancy/application, regular challenges, ATS/anti-fraud и mobile действительно остаются optional/plus — это явно согласуется с ТЗ.
4. Неделя — риск: P0 проходит к концу дня 5. Если обязательные финальные пункты не успевают до дня 7, их нельзя вычёркивать или заявлять готовыми: фиксировать как честный known gap и в приоритете делать PDF → history/cooldown → search filters.
