// Клиент для бэкенда. Все запросы идут на /api/*, Next.js проксирует их на FastAPI
// (см. rewrites в next.config.js), поэтому CORS не нужен.
// Контракт описан в services/api/app/modules/auth/README.md.

export type Role = 'candidate' | 'employer';

export interface User {
  id: number;
  email: string;
  role: Role;
  is_verified: boolean;
}

interface TokenResponse {
  access_token: string;
  token_type: 'bearer';
}

// ---------- Токен ----------
// Хранение в localStorage — простое решение для MVP. Токен живёт недолго (по умолчанию 15 минут),
// после истечения бэкенд вернёт 401, и кабинет отправит на страницу входа.

const TOKEN_KEY = 'fsp_access_token';

export const tokenStore = {
  get(): string | null {
    try {
      return window.localStorage.getItem(TOKEN_KEY);
    } catch {
      return null;
    }
  },
  set(token: string): void {
    try {
      window.localStorage.setItem(TOKEN_KEY, token);
    } catch {
      /* хранилище недоступно (приватный режим) — работаем без сохранения */
    }
  },
  clear(): void {
    try {
      window.localStorage.removeItem(TOKEN_KEY);
    } catch {
      /* ничего не делаем */
    }
  },
};

// ---------- Ошибки ----------

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

// Понятные пользователю сообщения по коду ответа. Для конкретного запроса
// их можно переопределить через параметр `errors`.
const DEFAULT_ERRORS: Record<number, string> = {
  400: 'Некорректный запрос',
  401: 'Нужно войти в аккаунт',
  403: 'Недостаточно прав для этого действия',
  404: 'Не найдено',
  409: 'Такая запись уже существует',
  422: 'Проверьте правильность введённых данных',
  503: 'Сервис временно недоступен. Попробуйте чуть позже',
};

interface RequestOptions {
  method?: 'GET' | 'POST' | 'PUT' | 'PATCH' | 'DELETE';
  body?: unknown;
  auth?: boolean;
  errors?: Record<number, string>;
}

async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { Accept: 'application/json' };
  if (options.body !== undefined) headers['Content-Type'] = 'application/json';
  if (options.auth) {
    const token = tokenStore.get();
    if (token) headers.Authorization = `Bearer ${token}`;
  }

  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method: options.method ?? 'GET',
      headers,
      body: options.body !== undefined ? JSON.stringify(options.body) : undefined,
    });
  } catch {
    throw new ApiError(0, 'Нет связи с сервером. Проверьте подключение и попробуйте ещё раз');
  }

  if (!response.ok) {
    const message =
      options.errors?.[response.status] ??
      DEFAULT_ERRORS[response.status] ??
      (response.status >= 500
        ? 'Ошибка на сервере. Попробуйте ещё раз чуть позже'
        : 'Не удалось выполнить запрос');
    throw new ApiError(response.status, message);
  }

  return (await response.json()) as T;
}

// ---------- Авторизация ----------

export const authApi = {
  register: (body: { email: string; password: string; role: Role }) =>
    request<User>('/auth/register', {
      method: 'POST',
      body,
      errors: { 409: 'Пользователь с таким email уже зарегистрирован' },
    }),

  login: (body: { email: string; password: string }) =>
    request<TokenResponse>('/auth/login', {
      method: 'POST',
      body,
      errors: { 401: 'Неверный email или пароль' },
    }),

  me: () =>
    request<User>('/auth/me', {
      auth: true,
      errors: { 401: 'Сессия истекла. Войдите снова' },
    }),

  verifyEmail: (token: string) =>
    request<{ status: 'ok' }>('/auth/verify-email', {
      method: 'POST',
      body: { token },
      errors: { 400: 'Код недействителен или срок его действия истёк' },
    }),
};

export function cabinetPath(role: Role): string {
  return role === 'candidate' ? '/candidate' : '/employer';
}
