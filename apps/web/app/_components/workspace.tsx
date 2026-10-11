'use client';
import { Component, useState, type ErrorInfo, type ReactNode } from 'react';
import { Alert } from './ui';

export type AsyncStatus = 'idle' | 'loading' | 'success' | 'error';

export function useAsync() {
  const [status, setStatus] = useState<AsyncStatus>('idle');
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function run(task: () => Promise<void>, message = '') {
    setStatus('loading'); setError(''); setSuccess('');
    try { await task(); setSuccess(message); setStatus('success'); }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выполнить запрос'); setStatus('error'); }
  }
  function reset() { setStatus('idle'); setError(''); setSuccess(''); }
  const feedback = <div aria-live="polite">{error && <Alert kind="error">{error}</Alert>}{success && <Alert kind="success">{success}</Alert>}</div>;
  return { busy: status === 'loading', status, error, success, run, reset, feedback };
}

// Обратно-совместимая обёртка для существующих компонентов.
export function useAction() {
  const state = useAsync();
  return { busy: state.busy, run: state.run, feedback: state.feedback };
}
export function Panel({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return (
    <section className="workspace-panel">
      <header className="mb-6">
        <h2 className="text-lg font-bold tracking-tight text-ink">{title}</h2>
        {description && <p className="mt-1.5 text-sm leading-relaxed text-ink/60">{description}</p>}
      </header>
      {children}
    </section>
  );
}
export function Select({ label, value, onChange, children, required = false }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode; required?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      <div className="relative">
        <select required={required} className="workspace-input appearance-none pr-9" value={value} onChange={e => onChange(e.target.value)}>{children}</select>
        <span aria-hidden="true" className="pointer-events-none absolute right-3 top-1/2 -translate-y-1/2 text-ink/60">
          <svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M4 6l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" /></svg>
        </span>
      </div>
    </label>
  );
}
export function Textarea({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-sm font-medium text-ink">{label}</span>
      <textarea required={required} className="workspace-input min-h-28" value={value} onChange={e => onChange(e.target.value)} />
    </label>
  );
}
export function Toggle({ label, description, value, onChange }: { label: string; description?: string; value: boolean; onChange: (value: boolean) => void }) {
  return (
    <label className="flex cursor-pointer items-start gap-3 rounded-xl border border-border bg-canvas p-4 transition hover:border-brand/40">
      <input className="mt-0.5 h-5 w-5 shrink-0 accent-brand" type="checkbox" checked={value} onChange={e => onChange(e.target.checked)} />
      <span>
        <span className="block text-sm font-semibold text-ink">{label}</span>
        {description && <span className="mt-1 block text-xs leading-relaxed text-ink/60">{description}</span>}
      </span>
    </label>
  );
}
export function Skills({ label, values, choices, onChange }: { label: string; values: string[]; choices: { id: string; name: string }[]; onChange: (values: string[]) => void }) {
  return (
    <fieldset>
      <legend className="mb-2 text-sm font-medium text-ink">{label}</legend>
      <div className="flex flex-wrap gap-2">
        {choices.map(s => (
          <label key={s.id} className={`cursor-pointer rounded-lg border px-3 py-2 text-xs transition ${values.includes(s.id) ? 'border-brand bg-brand-soft text-brand' : 'border-border bg-canvas text-ink/70 hover:border-brand/40'}`}>
            <input className="mr-2 accent-brand" type="checkbox" checked={values.includes(s.id)} onChange={e => onChange(e.target.checked ? [...values, s.id] : values.filter(v => v !== s.id))} />
            {s.name}
          </label>
        ))}
      </div>
    </fieldset>
  );
}
export function Empty({ title, action, children }: { title?: string; action?: ReactNode; children: ReactNode }) {
  return (
    <div className="rounded-xl border border-dashed border-border bg-canvas/60 p-8 text-sm leading-relaxed text-ink/60">
      {title && <p className="mb-2 font-semibold text-ink/80">{title}</p>}
      {children}
      {action && <div className="mt-4">{action}</div>}
    </div>
  );
}

// Ловит ошибки рендера внутри раздела и не роняет весь кабинет.
export class ErrorBoundary extends Component<{ children: ReactNode; fallback?: ReactNode }, { error: Error | null }> {
  state: { error: Error | null } = { error: null };
  static getDerivedStateFromError(error: Error) { return { error }; }
  componentDidCatch(error: Error, info: ErrorInfo) { console.error(error, info); }
  render() {
    if (this.state.error) {
      return this.props.fallback ?? (
        <div className="rounded-xl border border-accent/40 bg-accent/10 p-6 text-sm leading-relaxed text-accent-dark">
          При отображении раздела произошла ошибка.
          <button type="button" className="ml-2 font-semibold underline" onClick={() => this.setState({ error: null })}>Попробовать снова</button>
        </div>
      );
    }
    return this.props.children;
  }
}
