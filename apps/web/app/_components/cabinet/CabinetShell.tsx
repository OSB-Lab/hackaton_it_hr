'use client';
import Link from 'next/link';
import { useState, type ReactNode } from 'react';
import { Logo } from '../ui';
import type { Role } from '../../_lib/api';

export interface SectionDef {
  id: string;
  title: string;
  text: string;
  icon: ReactNode;
}

export function CabinetShell({
  role,
  roleTitle,
  welcome,
  email,
  sections,
  active,
  onLogout,
  children,
}: {
  role: Role;
  roleTitle: string;
  welcome: string;
  email: string;
  sections: SectionDef[];
  active: string;
  onLogout: () => void;
  children: ReactNode;
}) {
  const [open, setOpen] = useState(false);
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[264px_minmax(0,1fr)]">
      {/* Боковая навигация (desktop) */}
      <aside className="sticky top-0 hidden h-screen flex-col border-r border-border bg-canvas lg:flex">
        <div className="border-b border-border px-5 py-5">
          <Logo />
        </div>
        <nav aria-label="Разделы кабинета" className="flex-1 space-y-1 overflow-y-auto p-4">
          {sections.map((s) => (
            <Link
              key={s.id}
              href={`/${role}/${s.id}`}
              title={s.text}
              aria-current={active === s.id ? 'page' : undefined}
              className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium transition ${
                active === s.id ? 'bg-brand text-white' : 'text-ink/70 hover:bg-surface hover:text-ink'
              }`}
            >
              <span className="shrink-0" aria-hidden="true">{s.icon}</span>
              <span>{s.title}</span>
            </Link>
          ))}
        </nav>
        <div className="border-t border-border p-4">
          <p className="truncate text-xs text-ink/70">{email}</p>
          <button type="button" onClick={onLogout} className="mt-2 text-sm font-semibold text-brand hover:underline">
            Выйти
          </button>
        </div>
      </aside>

      <div className="min-w-0">
        {/* Верхняя панель + выдвижное меню (mobile) */}
        <header className="sticky top-0 z-20 border-b border-border bg-canvas/90 backdrop-blur lg:hidden">
          <div className="flex items-center justify-between px-4 py-3">
            <Logo />
            <button
              type="button"
              onClick={() => setOpen((v) => !v)}
              aria-expanded={open}
              aria-label="Открыть меню разделов"
              className="rounded-lg border border-border px-3 py-2 text-sm font-semibold text-ink"
            >
              Меню
            </button>
          </div>
          {open && (
            <div className="border-t border-border px-4 py-4">
              <nav aria-label="Разделы кабинета" className="space-y-1">
                {sections.map((s) => (
                  <Link
                    key={s.id}
                    href={`/${role}/${s.id}`}
                    onClick={() => setOpen(false)}
                    className={`flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm font-medium ${
                      active === s.id ? 'bg-brand text-white' : 'text-ink/70'
                    }`}
                  >
                    <span aria-hidden="true">{s.icon}</span>
                    {s.title}
                  </Link>
                ))}
              </nav>
              <div className="mt-3 flex items-center justify-between border-t border-border pt-3">
                <span className="truncate text-xs text-ink/70">{email}</span>
                <button type="button" onClick={onLogout} className="text-sm font-semibold text-brand">
                  Выйти
                </button>
              </div>
            </div>
          )}
        </header>

        <main className="p-4 sm:p-6 lg:p-8">
          <div className="mx-auto max-w-5xl">
            <h1 className="text-2xl font-bold tracking-tight">{roleTitle}</h1>
            <p className="mt-2 max-w-2xl text-sm leading-relaxed text-ink/60">{welcome}</p>
            <div className="mt-6">{children}</div>
          </div>
        </main>
      </div>
    </div>
  );
}
