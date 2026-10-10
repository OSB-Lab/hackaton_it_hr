'use client';
import { useState, type ReactNode } from 'react';
import { Alert } from './ui';

export function useAction() {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  async function run(task: () => Promise<void>, message = '') {
    setBusy(true); setError(''); setSuccess('');
    try { await task(); setSuccess(message); }
    catch (e) { setError(e instanceof Error ? e.message : 'Не удалось выполнить запрос'); }
    finally { setBusy(false); }
  }
  const feedback = <div aria-live="polite">{error && <Alert kind="error">{error}</Alert>}{success && <Alert kind="success">{success}</Alert>}</div>;
  return { busy, run, feedback };
}
export function Panel({ title, description, children }: { title: string; description?: string; children: ReactNode }) {
  return <section className="workspace-panel"><header className="mb-6"><h2 className="text-xl font-bold tracking-tight">{title}</h2>{description && <p className="mt-2 text-sm leading-relaxed text-ink/65">{description}</p>}</header>{children}</section>;
}
export function Select({ label, value, onChange, children, required = false }: { label: string; value: string; onChange: (value: string) => void; children: ReactNode; required?: boolean }) {
  return <label className="block text-sm font-medium">{label}<select required={required} className="workspace-input mt-1.5" value={value} onChange={e => onChange(e.target.value)}>{children}</select></label>;
}
export function Textarea({ label, value, onChange, required = false }: { label: string; value: string; onChange: (value: string) => void; required?: boolean }) {
  return <label className="block text-sm font-medium">{label}<textarea required={required} className="workspace-input mt-1.5 min-h-28" value={value} onChange={e => onChange(e.target.value)} /></label>;
}
export function Toggle({ label, description, value, onChange }: { label: string; description?: string; value: boolean; onChange: (value: boolean) => void }) {
  return <label className="flex cursor-pointer items-start gap-3 rounded-lg border border-muted/60 p-4"><input className="mt-1 h-5 w-5 accent-brand" type="checkbox" checked={value} onChange={e => onChange(e.target.checked)} /><span><span className="block text-sm font-semibold">{label}</span>{description && <span className="mt-1 block text-xs leading-relaxed text-ink/65">{description}</span>}</span></label>;
}
export function Skills({ label, values, choices, onChange }: { label: string; values: string[]; choices: { id: string; name: string }[]; onChange: (values: string[]) => void }) {
  return <fieldset><legend className="mb-2 text-sm font-medium">{label}</legend><div className="flex flex-wrap gap-2">{choices.map(s => <label key={s.id} className={`cursor-pointer rounded-md border px-3 py-2 text-xs ${values.includes(s.id) ? 'border-brand bg-brand-soft text-brand' : 'border-muted bg-white'}`}><input className="mr-2 accent-brand" type="checkbox" checked={values.includes(s.id)} onChange={e => onChange(e.target.checked ? [...values, s.id] : values.filter(v => v !== s.id))} />{s.name}</label>)}</div></fieldset>;
}
export function Empty({ children }: { children: ReactNode }) { return <div className="rounded-xl border border-dashed border-muted bg-surface/40 p-8 text-sm leading-relaxed text-ink/65">{children}</div>; }
