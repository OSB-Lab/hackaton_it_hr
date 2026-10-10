'use client';

import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useCallback, useEffect, useRef, useState } from 'react';
import { Alert, AuthShell, Button, Field } from '../_components/ui';
import { ApiError, authApi, cabinetPath, tokenStore } from '../_lib/api';

// Адрес почтового ящика для демо (Mailpit из docker-compose). В боевой версии его не будет.
const DEMO_MAILBOX_URL = 'http://localhost:8025';

function VerifyForm() {
  const router = useRouter();
  const params = useSearchParams();
  const email = params.get('email');
  const urlToken = params.get('token');

  const [token, setToken] = useState(urlToken ?? '');
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const autoSubmitted = useRef(false);

  const submit = useCallback(async (value: string) => {
    const clean = value.trim();
    if (!clean) {
      setError('Вставьте код из письма');
      return;
    }
    setError(null);
    setLoading(true);
    try {
      await authApi.verifyEmail(clean);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось подтвердить email');
    } finally {
      setLoading(false);
    }
  }, []);

  // Если код пришёл прямо в ссылке (?token=...), подтверждаем без лишних действий.
  useEffect(() => {
    if (urlToken && !autoSubmitted.current) {
      autoSubmitted.current = true;
      void submit(urlToken);
    }
  }, [urlToken, submit]);

  function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    void submit(token);
  }

  // Подтверждение не обязательно для входа: если человек уже вошёл, ведём в кабинет.
  async function goNext() {
    if (!tokenStore.get()) {
      router.replace('/login');
      return;
    }
    try {
      const user = await authApi.me();
      router.replace(cabinetPath(user.role));
    } catch {
      router.replace('/login');
    }
  }

  if (done) {
    return (
      <AuthShell title="Email подтверждён">
        <div className="space-y-5">
          <Alert kind="success">Спасибо! Адрес подтверждён, можно продолжать.</Alert>
          <Button type="button" onClick={goNext}>
            Перейти в кабинет
          </Button>
        </div>
      </AuthShell>
    );
  }

  return (
    <AuthShell
      title="Подтвердите email"
      subtitle={
        email
          ? `Мы отправили письмо на ${email}. Скопируйте из него код подтверждения и вставьте ниже.`
          : 'Скопируйте код подтверждения из письма и вставьте ниже.'
      }
      footer={
        <button type="button" onClick={goNext} className="font-semibold text-brand hover:underline">
          Подтвержу позже
        </button>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {error && <Alert kind="error">{error}</Alert>}

        <Field
          id="token"
          label="Код из письма"
          autoComplete="one-time-code"
          spellCheck={false}
          className="text-xs"
          value={token}
          onChange={(e) => setToken(e.target.value)}
        />
        <Button type="submit" loading={loading}>
          Подтвердить
        </Button>

        <Alert kind="info">
          Демо-режим: письмо можно открыть в{' '}
          <a
            href={DEMO_MAILBOX_URL}
            target="_blank"
            rel="noreferrer"
            className="font-semibold underline"
          >
            почтовом ящике Mailpit
          </a>
          .
        </Alert>
      </form>
    </AuthShell>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense>
      <VerifyForm />
    </Suspense>
  );
}
