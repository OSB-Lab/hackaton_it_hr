# MVP validation — SPR-6.2

Checkout: `feat/spr-18`, 2026-10-10. Working tree содержит незакоммиченные SPR-15/17/18,
invitations/contact disclosure и PDF. Это технический отчёт, не экспертное одобрение банка.

## Воспроизведение

Из корня репозитория, при работающих Compose api/web/postgres и установленных зависимостях:

```sh
python commands/validate.py
python -m unittest discover -s commands/tests -v
```

Runner последовательно выполняет backend pytest → frontend lint → frontend build →
Playwright primary flow → DS ranking evaluation, затем существующую assessment synthetic validation.
Рабочая директория docker-команд `/app`; frontend build/lint выполняются в временной копии
`/tmp/fsp-validation.*` в web-контейнере с его node_modules, без изменения рабочего `.next`.
Временные build-файлы остаются в контейнере для диагностики, до его пересоздания.
Backend conftest создаёт `fsp_test_<uuid>`, мигрирует и удаляет только эту тестовую БД.
Runner не запускает upgrade/stamp/reset/dev-seed и не запускает browser tests против dev-БД.

JSON и отдельный stdout/stderr log каждого выполненного этапа сохраняются в
`.cache/validation/<UTC timestamp>/`. `report.json` содержит команды, cwd, exit codes,
SHA256 backend tree и manifest. `evaluation.json` содержит результаты DS evaluation.
Exit codes: 0 — все этапы PASS; 1 — есть FAIL; 2 — есть BLOCKED без FAIL.
Пропуски никогда не считаются успешными. Отсутствие Docker/timeout — FAIL с логом.

Для использования достоверного предыдущего backend-прогона без дорогого повторения:

```sh
python commands/validate.py --skip-backend
```

Эта команда намеренно показывает backend **BLOCKED/NOT_RUN**, а не cached PASS.
Предыдущие 601 passed за 406.41s относятся к неизменённому backend SPR-6.1;
в этой задаче backend-код и его тесты не менялись. Эти результаты включают миграционные
тесты/`alembic check` на временных БД, auth, ownership, privacy, v3, invitations и PDF.
Одно существующее предупреждение Starlette/httpx. Полный pytest повторно не запускался.

## Фактические результаты и версии

| Проверка | Статус | Доказательство / ограничение |
|---|---|---|
| Backend pytest | PASS предыдущего прогона; NOT_RUN сейчас | 601 passed; код backend не изменён |
| Evaluation harness / runner exit codes | PASS | 11 unit tests; не dataset для оценки ranking |
| Frontend lint | BLOCKED | Нет npm script lint, ESLint configuration/dependency |
| Frontend build | PASS | Реальный npm run build, не typecheck вместо build |
| Playwright primary flow | BLOCKED | Нет конфигурации, spec, UI и изолированного E2E окружения |
| Ranking Precision@3 | BLOCKED / null | Нет ranking adapter и независимых labels/fixtures |
| Weak/medium/strong ranking scenarios | NOT_RUN | Нет утверждённых scenario fixtures |
| Ranking determinism и paired variants | NOT_RUN | Нет ranking implementation / paired fixtures |
| Assessment synthetic agents | PASS | Существующий validate_v3_skill_agents.py, 4 клетки × 5 агентов × A/B/C |

Catalog `fsp-catalog-v3-demo`; blueprints `backend/frontend × junior/middle`, версия
`v3-demo`, варианты A/B/C, статус DEMO. Точные artifact SHA256 — в
`services/api/app/data/catalog/manifest.json`, hash manifest — в report.json.
Версия ranking отсутствует: production `create_snapshot` возвращает 503 без записи.
Evaluation fixtures / relevance-label version отсутствуют. Значения Precision@3 не публикуются.

Существующие assessment fixtures — `services/api/docs/v3/business-logic/questions-v3.json`,
сценарии — `services/api/docs/v3/arch/validate_v3_skill_agents.py`. Это синтетические
novice/junior/strong-junior/middle/core-gap агенты, не подмена DS weak/medium/strong ranking labels.
На A/B/C проверяется согласованность fail против pass/high; одинаковый численный score
не требуется. Например frontend-middle: novice = 0/18,1/18,1/18 (все fail),
middle = 14/18 pass,17/18 high,15/18 pass; strong-junior = 11/18,12/18,8/18 (все fail).
Все 60 значений находятся в `assessment-synthetic-validation.log`.
Backend parity/границы scorer уже покрыты существующими pytest; повторного scorer в harness нет.

Зафиксированный запуск: `.cache/validation/20261010T110540980689Z/report.json`.
Копии отчёта и успешных логов сохранены в `docs/validation/` для review.
Первый sandbox-run не получил доступ к Docker и правильно отметил build FAIL;
после разрешения доступа реальный build прошёл. Наличие BLOCKED делает общий workflow незавершённым.

