'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ApiError, authApi, cabinetPath, tokenStore, type Role, type User } from '../_lib/api';
import { Alert, Logo } from './ui';

// Разделы будущих кабинетов (задачи 3.2–3.7). Пока это заглушки, но они показывают,
// как будет устроена навигация, и защищают маршрут по роли.
const SECTIONS: Record<Role, { title: string; text: string }[]> = {
  candidate: [
    { title: 'Профиль и согласия', text: 'Данные, приватность, привязка ФСП ID' },
    { title: 'Тест и категория', text: 'Специализация, грейд, история попыток' },
    { title: 'Приглашения', text: 'Предложения от работодателей с зарплатой' },
    { title: 'Достижения ФСП', text: 'Подтверждённые результаты соревнований' },
  ],
  employer: [
    { title: 'Компания', text: 'Описание и контакты организации' },
    { title: 'Потребность', text: 'Какие специалисты нужны и с каким стеком' },
    { title: 'Подборка', text: 'Рекомендованные кандидаты с объяснением' },
    { title: 'Приглашения', text: 'Отправленные предложения и их статусы' },
  ],
};

const ROLE_TITLE: Record<Role, string> = {
  candidate: 'Кабинет кандидата',
  employer: 'Кабинет работодателя',
};

export function CabinetStub({ role }: { role: Role }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!tokenStore.get()) {
      router.replace('/login');
      return;
    }

    let cancelled = false;
    authApi
      .me()
      .then((current) => {
        if (cancelled) return;
        // Чужой кабинет недоступен: отправляем в свой.
        if (current.role !== role) {
          router.replace(cabinetPath(current.role));
          return;
        }
        setUser(current);
      })
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 401) {
          tokenStore.clear();
          router.replace('/login?expired=1');
          return;
        }
        setError(err instanceof ApiError ? err.message : 'Не удалось загрузить кабинет');
      });

    return () => {
      cancelled = true;
    };
  }, [role, router]);

  function logout() {
    tokenStore.clear();
    router.replace('/login');
  }

  if (error) {
    return (
      <main className="mx-auto max-w-md px-5 py-20">
        <Alert kind="error">{error}</Alert>
      </main>
    );
  }

  if (!user) {
    return (
      <main className="grid min-h-screen place-items-center text-sm text-ink/60">Загрузка…</main>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-muted bg-white">
        <div className="mx-auto flex max-w-5xl items-center justify-between gap-4 px-5 py-4">
          <Logo />
          <div className="flex items-center gap-4 text-sm">
            <span className="hidden text-ink/70 sm:inline">{user.email}</span>
            <button
              type="button"
              onClick={logout}
              className="font-semibold text-brand hover:underline"
            >
              Выйти
            </button>
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-5xl px-5 py-10">
        <h1 className="text-2xl font-bold">{ROLE_TITLE[role]}</h1>

        {!user.is_verified && (
          <div className="mt-6">
            <Alert kind="info">
              Email не подтверждён.{' '}
              <Link
                href={`/verify-email?email=${encodeURIComponent(user.email)}`}
                className="font-semibold underline"
              >
                Подтвердить
              </Link>
            </Alert>
          </div>
        )}

        <ul className="mt-8 grid gap-4 sm:grid-cols-2">
          {SECTIONS[role].map((section) => (
            <li key={section.title} className="rounded-xl border border-muted bg-white p-6">
              <div className="flex items-start justify-between gap-3">
                <h2 className="text-base font-bold">{section.title}</h2>
                <span className="shrink-0 rounded-full bg-surface px-2.5 py-1 text-xs text-ink/70">
                  Скоро
                </span>
              </div>
              <p className="mt-2 text-sm leading-relaxed text-ink/70">{section.text}</p>
            </li>
          ))}
        </ul>
      </main>
    </div>
  );
}
