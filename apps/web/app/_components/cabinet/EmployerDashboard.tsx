'use client';
import Link from 'next/link';
import { useEffect, useState } from 'react';
import { ApiError } from '../../_lib/api';
import { get, type Catalog, type Company, type Invitation, type Need } from '../../_lib/platform';
import { Badge, SectionHeader } from '../ui';
import { useAction } from '../workspace';

const STATUS: Record<Invitation['status'], string> = { sent: 'Отправлено', viewed: 'Просмотрено', accepted: 'Принято', declined: 'Отклонено' };
const STATUS_TONE: Record<Invitation['status'], 'brand' | 'neutral' | 'success' | 'warning'> = { sent: 'brand', viewed: 'neutral', accepted: 'success', declined: 'warning' };

export function EmployerDashboard({ catalog }: { catalog: Catalog }) {
  const [company, setCompany] = useState<Company | null>(null);
  const [needs, setNeeds] = useState<Need[] | null>(null);
  const [invites, setInvites] = useState<Invitation[] | null>(null);
  const action = useAction();
  async function load() {
    let c: Company | null = null;
    try { c = await get<Company>('/employer/company'); } catch (e) { if (!(e instanceof ApiError && e.status === 404)) throw e; }
    const [n, inv] = await Promise.all([get<Need[]>('/employer/needs'), get<Invitation[]>('/invitations')]);
    setCompany(c);
    setNeeds(n);
    setInvites(inv);
  }
  useEffect(() => { void action.run(load); }, []);

  if (!needs || !invites) {
    return (
      <div className="workspace-panel">
        {action.feedback}
        <button onClick={() => void action.run(load)} className="text-sm font-semibold text-brand hover:underline">Загрузить обзор</button>
      </div>
    );
  }

  const specName = (id: string | null) => catalog.specializations.find((s) => s.id === id)?.name ?? id;
  const gradeName = (id: string | null) => catalog.grades.find((g) => g.id === id)?.name ?? id;
  const totalInvites = invites.length;
  const accepted = invites.filter((i) => i.status === 'accepted').length;

  return (
    <div className="space-y-6">
      <section className="workspace-panel">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-start sm:justify-between">
          <div className="min-w-0">
            <h2 className="text-lg font-bold">{company?.name || 'Компания не заполнена'}</h2>
            {company?.description
              ? <p className="mt-1 line-clamp-2 text-sm text-ink/60">{company.description}</p>
              : <p className="mt-1 text-sm text-ink/60">Добавьте название, описание и контакты компании.</p>}
          </div>
          <Link href="/employer/company" className="shrink-0 text-sm font-semibold text-brand hover:underline">{company ? 'Редактировать' : 'Заполнить компанию'} →</Link>
        </div>
      </section>

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="workspace-panel !p-5"><span className="text-xs text-ink/70">Потребности</span><p className="mt-1 text-2xl font-bold tabular-nums">{needs.length}</p></div>
        <div className="workspace-panel !p-5"><span className="text-xs text-ink/70">Отправленные предложения</span><p className="mt-1 text-2xl font-bold tabular-nums">{totalInvites}</p></div>
        <div className="workspace-panel !p-5"><span className="text-xs text-ink/70">Принятые приглашения</span><p className="mt-1 text-2xl font-bold tabular-nums">{accepted}</p></div>
      </div>

      <section className="workspace-panel">
        <SectionHeader title="Потребности" description="Роли, которые вы ищете. Подборку кандидатов можно создать прямо из банка талантов." />
        {needs.length === 0 ? (
          <div className="rounded-xl border border-dashed border-border p-8 text-center text-sm text-ink/60">
            Потребностей пока нет.<br />
            <Link href="/employer/needs" className="mt-2 inline-block font-semibold text-brand hover:underline">Создать потребность →</Link>
          </div>
        ) : (
          <ul className="space-y-3">
            {needs.map((n) => (
              <li key={n.id} className="flex flex-col gap-3 rounded-xl border border-border p-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="font-semibold">{n.title || `Потребность №${n.id}`}</p>
                  <div className="mt-1.5 flex flex-wrap items-center gap-2 text-xs text-ink/60">
                    {n.specialization && <Badge tone="brand">{specName(n.specialization)}</Badge>}
                    {n.minGrade && n.targetGrade && <span>{gradeName(n.minGrade)} → {gradeName(n.targetGrade)}</span>}
                    {n.requiredSkills.length > 0 && <span>{n.requiredSkills.length} навыков</span>}
                  </div>
                </div>
                <Link href="/employer/talent" className="shrink-0 text-sm font-semibold text-brand hover:underline">Подобрать кандидатов →</Link>
              </li>
            ))}
          </ul>
        )}
      </section>

      <section className="workspace-panel">
        <SectionHeader title="Приглашения" description="Предложения кандидатам и их статус." />
        {invites.length === 0 ? (
          <p className="text-sm text-ink/60">Приглашений пока нет. Они создаются из карточки кандидата в банке талантов.</p>
        ) : (
          <ul className="divide-y divide-border">
            {invites.slice(0, 5).map((i) => (
              <li key={i.id} className="flex flex-wrap items-center justify-between gap-3 py-3 text-sm">
                <span className="truncate">Кандидат №{i.candidateId}</span>
                <span className="tabular-nums text-ink/60">{i.salaryMin} — {i.salaryMax} {i.currency}</span>
                <Badge tone={STATUS_TONE[i.status]}>{STATUS[i.status]}</Badge>
              </li>
            ))}
          </ul>
        )}
      </section>
    </div>
  );
}