**Synthetic data и сценарии, использованные при настройке алгоритма, не доказывают production accuracy.**
Внутренняя проверка не является независимой экспертной валидацией. DEMO не становится APPROVED.

## Подключение DS без изменения production eligibility

```sh
python commands/evaluate.py --fixtures PATH/fixtures.json --labels PATH/labels.json --output PATH/evaluation.json --ranking-command python PATH/ranking_adapter.py
```

Адаптер — доверенный локальный offline executable, без БД и побочных эффектов.
Получает JSON `case.input` через stdin; stdout — только JSON
`{"algorithmVersion":"<real version>","orderedCandidateIds":["<candidate ID>"]}`.
Если нужны scores, адаптер может добавить их в вывод: детерминированность сравнивает весь JSON.
Три запуска отдельного процесса на каждый case, timeout 120s, неизвестные/повторные IDs — FAIL.

Fixtures schemaVersion=1: `version` (непустая immutable версия), `blueprintVersions` (список),
`cases` (непустой список). Каждый case: уникальный `id`, `scenario` weak/medium/strong,
`profileId`, необязательный `variant`, `candidateIds` (минимум 3 уникальных строковых IDs),
`input` (данные именно для настоящего ranking adapter).
Paired cases одного profileId должны иметь одинаковый need/cohort/profile, различаясь
только вариантом assessment; это обязательство автора fixture, не утверждение harness.

Labels schemaVersion=1: `version`, `fixtureVersion` (точное совпадение),
`provenance: {independentOfTuning: true, reference: "<document/dataset reference>"}`,
`labels: {"<case ID>": {"<candidate ID>": true/false}}`.
Нужны явные независимые бинарные метки для каждого кандидата каждого case, без пропусков.
Нельзя выводить labels из score, позиции или формулы проверяемого алгоритма.
Метаданные происхождения — декларация DS, не криптографическое доказательство независимости.

Precision@3 = количество relevant в первых трёх / 3; короткий список не уменьшает знаменатель.
Итог — macro average по cases, дополнительно выводятся каждый case, порядок, группы вариантов,
их sameOrder и версии/hash входных файлов. Отсутствие weak/medium/strong или paired variants — BLOCKED.
PASS означает успешное выполнение evaluation, **не принятие качества**: DS/продукт ещё должны
зафиксировать целевой P@3 и допустимую разницу вариантов. Произвольные пороги не добавлены.

## Передача frontend / Playwright

Фактически `apps/web/app/page.tsx` содержит только FSP Platform и ссылку health.
`apps/web/e2e/primary-flow.spec.ts`, Playwright configuration/dependency отсутствуют.
Не созданы фиктивные spec, UI, mocks или skip-as-PASS. Primary flow runner пока BLOCKED;
после интеграции надо подключить реальный Playwright command с guard изолированной тестовой БД.

Предлагаемые стабильные `data-testid` для согласования (пока не существуют):

| Шаг | Селекторы / действия |
|---|---|
| Login | login-email, login-password, login-submit; войти двумя отдельными contexts candidate/employer |
| Profile/privacy | profile-name, profile-stack, consent-processing, consent-publication, privacy-show-contacts, profile-save |
| Assessment | assessment-start, assessment-question-<id>, assessment-option-<id>, assessment-submit, assessment-result |
| Employer need | need-title, need-specialization, need-min-grade, need-target-grade, need-required-skills, need-save |
| Recommendations | recommendations-load, candidate-card-<id>, candidate-contact (отсутствует до разрешения) |
| Invitation | invitation-offer, invitation-contact-method, invitation-salary-min/max, invitation-send |
| Candidate inbox | invitation-<id>, invitation-accept, invitation-decline, invitation-status |
| Disclosure | invitation-details, candidate-contact; проверять email/phone и отсутствие в остальных карточках |
| PDF | profile-pdf-download; waitForEvent('download'), PDF MIME/текст и отсутствие контактов |

Третий независимый context для другого employer: чужое invitation 404, его собственные карточки
masked даже после accept первому employer. После отзыва consent/show_contacts — снова masked
для origin employer. Не ограничиваться DOM: проверять API response bodies и скачанный PDF.
Технические API privacy/state-machine тесты уже существуют и не зависят от этих экранов.

Для настоящего primary flow нужны ranking integration и экспертно одобренный versioned контент.
Контролируемые APPROVED fixtures допустимы только в изолированном тестовом окружении и должны
явно обозначаться test-only; они не доказывают readiness production DEMO-пула.
Frontend добавляет lint script/config, UI, Playwright dependency/config/spec и согласованные selectors.
DS передаёт adapter/version, held-out labels с происхождением, сценарии/paired fixtures и критерии качества.
Это критические блокеры end-to-end и заявления о качестве рекомендаций, не повод ослаблять gates.
