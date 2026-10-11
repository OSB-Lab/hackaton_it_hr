'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState, type ReactNode } from 'react';
import { ApiError, authApi, cabinetPath, tokenStore, type Role, type User } from '../_lib/api';
import { Alert, Spinner } from './ui';
import { get, type Catalog } from '../_lib/platform';
import { ErrorBoundary } from './workspace';
import { CandidateProfile, Assessment, FspInfo } from './CandidateWorkspace';
import { CompanyProfile, Needs, TalentBank } from './EmployerWorkspace';
import { Invitations } from './InvitationsWorkspace';
import { CabinetShell } from './cabinet/CabinetShell';
import { CandidateDashboard } from './cabinet/CandidateDashboard';
import { EmployerDashboard } from './cabinet/EmployerDashboard';

// Разделы кабинетов с иконками для боковой навигации.
const Svg = ({ children }: { children: ReactNode }) => (
  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" aria-hidden="true">{children}</svg>
);

const SECTIONS: Record<Role, { id: string; title: string; text: string; icon: ReactNode }[]> = {
  candidate: [
    { id: 'dashboard', title: 'Обзор', text: 'Состояние и следующие шаги', icon: <Svg><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></Svg> },
    { id: 'profile', title: 'Профиль', text: 'Редактирование данных', icon: <Svg><circle cx="12" cy="8" r="4" /><path d="M4 21v-1a6 6 0 0 1 6-6h4a6 6 0 0 1 6 6v1" /></Svg> },
    { id: 'assessment', title: 'Тест и квалификация', text: 'Вопросы и результаты', icon: <Svg><rect x="4" y="3" width="16" height="18" rx="2" /><path d="M8 7h8M8 12h5M8 17h3" /></Svg> },
    { id: 'invitations', title: 'Приглашения', text: 'Предложения с зарплатой', icon: <Svg><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></Svg> },
    { id: 'fsp', title: 'Достижения ФСП', text: 'Статус интеграции', icon: <Svg><circle cx="12" cy="9" r="6" /><path d="M9 14l-1.5 6L12 18l4.5 2L15 14" /></Svg> },
  ],
  employer: [
    { id: 'dashboard', title: 'Обзор', text: 'Компания и подбор', icon: <Svg><rect x="3" y="3" width="7" height="7" rx="1.5" /><rect x="14" y="3" width="7" height="7" rx="1.5" /><rect x="3" y="14" width="7" height="7" rx="1.5" /><rect x="14" y="14" width="7" height="7" rx="1.5" /></Svg> },
    { id: 'company', title: 'Компания', text: 'Описание и контакты', icon: <Svg><rect x="4" y="3" width="16" height="18" rx="1" /><path d="M8 7h2M14 7h2M8 11h2M14 11h2M8 15h2M14 15h2" /></Svg> },
    { id: 'needs', title: 'Потребности', text: 'Роли и технические навыки', icon: <Svg><rect x="3" y="7" width="18" height="13" rx="2" /><path d="M9 7V5a2 2 0 0 1 2-2h2a2 2 0 0 1 2 2v2" /></Svg> },
    { id: 'talent', title: 'Банк талантов', text: 'Подборки и объяснения', icon: <Svg><circle cx="9" cy="8" r="3" /><path d="M3 20v-1a5 5 0 0 1 5-5h2a5 5 0 0 1 5 5v1" /><circle cx="17" cy="9" r="2" /><path d="M17 14a4 4 0 0 1 4 4v1" /></Svg> },
    { id: 'invitations', title: 'Приглашения', text: 'Предложения и контакты', icon: <Svg><rect x="3" y="5" width="18" height="14" rx="2" /><path d="M3 7l9 6 9-6" /></Svg> },
  ],
};

const ROLE_TITLE: Record<Role, string> = {
  candidate: 'Кабинет кандидата',
  employer: 'Кабинет работодателя',
};

const WELCOME: Record<Role, string> = {
  candidate: 'Управляйте профилем, проверяйте навыки и выбирайте предложения. DEMO-тест не подтверждает квалификацию.',
  employer: 'Опишите, кого вы ищете, и вы получите подборку кандидатов с объяснением.',
};

export function CabinetStub({ role, section }: { role: Role; section?: string }) {
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<Catalog | null>(null);
  const [catalogError, setCatalogError] = useState('');
  const active = section || SECTIONS[role][0].id;
  async function loadCatalog() {
    setCatalogError('');
    try { setCatalog(await get<Catalog>('/catalog')); }
    catch (e) { setCatalogError(e instanceof Error ? e.message : 'Каталог недоступен'); }
  }
  useEffect(() => { if(user) void loadCatalog(); }, [user]);

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
      <main className="grid min-h-screen place-items-center">
        <Spinner label="Загрузка кабинета…" />
      </main>
    );
  }

  const renderSection = () => {
    if (active === 'invitations') return <Invitations role={role} />;
    if (role === 'candidate' && active === 'fsp') return <FspInfo />;
    if (role === 'employer' && active === 'company') return <CompanyProfile />;
    if (!catalog) {
      return (
        <div className="workspace-panel">
          {catalogError ? (
            <>
              <Alert kind="error">{catalogError}</Alert>
              <button className="mt-4 text-brand underline" onClick={() => void loadCatalog()}>Повторить загрузку каталога</button>
            </>
          ) : (
            <p role="status" className="text-sm text-ink/70">Загрузка справочника…</p>
          )}
        </div>
      );
    }
    if (active === 'dashboard') return role === 'candidate' ? <CandidateDashboard user={user} catalog={catalog} /> : <EmployerDashboard catalog={catalog} />;
    if (role === 'candidate' && active === 'profile') return <CandidateProfile catalog={catalog} />;
    if (role === 'candidate' && active === 'assessment') return <Assessment catalog={catalog} userId={user.id} />;
    if (role === 'employer' && active === 'needs') return <Needs catalog={catalog} />;
    if (role === 'employer' && active === 'talent') return <TalentBank catalog={catalog} userId={user.id} />;
    return <Alert kind="error">Раздел не найден.</Alert>;
  };

  return (
    <CabinetShell
      role={role}
      roleTitle={ROLE_TITLE[role]}
      welcome={WELCOME[role]}
      email={user.email}
      sections={SECTIONS[role]}
      active={active}
      onLogout={logout}
    >
      {!user.is_verified && (
        <div className="mb-6">
          <Alert kind="info">
            Email не подтверждён.{' '}
            <Link href={`/verify-email?email=${encodeURIComponent(user.email)}`} className="font-semibold underline">
              Подтвердить
            </Link>
          </Alert>
        </div>
      )}
      <ErrorBoundary key={active}>{renderSection()}</ErrorBoundary>
    </CabinetShell>
  );
}
