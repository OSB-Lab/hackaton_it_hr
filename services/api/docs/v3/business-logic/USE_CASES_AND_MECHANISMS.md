> **Исторический снимок.** Этот документ отражает состояние до удаления разделения demo/real/test
> (флаги `DEMO`/`APPROVED`/`content_status` удалены, миграция `0012`, квалификация — по баллу).
> Актуальное состояние — в [`README.md`](../../README.md) и [`docs/JURY.md`](../../docs/JURY.md).

# Сквозные use cases и механики

## UC-01: Категоризация кандидата

**Actor:** Candidate.  
**Preconditions:** email verified; profile заполнен; есть specialization и self-declared grade; нет active attempt.

1. Candidate выбирает `backend|frontend` и предполагаемый `junior|middle`.
2. API проверяет cooldown и доступность blueprint.
3. API выбирает server-side A/B, а при retest — невиданную этим candidate форму; сохраняет immutable snapshot вопросника.
4. Candidate получает public questions без answer keys и отправляет ответы.
5. API атомарно считает question scores, technical total и `skillEvidence` по тегам.
6. API применяет FAIL/PASS/HIGH и обновляет verified grade только по контракту.
7. UI показывает category status, technical total, skill evidence, diagnostic teamwork и разрешённое следующее действие.

**DoD:** чужой user не читает attempt; повторный submit не пересчитывает результат; raw answer keys не выходят наружу.

## UC-02: FAIL, lower retest и сохранение категории

- FAIL — `<13/18` technical или evidence любого core skill `<50%`.
- Если grade ещё не подтверждён и candidate не сдал Middle, UI предлагает Junior.
- Если Junior уже verified, несданный Middle не понижает категорию и не предлагает бессмысленно пересдать Junior.
- FAIL не запускает cooldown.

## UC-03: PASS/HIGH и cooldown

- PASS: 13–15/18 и каждый core skill ≥50%.
- HIGH: 16–18/18 и каждый core skill ≥70%; предлагает следующий grade, если он доступен.
- PASS/HIGH, впервые установивший или повысивший verified grade, записывает `last_grade_change_at`.
- До `last_grade_change_at + 90 days` блокируется start на том же или более высоком grade; API отдаёт `409` и `retestAvailableAt`.

## UC-04: Доказательства навыков и профиль

`skillEvidence` считается из всех questions с соответствующим `skillTags`:

```text
correct tagged questions / all tagged questions * 100
```

Один верный multi-tag item повышает evidence всех его tags, но участвует в total ровно один раз.

Профильные статусы:

- `verified` — достаточное evidence по skill;
- `unverified` — skill заявлен, но evidence недостаточно;
- `discrepancy` — заявлен как основной, но test evidence ниже порога;
- `not_assessed` — skill нет в текущем canonical blueprint.

Система никогда молча не удаляет self-declared skill: предлагает кандидату review/уточнение.

## UC-05: Подбор работодателя

### Eligibility gate

Кандидат попадает в подборку только при наличии:

- verified email;
- publication consent;
- verified specialization, совпадающей с need;
- verified grade ≥ `need.minGrade`;
- submitted attempt, установившего текущую category.

ФСП, свободное резюме, self-declared grade и высокий один skill не обходят gate.

### Ranking

```text
rankScore = 0.50 * skillFit + 0.35 * testStrength + 0.15 * fspBonus
```

- `skillFit`: evidence required skills (80%) и optional skills (20%).
- `testStrength`: technical total attempt, установившей category.
- `fspBonus`: только подтверждённые achievements; `no_history = 0`.

Tie-break: rankScore DESC → technicalTotal DESC → candidateId ASC. Snapshot ranking неизменяем; filters только скрывают/показывают items, не пересчитывают порядок.

## UC-06: Контакты и приглашение

Employer видит category, evidence и объяснение ранжирования, но не phone/email/raw answers. Invitation содержит company, salary range RUB, offer description и contact method. Только `accepted` создаёт `ContactDisclosure`; только исходный employer после accept видит контакты. Второй employer остаётся masked.

## Validation

- `../arch/validate_v3_skill_agents.py` — question-level synthetic agents, включая сильного Junior и Middle с gap в одном core skill.
- Перед release: expert review item content, real/labelled pilot, Precision@3 и E2E candidate → ranking → invitation → accept.
