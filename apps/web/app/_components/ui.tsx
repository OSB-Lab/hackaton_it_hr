import Link from 'next/link';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';

// Небольшой набор общих элементов интерфейса в стиле ФСП.

export function Logo({ light = false }: { light?: boolean }) {
  return (
    <Link href="/" className="inline-flex items-center gap-2.5 font-bold">
      <span
        className={`grid h-9 w-9 place-items-center rounded-lg text-xs ${
          light ? 'bg-white text-brand' : 'bg-brand text-white'
        }`}
      >
        ФСП
      </span>
      <span className={`text-sm ${light ? 'text-white' : 'text-ink'}`}>ИТ-подбор</span>
    </Link>
  );
}

// Каркас страниц входа, регистрации и подтверждения: слева смысл продукта, справа форма.
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
    <main className="grid min-h-screen lg:grid-cols-[1fr_1.1fr]">
      <aside className="hidden flex-col justify-between bg-brand p-10 text-white lg:flex">
        <Logo light />
        <div className="max-w-md space-y-6">
          <h2 className="text-3xl font-bold leading-tight">Работодатель находит вас сам.</h2>
          <ul className="space-y-4 text-sm leading-relaxed text-white/90">
            <li>— Категория определяется тестом, а не резюме.</li>
            <li>— Подтверждённые достижения ФСП видны работодателю.</li>
            <li>— Зарплата указана в первом же предложении, а контакты открываются только после вашего согласия.</li>
          </ul>
        </div>
        <p className="text-xs text-white/80">Федерация спортивного программирования России</p>
      </aside>

      <section className="flex items-center justify-center px-5 py-10">
        <div className="w-full max-w-md">
          <div className="mb-8 lg:hidden">
            <Logo />
          </div>
          <h1 className="text-2xl font-bold">{title}</h1>
          {subtitle && <p className="mt-2 text-sm leading-relaxed text-ink/70">{subtitle}</p>}
          <div className="mt-8">{children}</div>
          {footer && <div className="mt-6 text-sm text-ink/70">{footer}</div>}
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
        className={`w-full rounded-lg border bg-white px-3.5 py-2.5 text-sm outline-none transition focus:border-brand focus:ring-2 focus:ring-brand/30 ${
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
  variant?: 'primary' | 'secondary';
}) {
  const styles =
    variant === 'primary'
      ? 'bg-brand text-white hover:bg-brand-dark'
      : 'border border-muted bg-white text-ink hover:border-brand';
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex w-full items-center justify-center rounded-lg px-4 py-3 text-sm font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${styles} ${className}`}
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
      className={`rounded-lg border px-4 py-3 text-sm leading-relaxed ${styles}`}
    >
      {children}
    </div>
  );
}
