'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useState } from 'react';
import { Alert, AuthShell, Button, Field } from '../_components/ui';
import { ApiError, authApi, cabinetPath, tokenStore } from '../_lib/api';

function LoginForm() {
  const router = useRouter();
  const expired = useSearchParams().get('expired') === '1';

  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    if (!email.trim() || !password) {
      setError('Введите email и пароль');
      return;
    }

    setLoading(true);
    try {
      const { access_token } = await authApi.login({ email: email.trim(), password });
      tokenStore.set(access_token);
      // Роль берём с сервера, чтобы отправить человека в нужный кабинет.
      const user = await authApi.me();
      router.replace(cabinetPath(user.role));
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось войти. Попробуйте ещё раз');
      setLoading(false);
    }
  }

  return (
    <AuthShell
      title="Вход"
      subtitle="Войдите, чтобы открыть свой кабинет."
      footer={
        <>
          Нет аккаунта?{' '}
          <Link href="/register" className="font-semibold text-brand hover:underline">
            Зарегистрироваться
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {expired && !error && <Alert kind="info">Сессия истекла. Войдите снова.</Alert>}
        {error && <Alert kind="error">{error}</Alert>}

        <Field
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          id="password"
          label="Пароль"
          type="password"
          autoComplete="current-password"
          value={password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Button type="submit" loading={loading}>
          Войти
        </Button>
      </form>
    </AuthShell>
  );
}

// useSearchParams требует Suspense при сборке Next.js.
export default function LoginPage() {
  return (
    <Suspense>
      <LoginForm />
    </Suspense>
  );
}
