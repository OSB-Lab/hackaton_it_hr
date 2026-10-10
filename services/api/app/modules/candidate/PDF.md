# Экспорт профиля (SPR-6.1)

`GET /me/profile-pdf`, `Authorization: Bearer <access JWT>`, только candidate.
Query parameters не поддерживаются; ID берётся исключительно из auth context.
Ответ: `200 application/pdf`, `Content-Disposition: attachment; filename="candidate-profile.pdf"`,
`Cache-Control: no-store`. Генерация в памяти, публичного URL и сохранения файла нет.

Экспорт: имя, специализация профиля (не объявляется подтверждённой), стек.
Подтверждённые specialization/grade выводятся только через существующий `qualification()`:
сохранённая успешная APPROVED v3 submitted attempt. Иначе «Квалификация не подтверждена».
Отдельного подтверждённого поля category в модели нет; категория не выдумывается.
Self-declared/legacy grade, результаты DEMO и внутренности assessment не экспортируются.

Email/phone исключены **всегда**, независимо от showContacts: текущий контракт раскрытия
контактов разрешает их origin employer через invitation, но не определяет portable export.
ContactDisclosure не читается и не создаётся. Строки с контактами также исключаются
из свободных полей. FSP achievements не экспортируются как подтверждённые: в текущей
таблице нет проверяемого признака подтверждения/происхождения, а seed содержит demo data.
Это не изменение существующих privacy/consent правил.

ReportLab 4.4.4 формирует PDF напрямую (без HTML/browser/network). Пользовательские
строки экранируются перед передачей в Paragraph. DejaVu Sans устанавливается Dockerfile
(`fonts-dejavu-core`) и встраивается в PDF, поддерживая кириллицу. Для запуска вне Docker
нужен `/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf`. Произвольные emoji/CJK не гарантируются.
pypdf 6.1.1 используется тестами для извлечения текста и проверки декодированных объектов.

## Frontend

Ошибки: 401 — войти заново; 403 — не candidate; 404 — сначала заполнить профиль;
422 — убрать query parameters; 5xx — показать ошибку, не сохранять ответ как PDF.

```ts
const response = await fetch('/api/me/profile-pdf', {
  headers: { Authorization: `Bearer ${accessToken}` },
});
if (!response.ok) throw new Error(`PDF export: ${response.status}`);
const url = URL.createObjectURL(await response.blob());
const link = document.createElement('a');
link.href = url;
link.download = 'candidate-profile.pdf';
document.body.appendChild(link);
link.click();
link.remove();
setTimeout(() => URL.revokeObjectURL(url), 1000);
```

`/api` — существующий Next proxy; при прямом API вызове путь `/me/profile-pdf`.
Frontend-команда добавляет ProfilePdfButton.tsx и browser E2E скачивания в candidate session,
проверяет 401/403 и открытие файла. Образ API требуется пересобрать для новых зависимостей.
Миграций нет; production DEMO-пул по-прежнему не даёт verified qualification.
