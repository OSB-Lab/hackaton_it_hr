'use client';

import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useEffect, useState } from 'react';
import { ApiError, authApi, cabinetPath, tokenStore, type Role, type User } from '../_lib/api';
import { Alert, Logo } from './ui';
import { get, type Catalog } from '../_lib/platform';
import { CandidateProfile, Assessment, FspInfo } from './CandidateWorkspace';
import { CompanyProfile, Needs, TalentBank } from './EmployerWorkspace';
import { Invitations } from './InvitationsWorkspace';

// Разделы будущих кабинетов (задачи 3.2–3.7). Пока это заглушки, но они показывают,
// как будет устроена навигация, и защищают маршрут по роли.
const SECTIONS: Record<Role, { id: string; title: string; text: string }[]> = {
  candidate: [
    { id: 'profile', title: 'Профиль и согласия', text: 'Данные и приватность' },
    { id: 'assessment', title: 'Тест и квалификация', text: 'Вопросы и результаты' },
    { id: 'invitations', title: 'Приглашения', text: 'Предложения с зарплатой' },
    { id: 'fsp', title: 'Достижения ФСП', text: 'Статус интеграции' },
  ],
  employer: [
    { id: 'company', title: 'Компания', text: 'Описание и контакты' },
    { id: 'needs', title: 'Потребности', text: 'Роли и технические навыки' },
    { id: 'talent', title: 'Банк талантов', text: 'Подборки и объяснения' },
    { id: 'invitations', title: 'Приглашения', text: 'Предложения и контакты' },
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
      <main className="grid min-h-screen place-items-center text-sm text-ink/70">Загрузка…</main>
    );
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-ink bg-white">
        <div className="mx-auto flex max-w-7xl items-center justify-between gap-4 px-5 py-4">
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

      <main className="mx-auto max-w-7xl px-5 py-8 sm:py-10">
        <h1 className="text-2xl font-bold sm:text-3xl">{ROLE_TITLE[role]}</h1>
        <p className="mt-3 max-w-xl text-sm leading-relaxed text-ink/75">{WELCOME[role]}</p>

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

        <div className="mt-8 grid items-start gap-6 lg:grid-cols-[240px_minmax(0,1fr)]"><nav aria-label="Разделы кабинета" className="grid grid-cols-2 gap-2 lg:sticky lg:top-5 lg:grid-cols-1">
          {SECTIONS[role].map((section) => (
            <Link
              key={section.title}
              href={`/${role}/${section.id}`}
              aria-current={active===section.id?'page':undefined}
              className={`rounded-xl border p-4 transition ${active===section.id?'border-brand bg-brand text-white shadow-sm':'border-muted/50 bg-white hover:border-brand'}`}
            >
              <div>
                <h2 className="font-bold">{section.title}</h2>
                <p className="mt-1 text-xs leading-relaxed opacity-70">{section.text}</p>
              </div>
            </Link>
          ))}
        </nav><div className="min-w-0">
          {active==='invitations' ? <Invitations role={role}/> : role==='candidate'&&active==='fsp' ? <FspInfo/> : role==='employer'&&active==='company' ? <CompanyProfile/> : !catalog ? <div className="workspace-panel">{catalogError?<><Alert kind="error">{catalogError}</Alert><button className="mt-4 text-brand underline" onClick={()=>void loadCatalog()}>Повторить загрузку каталога</button></>:<p role="status">Загрузка справочника…</p>}</div> : role==='candidate'&&active==='profile' ? <CandidateProfile catalog={catalog}/> : role==='candidate'&&active==='assessment' ? <Assessment catalog={catalog} userId={user.id}/> : role==='employer'&&active==='needs' ? <Needs catalog={catalog}/> : role==='employer'&&active==='talent' ? <TalentBank catalog={catalog} userId={user.id}/> : <Alert kind="error">Раздел не найден.</Alert>}
        </div></div>
      </main>
    </div>
  );
}
