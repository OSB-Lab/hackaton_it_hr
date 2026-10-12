> **Исторический снимок.** Этот документ отражает состояние до удаления разделения demo/real/test
> (флаги `DEMO`/`APPROVED`/`content_status` удалены, миграция `0012`, квалификация — по баллу).
> Актуальное состояние — в [`README.md`](../../README.md) и [`docs/JURY.md`](../../docs/JURY.md).

# Синтетическая проверка таксономического банка

Банк: `taxonomy-curated-demo-v4-683ff1d69aa7`; кандидатов: 1000. **Семантическая валидность: НЕ УСТАНОВЛЕНА.**

| Метрика | Результат |
|---|---:|
| `sameGradePassRate` | 0.659 |
| `adjacentLowerPassRate` | 0.0333 |
| `strongJuniorOnMiddlePassRate` | 0.0697 |
| `typicalMiddlePassRate` | 0.7 |
| `formDecisionStability` | 0.585 |
| `meanScoreSpreadAcrossForms` | 14.62 |
| `lexicalAnswerLeaks` | 0 |
| `duplicateOrAmbiguousOptions` | 0 |
| `categoryShortcutItemFraction` | 0.0 |
| `reusedMvpItems` | 216 |
| `curatedScenarioItems` | 684 |
| `generatedRecognitionItems` | 0 |

Модель ответов использует латентные проценты навыков и **заданную извне**
вероятность ошибки по грейду. Она не выводится из ответов независимых людей.
Поэтому её цифры не доказывают разделяющую силу банка на реальной аудитории.
A/B/C часто повторяют одну и ту же идею; четыре вопроса на навык могут сводиться
к одной предметной карточке с разными формулировками.
Негативный агент, выбирающий единственный инструмент названной категории, теперь не имеет shortcut.
Но без отдельной экспертной разметки и пилота банк остаётся DEMO.
