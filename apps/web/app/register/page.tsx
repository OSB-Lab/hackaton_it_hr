'use client';

import Link from 'next/link';
import { useRouter, useSearchParams } from 'next/navigation';
import { FormEvent, Suspense, useState } from 'react';
import { Alert, AuthShell, Button, Field } from '../_components/ui';
import { ApiError, authApi, tokenStore, type Role } from '../_lib/api';

const ROLES: { value: Role; title: string; text: string }[] = [
  {
    value: 'candidate',
    title: 'Я ищу работу',
    text: 'Пройду тест, получу категорию, и работодатели найдут меня сами.',
  },
  {
    value: 'employer',
    title: 'Я работодатель',
    text: 'Найду нужную категорию специалистов и отправлю предложение с зарплатой.',
  },
];

const EMAIL_PATTERN = /^\S+@\S+\.\S+$/;
const MIN_PASSWORD_LENGTH = 8;

type FieldErrors = { email?: string; password?: string; confirm?: string };

function RegisterForm() {
  const router = useRouter();
  const initialRole = useSearchParams().get('role') === 'employer' ? 'employer' : 'candidate';

  const [role, setRole] = useState<Role>(initialRole);
  const [email, setEmail] = useState('');
  const [password, setPassword] = useState('');
  const [confirm, setConfirm] = useState('');
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  function validate(): FieldErrors {
    const errors: FieldErrors = {};
    if (!EMAIL_PATTERN.test(email.trim())) errors.email = 'Введите корректный email';
    if (password.length < MIN_PASSWORD_LENGTH) {
      errors.password = `Минимум ${MIN_PASSWORD_LENGTH} символов`;
    }
    if (confirm !== password) errors.confirm = 'Пароли не совпадают';
    return errors;
  }

  async function onSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);

    const errors = validate();
    setFieldErrors(errors);
    if (Object.keys(errors).length > 0) return;

    setLoading(true);
    const cleanEmail = email.trim();
    try {
      await authApi.register({ email: cleanEmail, password, role });
    } catch (err) {
      setError(err instanceof ApiError ? err.message : 'Не удалось зарегистрироваться');
      setLoading(false);
      return;
    }

    // Бэкенд не требует подтверждённого email для входа, поэтому сразу входим,
    // а страница подтверждения предложит ввести код из письма.
    try {
      const { access_token } = await authApi.login({ email: cleanEmail, password });
      tokenStore.set(access_token);
    } catch {
      /* аккаунт создан — человек сможет войти вручную */
    }
    router.replace(`/verify-email?email=${encodeURIComponent(cleanEmail)}`);
  }

  return (
    <AuthShell
      title="Регистрация"
      subtitle="Создайте аккаунт. Это займёт минуту."
      footer={
        <>
          Уже есть аккаунт?{' '}
          <Link href="/login" className="font-semibold text-brand hover:underline">
            Войти
          </Link>
        </>
      }
    >
      <form onSubmit={onSubmit} className="space-y-5" noValidate>
        {error && <Alert kind="error">{error}</Alert>}

        <fieldset>
          <legend className="mb-1.5 text-sm font-medium">Кто вы?</legend>
          <div className="grid gap-3 sm:grid-cols-2">
            {ROLES.map((item) => (
              <label key={item.value} className="cursor-pointer">
                <input
                  type="radio"
                  name="role"
                  value={item.value}
                  checked={role === item.value}
                  onChange={() => setRole(item.value)}
                  className="peer sr-only"
                />
                <div className="h-full rounded-lg border border-muted bg-white p-4 transition peer-checked:border-brand peer-checked:bg-brand-soft peer-focus-visible:ring-2 peer-focus-visible:ring-brand/40">
                  <p className="text-sm font-bold">{item.title}</p>
                  <p className="mt-1.5 text-xs leading-relaxed text-ink/70">{item.text}</p>
                </div>
              </label>
            ))}
          </div>
        </fieldset>

        <Field
          id="email"
          label="Email"
          type="email"
          autoComplete="email"
          value={email}
          error={fieldErrors.email}
          onChange={(e) => setEmail(e.target.value)}
        />
        <Field
          id="password"
          label="Пароль"
          type="password"
          autoComplete="new-password"
          hint={`Не короче ${MIN_PASSWORD_LENGTH} символов`}
          value={password}
          error={fieldErrors.password}
          onChange={(e) => setPassword(e.target.value)}
        />
        <Field
          id="confirm"
          label="Повторите пароль"
          type="password"
          autoComplete="new-password"
          value={confirm}
          error={fieldErrors.confirm}
          onChange={(e) => setConfirm(e.target.value)}
        />
        <Button type="submit" loading={loading}>
          Создать аккаунт
        </Button>
      </form>
    </AuthShell>
  );
}

export default function RegisterPage() {
  return (
    <Suspense>
      <RegisterForm />
    </Suspense>
  );
}
