import Link from 'next/link';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';
import { NetworkArt } from './NetworkArt';

// Общие элементы интерфейса. Радиусы небольшие, линии тонкие: стиль «турнирной таблицы».

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="inline-flex items-center gap-2.5 font-bold">
      <span
        className={`grid h-9 w-9 place-items-center rounded-md text-xs ${
          light ? 'bg-white text-brand' : 'bg-brand text-white'
        }`}
      >
        ФСП
      </span>
      <span className={`text-sm ${light ? 'text-white' : 'text-ink'}`}>ИТ-подбор</span>
    </Link>
  );
}

const AUTH_POINTS = [
  'Категорию определяет тест, а не резюме.',
  'Достижения ФСП подтверждают навыки.',
  'Зарплата указана в первом предложении, контакты открываются после вашего согласия.',
];

// Каркас страниц входа, регистрации и подтверждения: слева смысл продукта на синем фоне, справа форма.
export function AuthShell({
  title,
  subtitle,
  children,
  footer,
}: {
  title: string;
  subtitle?: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <main className="grid min-h-screen lg:grid-cols-[5fr_6fr]">
      <aside className="on-brand relative hidden flex-col overflow-hidden bg-brand p-10 text-white lg:flex">
        {/* Сеть занимает нижнюю часть панели, чтобы линии не проходили по тексту. */}
        <NetworkArt className="pointer-events-none absolute inset-x-0 bottom-14 h-[40%] w-full" />
        <div className="relative">
          <Logo light />
        </div>
        <div className="relative mt-20 max-w-md space-y-6">
          <h2 className="text-3xl font-bold leading-tight">Вас находят по подтверждённым навыкам.</h2>
          <ul className="space-y-3 text-sm leading-relaxed">
            {AUTH_POINTS.map((point) => (
              <li key={point} className="flex gap-3">
                <span className="mt-1.5 h-2 w-2 shrink-0 bg-white" aria-hidden="true" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <p className="relative mt-auto text-xs text-white/85">Федерация спортивного программирования России</p>
      </aside>

      <section className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md">
          <div className="mb-6 lg:hidden">
            <Logo />
          </div>
          <div className="rounded-lg border border-muted bg-white p-6 sm:p-8">
            <h1 className="text-2xl font-bold">{title}</h1>
            {subtitle && <p className="mt-2 text-sm leading-relaxed text-ink/70">{subtitle}</p>}
            <div className="mt-7">{children}</div>
          </div>
          {footer && <div className="mt-5 px-1 text-sm text-ink/70">{footer}</div>}
        </div>
      </section>
    </main>
  );
}

type FieldProps = InputHTMLAttributes<HTMLInputElement> & {
  id: string;
  label: string;
  error?: string;
  hint?: string;
};

export function Field({ id, label, error, hint, className = '', ...props }: FieldProps) {
  const describedBy = error ? `${id}-error` : hint ? `${id}-hint` : undefined;
  return (
    <div>
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`w-full rounded-md border bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/25 ${
          error ? 'border-accent' : 'border-muted'
        } ${className}`}
        {...props}
      />
      {error ? (
        <p id={`${id}-error`} className="mt-1.5 text-xs text-accent-dark">
          {error}
        </p>
      ) : hint ? (
        <p id={`${id}-hint`} className="mt-1.5 text-xs text-ink/60">
          {hint}
        </p>
      ) : null}
    </div>
  );
}

export function Button({
  loading = false,
  variant = 'primary',
  className = '',
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'accent';
}) {
  const styles = {
    primary: 'bg-brand text-white hover:bg-brand-dark',
    // Красный используется только для действий работодателя (например, «Отправить предложение»).
    accent: 'bg-accent text-white hover:bg-accent-dark',
    secondary: 'border border-ink bg-white text-ink hover:bg-surface',
  }[variant];
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex w-full items-center justify-center rounded-md px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles} ${className}`}
    >
      {loading ? 'Подождите…' : children}
    </button>
  );
}

export function Alert({
  kind,
  children,
}: {
  kind: 'error' | 'success' | 'info';
  children: ReactNode;
}) {
  const styles = {
    error: 'border-accent/40 bg-accent/10 text-accent-dark',
    success: 'border-green-700/30 bg-green-50 text-green-900',
    info: 'border-brand/30 bg-brand-soft text-brand-dark',
  }[kind];
  return (
    <div
      role={kind === 'error' ? 'alert' : 'status'}
      className={`rounded-md border px-4 py-3 text-sm leading-relaxed ${styles}`}
    >
      {children}
    </div>
  );
}
