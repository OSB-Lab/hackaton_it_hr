# Демо-реестр достижений ФСП: контракт и проверка

**Статус:** синтетические записи, **не данные и не подтверждение ФСП**. Основание: ТЗ ФСП, стр. 1–4, 6: история ФСП — дополнительный сигнал *внутри* подтверждённой тестом категории; отсутствие истории допустимо, API/схема ФСП организаторами не предоставлены. Референс `SergeLyamin/fsp-talent` использован для идей объяснимого подбора, но не как источник официальной схемы. Производственный `FSP_DEMO_MODE=false` полностью отключает файл и бонус. Будущая интеграция требует проверки права на FSP ID/происхождения записи; одного `FspLink` для реальной верификации недостаточно.

## Файл

Канонический пример: [`app/modules/fsp/demo_registry.v1.json`](../app/modules/fsp/demo_registry.v1.json). По умолчанию читается он; `infra/docker-compose.yml` включает **только демо-контейнер** (`FSP_DEMO_MODE=true` по умолчанию), а прямой запуск API вне Compose — нет (`false`). Для другой синтетической выборки установить `FSP_DEMO_REGISTRY_PATH=/app/path/to/file.json` (путь должен быть доступен процессу API). Для отключения в Compose: `FSP_DEMO_MODE=false docker compose -f infra/docker-compose.yml up -d --force-recreate api`. Файл читается при новом запросе; malformed/недоступный файл → отказ 503 при создании snapshot/чтении профиля, а не молчаливый нулевой бонус. Размещать файл только в доверенном окружении; нельзя принимать его от кандидата как «подтверждение».

```json
{
  "schemaVersion": 1,
  "source": "fsp",
  "participants": [
    {"fspId": "demo-fsp-002", "achievements": [
      {"recordId": "demo-result-002", "kind": "competition_result",
       "result": "winner", "role": "contributor",
       "skillIds": ["python", "sql"], "achievedAt": "2025-05-12"}
    ]},
    {"fspId": "demo-fsp-003", "achievements": []}
  ]
}
```

- `fspId`: ключ записи, связывается с **существующим** `FspLink` (`status=linked`, `linked_at` задан). Нет записи/связи или пустой `achievements` → нет истории и бонус 0; не исключать кандидата. Дубли `fspId`/`recordId` запрещены.
- `kind`: `competition_result` (результат соревнования) или `sport_rank` (разряд). `result`: `winner`, `prizewinner`, `finalist`, `participant` для соревнования; **только** `awarded` для разряда. Это синтетическая классификация команды, не словарь ФСП.
- `role`: `lead`, `contributor`, `participant` — смоделированная роль кандидата. В реальном командном соревновании её нельзя принимать за проверенный индивидуальный вклад без отдельного подтверждения.
- `skillIds`: непустой список уникальных канонических технических ID `python`, `sql`, `api`, `javascript`, `typescript`, `react`; не свободное текстовое название дисциплины. Связь достижение→навык в реальном продукте потребует экспертной проверки. `achievedAt`: ISO `YYYY-MM-DD`, не в будущем относительно даты ранжирования. `recordId`: уникален внутри участника; хранит стабильную ссылку на запись в синтетическом источнике.
- Не хранить ФИО, контакты, текст резюме и ответы теста. Внешний реестр/Keycloak отсутствуют. `source` обязательно маркирует демо-происхождение.

## Единый порядок решений

1. **Hard gate без ФСП:** verified email, публикация/приватность, успешная квалификационная APPROVED-попытка, та же специализация, допустимый грейд, порог evidence по обязательным skills. DEMO-попытка не создаёт категорию, даже при «победе» в файле. Самозаявленный стек и строки `fsp_achievements` БД не являются свидетельством для score.
2. **Внутри cohort:** `skillFit = .8 × requiredCoverage + .2 × optionalCoverage` (без optional весь вес required), `testStrength = technicalTotal/100`. ФСП: по каждому рекорду `kind/result × role × stack × age`, берётся **максимум одного** рекорда, не сумма. Тип: winner=1, prizewinner=.85, finalist=.6, participant=.25, awarded=.65; роль: lead=1, contributor=.85, participant=.65; стек: `.2 + .8 × |skillIds ∩ need.requiredSkills|/|need.requiredSkills|` (пустой required → .2); давность от даты создания snapshot: до 730 дней=1, до 1825 дней=.7, старше=.4. `fspBonus ∈ [0,1]`. Итог `score=.50×skillFit+.35×testStrength+.15×fspBonus`; отсутствие истории=0, **не штраф**, никакого дополнительного FSP-коэффициента фильтра. Ни один FSP-бонус не обходит hard gate.
3. **Порядок:** score DESC → testStrength DESC → candidate ID ASC. Хранятся версия `v3-mvp-coverage-fsp-demo-2`, веса, score, компоненты и допустимые числовые причины (`Demo FSP bonus`); чтение snapshot не пересчитывает их. Talent Bank `hasFspAchievements` для новых snapshot выводит из сохранённого `fspBonus>0`; фильтр сохраняет ранг и не обходит privacy. Для старых snapshot fallback на текущую связанную запись из файла (исторические старые баллы не переписываются). Профиль владельца получает `fspSource` и `fspAchievements`, когда включён демо-режим.

**Не путать:** `ranking/formal-filtering-spec.md` в проектных материалах — proposal v4 для смежных ролей/грейдов, не работающая политика API. Его коэффициент `Cachievements` *не включён*: двойной учёт с `fspBonus` запрещён. В `docs/v3/business-logic/ASSESSMENT_AND_MATCHING_CONTRACT.md` §14 веса/gate остаются неизменными; здесь описана демо-нормализация бонуса.

## Валидация

```sh
docker compose -f infra/docker-compose.yml run --rm api pytest tests/test_fsp_demo.py tests/integration/test_fsp_demo_flow.py -q
```

`test_twenty_synthetic_candidates_keep_eligibility_and_test_dominant` формирует ровно 20 записей, проверяет отсутствие накопления бонуса, вариацию типа/роли/стека/давности, bounded score и приоритет полностью подтверждённого тестом профиля над более слабым. Это **синтетическая гипотеза**, не оценка Precision@K на реальных кандидатах. Интеграционный тест проверяет путь linked ID → профиль → snapshot → фильтр и неизменность фильтра после смены источника. Для работы реального demo надо включить `FSP_DEMO_MODE=true`, создать связанные записи (`seed_demo` уже создаёт три ID) и обеспечить APPROVED-квалификацию: обычные DEMO-попытки намеренно не допускаются в выдачу.
