'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import type { User } from '../../_lib/api';
import { get, type Catalog, type Invitation, type Profile } from '../../_lib/platform';
import { Badge, ProgressRing, SectionHeader, Stepper } from '../ui';
import { useAction } from '../workspace';

// Поля, из которых честно считается «Заполненность профиля».
const PROFILE_FIELDS = ['fullName', 'phone', 'role', 'experienceMonths', 'specialization', 'selfDeclaredGrade', 'stack', 'softSkills'] as const;

function completeness(p: Profile): number {
  const filled = PROFILE_FIELDS.filter((k) => {
    const v = p[k];
    return Array.isArray(v) ? v.length > 0 : v !== null && v !== '';
  }).length;
  return Math.round((filled / PROFILE_FIELDS.length) * 100);
}

export function CandidateDashboard({ user, catalog }: { user: User; catalog: Catalog }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [invites, setInvites] = useState<Invitation[] | null>(null);
  const action = useAction();
  async function load() {
    const [p, inv] = await Promise.all([get<Profile>('/me/candidate-profile'), get<Invitation[]>('/invitations')]);
    setProfile(p);
    setInvites(inv);
  }
  useEffect(() => { void action.run(load); }, []);

  if (!profile) {
    return (
      <div className="workspace-panel">
        {action.feedback}
        <button onClick={() => void action.run(load)} className="text-sm font-semibold text-brand hover:underline">Загрузить обзор</button>
      </div>
    );
  }

  const done = completeness(profile);
  const checks = [
    { label: 'Профиль', done: done === 100 },
    { label: 'Email', done: user.is_verified },
    { label: 'Квалификация', done: !!profile.verifiedGrade },
    { label: 'Согласие на публикацию', done: profile.consents.publication },
  ];
  let currentFound = false;
  const steps = checks.map((c) => {
    let state: 'done' | 'current' | 'todo';
    if (c.done) state = 'done';
    else if (!currentFound) { currentFound = true; state = 'current'; }
    else state = 'todo';
    return { id: c.label, label: c.label, state };
  });

  const activeInvites = invites?.filter((i) => i.status === 'sent' || i.status === 'viewed').length ?? 0;
  const specName = (id: string | null) => catalog.specializations.find((s) => s.id === id)?.name ?? id;
  const gradeName = (id: string | null) => catalog.grades.find((g) => g.id === id)?.name ?? id;

  const nextActions = [
    { href: '/verify-email', title: 'Подтвердить email', done: user.is_verified },
    { href: '/candidate/profile', title: 'Заполнить профиль', done: done === 100 },
    { href: '/candidate/assessment', title: 'Пройти тест', done: !!profile.verifiedGrade },
    { href: '/candidate/profile', title: 'Включить согласие на публикацию', done: profile.consents.publication },
  ];

  return (
    <div className="space-y-6">
      <section className="workspace-panel">
        <SectionHeader title="Путь к подбору" description="Эти условия нужны для участия в подборе. Итоговая доступность для подбора — отдельный показатель в «Сводке»." />
        <Stepper steps={steps} />
        <p className="mt-4 text-xs leading-relaxed text-ink/70">Включённое согласие на публикацию — только одно из условий. Фактический допуск к подбору зависит от подтверждённых email и квалификации и показан в «Сводке».</p>
      </section>

      <div className="grid gap-6 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div className="space-y-6">
          <section className="workspace-panel">
            <div className="flex flex-col gap-5 sm:flex-row sm:items-center">
              <div className="flex flex-col items-center gap-2">
                <ProgressRing value={done} />
                <span className="text-xs text-ink/70">Заполненность профиля</span>
              </div>
              <div className="min-w-0">
                <h2 className="text-lg font-bold">{profile.fullName || 'Профиль кандидата'}</h2>
                <p className="mt-1 truncate text-sm text-ink/60">{profile.email}</p>
                <div className="mt-3 flex flex-wrap gap-2">
                  {profile.specialization && <Badge tone="brand">{specName(profile.specialization)}</Badge>}
                  {profile.selfDeclaredGrade && <Badge>{gradeName(profile.selfDeclaredGrade)} · самооценка</Badge>}
                  {profile.role && <Badge>{profile.role}</Badge>}
                </div>
              </div>
            </div>
            <div className="mt-4 border-t border-border pt-4">
              <Link href="/candidate/profile" className="text-sm font-semibold text-brand hover:underline">Редактировать профиль →</Link>
            </div>
          </section>

          <section className="workspace-panel">
            <SectionHeader title="Квалификация" />
            {profile.verifiedGrade ? (
              <div className="flex flex-wrap items-center gap-3">
                <Badge tone="success" dot>{specName(profile.verifiedSpecialization)} · {gradeName(profile.verifiedGrade)}</Badge>
                <Link href="/candidate/assessment" className="text-sm font-semibold text-brand hover:underline">Результаты теста →</Link>
              </div>
            ) : (
              <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <p className="text-sm text-ink/70">Квалификация пока не подтверждена. Её определяет тест, а не резюме.</p>
                <Link href="/candidate/assessment" className="shrink-0 text-sm font-semibold text-brand hover:underline">Пройти тест →</Link>
              </div>
            )}
          </section>
        </div>

        <div className="space-y-6">
          <section className="workspace-panel">
            <SectionHeader title="Следующие действия" />
            <ul className="space-y-2.5">
              {nextActions.map((a) => (
                <li key={a.title}>
                  {a.done ? (
                    <span className="flex items-center gap-2 text-sm text-ink/70"><span aria-hidden="true" className="text-success">✓</span>{a.title}</span>
                  ) : (
                    <Link href={a.href} className="flex items-center gap-2 text-sm font-medium text-brand hover:underline"><span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-accent" />{a.title}</Link>
                  )}
                </li>
              ))}
            </ul>
          </section>

          <section className="workspace-panel">
            <SectionHeader title="Сводка" />
            <dl className="space-y-3 text-sm">
              <div className="flex items-center justify-between gap-3"><dt className="text-ink/60">Доступен для подбора</dt><dd><Badge tone={profile.eligibleForEmployerSearch ? 'success' : 'warning'} dot>{profile.eligibleForEmployerSearch ? 'Да' : 'Нет'}</Badge></dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="text-ink/60">Активные приглашения</dt><dd className="font-semibold tabular-nums">{activeInvites}</dd></div>
              <div className="flex items-center justify-between gap-3"><dt className="text-ink/60">Публикация профиля</dt><dd><Badge tone={profile.consents.publication ? 'success' : 'neutral'}>{profile.consents.publication ? 'Вкл.' : 'Выкл.'}</Badge></dd></div>
            </dl>
          </section>
        </div>
      </div>
    </div>
  );
}
