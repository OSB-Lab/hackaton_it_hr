import Link from 'next/link';
import type { ButtonHTMLAttributes, InputHTMLAttributes, ReactNode } from 'react';
import { NetworkArt } from './NetworkArt';

// Общие элементы интерфейса. Радиусы небольшие, линии тонкие: стиль «турнирной таблицы».

// Фирменный логотип ФСП — SVG из брендбука. На светлом фоне цветной вариант,
// на тёмном/фиолетовом — белый (logo-white.svg получен перекрашиванием logo-color.svg).
export function Logo({ light = false, className = '' }: { light?: boolean; className?: string }) {
  return (
    <Link href="/" aria-label="ФСП — на главную" className={`inline-flex items-center gap-2.5 ${className}`}>
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={light ? '/brand/logo-white.svg' : '/brand/logo-color.svg'}
        alt="Федерация спортивного программирования"
        width={119}
        height={40}
        className="h-8 w-auto sm:h-9"
      />
      <span className={`text-sm font-semibold ${light ? 'text-white' : 'text-ink'}`}>ИТ-подбор</span>
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
          <div className="rounded-2xl border border-border bg-canvas p-6 shadow-card sm:p-8">
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
      <label htmlFor={id} className="mb-1.5 block text-sm font-medium text-ink">
        {label}
      </label>
      <input
        id={id}
        aria-invalid={error ? true : undefined}
        aria-describedby={describedBy}
        className={`w-full rounded-lg border bg-canvas px-3.5 py-2.5 text-sm text-ink outline-none transition placeholder:text-ink/60 focus:border-brand focus:ring-2 focus:ring-brand/20 ${
          error ? 'border-accent' : 'border-border'
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
  size = 'md',
  className = '',
  disabled,
  children,
  ...props
}: ButtonHTMLAttributes<HTMLButtonElement> & {
  loading?: boolean;
  variant?: 'primary' | 'secondary' | 'accent' | 'ghost' | 'danger';
  size?: 'sm' | 'md';
}) {
  const variants = {
    primary: 'bg-brand text-white hover:bg-brand-dark',
    // Красный — редкий смысловой акцент (например, «Отправить предложение»).
    accent: 'bg-accent text-white hover:bg-accent-dark',
    secondary: 'border border-border bg-canvas text-ink hover:bg-surface',
    ghost: 'text-brand hover:bg-brand-soft',
    danger: 'bg-accent text-white hover:bg-accent-dark',
  }[variant];
  const sizes = {
    sm: 'px-3 py-2 text-xs',
    md: 'px-4 py-2.5 text-sm',
  }[size];
  return (
    <button
      {...props}
      disabled={disabled || loading}
      className={`inline-flex w-full items-center justify-center gap-2 rounded-lg font-semibold transition disabled:cursor-not-allowed disabled:opacity-60 ${variants} ${sizes} ${className}`}
    >
      {loading ? (
        <>
          <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-current/30 border-t-current" />
          Подождите…
        </>
      ) : (
        children
      )}
    </button>
  );
}

export function Alert({
  kind,
  children,
}: {
  kind: 'error' | 'success' | 'info' | 'warning';
  children: ReactNode;
}) {
  const styles = {
    error: 'border-accent/40 bg-accent-soft text-accent-dark',
    success: 'border-success/30 bg-success-soft text-success',
    info: 'border-brand/30 bg-brand-soft text-brand-dark',
    warning: 'border-warning/30 bg-warning-soft text-warning',
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

export function Spinner({ label = 'Загрузка…' }: { label?: string }) {
  return (
    <span role="status" className="inline-flex items-center gap-2 text-sm text-ink/70">
      <span aria-hidden="true" className="h-4 w-4 animate-spin rounded-full border-2 border-brand/30 border-t-brand" />
      {label}
    </span>
  );
}

export function Skeleton({ className = '' }: { className?: string }) {
  return <div aria-hidden="true" className={`animate-pulse rounded-md bg-muted/40 ${className}`} />;
}

export type Tone = 'neutral' | 'brand' | 'success' | 'warning' | 'danger';

const TONE_STYLES: Record<Tone, string> = {
  neutral: 'border-border bg-surface text-ink/70',
  brand: 'border-brand/20 bg-brand-soft text-brand-dark',
  success: 'border-success/20 bg-success-soft text-success',
  warning: 'border-warning/20 bg-warning-soft text-warning',
  danger: 'border-accent/20 bg-accent-soft text-accent-dark',
};

export function Badge({ tone = 'neutral', dot = false, children, className = '' }: { tone?: Tone; dot?: boolean; children: ReactNode; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs font-medium ${TONE_STYLES[tone]} ${className}`}>
      {dot && <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-current" />}
      {children}
    </span>
  );
}

export function Card({ className = '', children }: { className?: string; children: ReactNode }) {
  return <div className={`rounded-2xl border border-border bg-canvas shadow-card ${className}`}>{children}</div>;
}

export function Stat({ label, value, hint }: { label: string; value: ReactNode; hint?: ReactNode }) {
  return (
    <div className="rounded-xl border border-border bg-canvas p-5 shadow-card">
      <span className="block text-xs font-medium text-ink/70">{label}</span>
      <strong className="mt-2 block text-2xl font-bold text-ink">{value}</strong>
      {hint && <span className="mt-1 block text-xs text-ink/70">{hint}</span>}
    </div>
  );
}

export function ProgressBar({ value, max = 100, className = '' }: { value: number; max?: number; className?: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div role="progressbar" aria-valuenow={Math.round(pct)} aria-valuemin={0} aria-valuemax={100} className={`h-2 w-full overflow-hidden rounded-full bg-surface ${className}`}>
      <div className="h-full rounded-full bg-brand transition-all" style={{ width: `${pct}%` }} />
    </div>
  );
}

export function Tag({ children, className = '' }: { children: ReactNode; className?: string }) {
  return <span className={`inline-flex items-center rounded-md border border-border bg-surface px-2.5 py-1 text-xs font-medium text-ink/80 ${className}`}>{children}</span>;
}

export function SectionHeader({ title, description }: { title: string; description?: string }) {
  return (
    <div className="mb-4">
      <h3 className="text-base font-semibold text-ink">{title}</h3>
      {description && <p className="mt-1 text-sm text-ink/60">{description}</p>}
    </div>
  );
}

// Кольцевой индикатор (0..100). Трек и заполнение заданы палитрой; value
// вычисляется из реальных данных, а не из фиктивных метрик.
export function ProgressRing({ value, size = 92, stroke = 8, label }: { value: number; size?: number; stroke?: number; label?: ReactNode }) {
  const pct = Math.min(100, Math.max(0, value));
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const offset = c - (pct / 100) * c;
  return (
    <div className="relative inline-flex shrink-0 items-center justify-center" style={{ width: size, height: size }}>
      <svg width={size} height={size} className="-rotate-90">
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#D9DADB" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="#402FFF" strokeWidth={stroke} strokeLinecap="round" strokeDasharray={c} strokeDashoffset={offset} className="transition-all duration-500" />
      </svg>
      <div className="absolute inset-0 flex flex-col items-center justify-center text-center">
        <span className="text-lg font-bold leading-none text-ink">{Math.round(pct)}%</span>
        {label && <span className="mt-0.5 px-1 text-[10px] leading-tight text-ink/70">{label}</span>}
      </div>
    </div>
  );
}

// Подписанная горизонтальная метрика (0..max), для оценки компонент подбора.
export function MetricBar({ label, value, max = 1, className = '' }: { label: string; value: number; max?: number; className?: string }) {
  const pct = max > 0 ? Math.min(100, Math.max(0, (value / max) * 100)) : 0;
  return (
    <div>
      <div className="mb-1 flex items-baseline justify-between gap-2 text-xs">
        <span className="text-ink/60">{label}</span>
        <span className="font-semibold tabular-nums text-ink">{Math.round(pct)}%</span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-surface">
        <div className={`h-full rounded-full transition-all ${className || 'bg-brand'}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  );
}

// Горизонтальный степпер чекпоинтов: done / current / todo.
export function Stepper({ steps }: { steps: { id: string; label: string; state: 'done' | 'current' | 'todo' }[] }) {
  return (
    <ol className="flex flex-col gap-4 sm:flex-row sm:items-start">
      {steps.map((s, i) => (
        <li key={s.id} className="flex flex-1 items-start gap-3 sm:flex-col sm:items-center sm:gap-2 sm:text-center">
          <div className="relative flex items-center">
            {i > 0 && <span className="absolute right-full top-1/2 hidden h-0.5 w-8 -translate-y-1/2 bg-border sm:block" aria-hidden="true" />}
            <span
              aria-hidden="true"
              className={`flex h-7 w-7 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
                s.state === 'done' ? 'bg-brand text-white' : s.state === 'current' ? 'border-2 border-brand text-brand' : 'border-2 border-border text-ink/55'
              }`}
            >
              {s.state === 'done' ? '✓' : i + 1}
            </span>
          </div>
          <p className={`text-sm font-semibold ${s.state === 'todo' ? 'text-ink/70' : 'text-ink'}`}>{s.label}</p>
        </li>
      ))}
    </ol>
  );
}
