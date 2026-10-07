# Auth: schemas, security, registration and email verification (SPR-11.1–SPR-11.3)

Схемы импортируются из `app.modules.auth.schemas`. Общий тип
`AuthRole = Literal["candidate", "employer"]` соответствует строковому полю
`User.role` и CHECK constraint существующей таблицы. Нового enum в БД нет.

| Endpoint | Request schema | Response schema | HTTP |
| --- | --- | --- | --- |
| POST /auth/register | RegisterRequest | UserResponse | 201 |
| POST /auth/login | LoginRequest | TokenResponse | 200 |
| GET /auth/me | — | UserResponse | 200 |
| POST /auth/verify-email | VerifyEmailRequest | VerifyEmailResponse | 200 |

- `RegisterRequest`: email: str, password: str, role: AuthRole.
- `UserResponse`: id: int, email: str, role: AuthRole, is_verified: bool.
- `LoginRequest`: email: str, password: str.
- `TokenResponse`: access_token: str, token_type: Literal["bearer"] = "bearer".
- `VerifyEmailRequest`: token: str.
- `VerifyEmailResponse`: status: Literal["ok"] = "ok".

`UserResponse.model_validate(user)` читает поля ORM через
`from_attributes=True`. В ответ не входят password_hash и created_at.
Пароль запроса остаётся строкой и скрыт из repr схемы; это не хеширование.
RegisterRequest и LoginRequest используют общий NormalizedEmail:
внешние пробелы удаляются, весь адрес приводится к нижнему регистру,
затем проверяется EmailStr через email-validator (без DNS-проверок).
Точки и +suffix не удаляются. Правила сложности пароля пока не вводятся.

## Registration and email verification

В app подключён auth router. Реализованы только POST /auth/register и
POST /auth/verify-email; login и me остаются будущими endpoint.

Регистрация вызывает существующий hash_password, сохраняет User с
is_verified=false и возвращает HTTP 201 с UserResponse. Предварительный
SELECT также распознаёт существующие email в другом регистре. Все новые
записи API нормализованы; конкурентные вставки защищает существующий
уникальный индекс ix_users_email. Его нарушение (SQLSTATE 23505)
вызывает rollback и HTTP 409. Другие ошибки БД дают общий HTTP 503,
без SQL и внутренних исключений в ответе.

После commit создаётся verification token и синхронно отправляется письмо.
SMTP не выполняется внутри открытой транзакции БД. Отправка best-effort:
SMTP/network failure сохраняет результат регистрации (201), оставляет
пользователя неподтверждённым и пишет предупреждение только с user_id,
без пароля, token или содержимого SMTP exception.
Повторная регистрация такого email вернёт 409. Повторной отправки письма
и очереди пока нет; для демо следует обеспечить доступность Mailpit заранее.

Письмо plain text содержит JSON с token и инструкцию POST /auth/verify-email.
Нового frontend URL нет. SMTP использует стандартный smtplib, таймаут 5 секунд.
Настройки: SMTP_HOST=mailpit, SMTP_PORT=1025, SMTP_FROM=noreply@fsp.example.
При запуске API вне Docker задайте SMTP_HOST=localhost. UI Mailpit:
http://localhost:8025. В тестах SMTP подменяется и Mailpit не требуется.

Verification декодирует token через security API, находит User и сохраняет
is_verified=true. Повторный валидный token возвращает 200 {"status":"ok"}.
Невалидный, просроченный token, access token и token отсутствующего User
возвращают одинаковый HTTP 400. Ошибка БД даёт общий HTTP 503.

Demo seed теперь создаёт пароли через hash_password из plaintext
демонстрационных credentials JSON. Старые bcrypt-хеши существующих demo
email заменяются на Argon2id один раз. Существующие Argon2id-хеши, включая
пользовательскую смену пароля, повторный seed сохраняет. Новые demo users
имеют is_verified=true. Bcrypt в authentication не поддерживается.

## JWT

Транспорт: `Authorization: Bearer <jwt>`.

Обязательные claims:
- `sub` — строка из положительного целочисленного User.id, например "42";
- `role` — candidate или employer;
- `exp` — срок действия токена.
- `type` — "access" для access JWT.

Security API находится в `app.modules.auth.security`:

```python
hash_password(password: str) -> str
verify_password(password: str, password_hash: str) -> bool
create_access_token(user_id: int, role: AuthRole) -> str
decode_access_token(token: str) -> AccessTokenClaims
create_email_verification_token(user_id: int) -> str
decode_email_verification_token(token: str) -> int
```

`AccessTokenClaims` — immutable Pydantic-модель с полями `sub: str`,
`role: AuthRole`, `exp: int`, `type: Literal["access"]`.
Пароли хешируются через argon2-cffi PasswordHasher с явным Type.ID
и случайной солью. Неверный пароль, повреждённый хеш или неподдерживаемый
формат дают False. Plaintext не сохраняется и не логируется.

Оба вида токенов подписываются PyJWT и имеют exp (UTC Unix timestamp).
Email verification token содержит sub, exp и type="email_verification";
декодер возвращает int user id. Access/verification токены не взаимозаменяемы.
Подпись и exp проверяет PyJWT, обязательные claims и их типы дополнительно
проверяет Pydantic. Допустимый алгоритм берётся только из settings.
Невалидный токен вызывает единый `InvalidTokenError` без HTTP-семантики.
Неверные аргументы создания токенов вызывают ValueError/ValidationError.

Настройки:

| Переменная | Значение по умолчанию |
| --- | --- |
| JWT_SECRET | Обязательна, без default; используется существующая переменная |
| JWT_ALGORITHM | HS256; разрешены HS256, HS384, HS512 |
| ACCESS_TOKEN_TTL_MINUTES | 15, строго больше нуля |
| EMAIL_VERIFICATION_TOKEN_TTL_MINUTES | 1440, строго больше нуля |

AUTH_SECRET не вводится: обе функции используют существующий JWT_SECRET.
В .env.example находится только placeholder; для реального использования
нужен случайный секрет достаточной длины (32/48/64 байта для HS256/384/512).
Security unit tests задают собственные settings и не обращаются к БД.

Verification token stateless: до истечения exp его можно использовать повторно.
Поиск User и установка is_verified выполняются POST /auth/verify-email.

## Dependencies

Публичный путь: `app.modules.auth.dependencies`.

```python
from typing import Annotated
from fastapi import Depends
from app.models.user import User
from app.modules.auth.dependencies import current_user, require_role

# Типы параметров будущих обработчиков:
AuthenticatedUser = Annotated[User, Depends(current_user)]
CandidateUser = Annotated[User, Depends(require_role("candidate"))]
EmployerUser = Annotated[User, Depends(require_role("employer"))]
```

- `current_user` — async FastAPI dependency. Будущая реализация валидирует
  Bearer JWT и возвращает ORM User, а не схему ответа или словарь claims.
- `require_role(role: AuthRole)` — factory async dependency. Использует
  `Depends(current_user)`, возвращает ORM User при нужной роли;
  несовпадение роли в будущей реализации даёт HTTP 403.
- Сигнатуры возвращаемых значений, имена функций и пути импорта зафиксированы.
  Внутренние зависимости чтения JWT/сессии будут добавлены на security-шаге.

Сейчас обе зависимости — заглушки с `NotImplementedError`. Они не
аутентифицируют пользователя и не предоставляют доступ. Их нельзя подключать
к рабочим маршрутам до реализации dependencies в SPR-11.4.
JWT и hashing реализованы в security.py; login, me и RBAC пока не реализованы.
