'use client';
import { useEffect, useState } from 'react';
import { Button, Field, Alert } from './ui';
import { Panel, Select, Toggle, Skills, Empty, useAction } from './workspace';
import { get, send, downloadPdf, recalled, remember, type Profile, type Catalog, type Attempt, type Result } from '../_lib/platform';

export function CandidateProfile({ catalog }: { catalog: Catalog }) {
  const [profile, setProfile] = useState<Profile | null>(null);
  const [soft, setSoft] = useState('');
  const action = useAction();
  async function load() { const p = await get<Profile>('/me/candidate-profile'); setProfile(p); setSoft(p.softSkills.join(', ')); }
  useEffect(() => { void action.run(load); }, []);
  function update<K extends keyof Profile>(key: K, value: Profile[K]) { setProfile(p => p && ({ ...p, [key]: value })); }
  if (!profile) return <Panel title="Профиль кандидата">{action.feedback}<Button variant="secondary" loading={action.busy} onClick={() => void action.run(load)}>Загрузить профиль</Button></Panel>;
  return <div className="space-y-5"><Panel title="Ваш профессиональный профиль" description="Расскажите о себе. Квалификация подтверждается отдельно — результатом одобренного теста.">
    <div className="mb-6 flex flex-wrap gap-2"><span className="workspace-badge">{profile.verifiedGrade ? `${profile.verifiedSpecialization} · ${profile.verifiedGrade}` : 'Квалификация не подтверждена'}</span><span className="workspace-badge">{profile.eligibleForEmployerSearch ? 'Доступен для подбора' : 'Пока не участвует в подборе'}</span></div>
    {action.feedback}
    <form className="mt-5 space-y-6" onSubmit={e => { e.preventDefault(); void action.run(async () => {
      const p = await send<Profile>('/me/candidate-profile', {
        fullName: profile.fullName, phone: profile.phone, role: profile.role, experienceMonths: profile.experienceMonths,
        specialization: profile.specialization, stack: profile.stack,
        softSkills: soft.split(',').map(s => s.trim()).filter(Boolean), selfDeclaredGrade: profile.selfDeclaredGrade,
        consents: profile.consents, privacy: profile.privacy,
      }, 'PATCH'); setProfile(p);
    }, 'Профиль и настройки сохранены.'); }}>
      <div className="workspace-grid"><Field id="profile-name" label="Имя и фамилия" maxLength={200} value={profile.fullName || ''} onChange={e => update('fullName', e.target.value)} />
        <Field id="profile-email" label="Email (только чтение)" value={profile.email} readOnly />
        <Field id="profile-phone" label="Телефон" type="tel" maxLength={50} value={profile.phone || ''} onChange={e => update('phone', e.target.value || null)} />
        <Field id="profile-role" label="Профессиональная роль" maxLength={200} value={profile.role || ''} onChange={e => update('role', e.target.value)} />
        <Select label="Специализация" value={profile.specialization || ''} onChange={v => update('specialization', v || null)}><option value="">Не выбрана</option>{catalog.specializations.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</Select>
        <Field id="profile-experience" label="Опыт, месяцев" type="number" min={0} step={1} value={profile.experienceMonths ?? ''} onChange={e => update('experienceMonths', e.target.value === '' ? null : Number(e.target.value))} />
        <Select label="Самооценка уровня (не подтверждение)" value={profile.selfDeclaredGrade || ''} onChange={v => update('selfDeclaredGrade', v || null)}><option value="">Не указан</option>{catalog.grades.map(g => <option key={g.id} value={g.id}>{g.name}</option>)}</Select>
        <Field id="profile-soft" label="Soft skills, через запятую" value={soft} onChange={e => setSoft(e.target.value)} /></div>
      <Skills label="Навыки" choices={catalog.skills.filter(s => s.id !== 'teamwork')} values={profile.stack} onChange={v => update('stack', v)} />
      {profile.stack.filter(v => !catalog.skills.some(s => s.id === v)).map(v => <button type="button" className="workspace-badge mr-2" key={v} onClick={() => update('stack', profile.stack.filter(s => s !== v))}>{v} ×</button>)}
      <div className="space-y-3"><h3 className="font-bold">Согласия и приватность</h3>
        <Toggle label="Обработка персональных данных" value={profile.consents.processing} onChange={v => update('consents', { ...profile.consents, processing: v })} />
        <Toggle label="Публикация профиля" description="Отдельное согласие на участие в подборе работодателей. Также нужны подтверждённые email и квалификация." value={profile.consents.publication} onChange={v => update('consents', { ...profile.consents, publication: v })} />
        <Toggle label="Разрешить раскрытие контактов" description="Только компании, приглашение которой вы приняли, при действующих согласиях. Отзыв разрешения скрывает контакты в последующих запросах." value={profile.privacy.showContacts} onChange={v => update('privacy', { showContacts: v })} /></div>
      <Button loading={action.busy} type="submit">Сохранить профиль и согласия</Button>
    </form></Panel><Panel title="PDF-профиль" description="Имя, специализация и навыки. Email и телефон в экспорт не включаются."><Button variant="secondary" loading={action.busy} onClick={() => void action.run(downloadPdf)}>Скачать PDF</Button></Panel></div>;
}

export function Assessment({ catalog, userId }: { catalog: Catalog; userId: number }) {
  const [test, setTest] = useState('0');
  const [attempt, setAttempt] = useState<Attempt | null>(null);
  const [answers, setAnswers] = useState<Record<string, string>>({});
  const [result, setResult] = useState<Result | null>(null);
  const [attemptId, setAttemptId] = useState('');
  const [confirm, setConfirm] = useState(false);
  const action = useAction();
  const key = `fsp_attempt_${userId}`;
  async function open(id: string) {
    if (!/^\d+$/.test(id) || Number(id) < 1) throw new Error('Укажите номер попытки.');
    const a = await get<Attempt>(`/assessments/${id}`); setAttempt(a); setAnswers({}); setResult(null); setConfirm(false); setAttemptId(String(a.id)); remember(key, String(a.id));
    if (a.status === 'submitted') { const saved = await send<{ result: Result }>(`/assessments/${a.id}/submit`, { answers: [] }); setResult(saved.result); }
  }
  useEffect(() => { const id = recalled(key); if (id) { setAttemptId(id); void action.run(() => open(id)); } }, [key]);
  const answered = Object.values(answers).filter(Boolean).length;
  return <div className="space-y-5"><Panel title="Тест и квалификация" description="Одна активная попытка. Вариант выбирает сервер; после отправки ответы изменить нельзя.">
    {action.feedback}
    {!attempt && <><form className="mt-4 space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => {
      const t = catalog.tests[Number(test)]; if (!t) throw new Error('Нет доступного теста.');
      const a = await send<Attempt>('/assessments/start', { specialization: t.specialization, grade: t.grade }, 'POST', {409:'Нельзя начать попытку: сохраните профиль, проверьте текущую попытку или срок повторного теста.'});
      setAttempt(a); setResult(null); setAnswers({}); setAttemptId(String(a.id)); remember(key, String(a.id));
    }); }}><Select required label="Доступный тест" value={test} onChange={setTest}>{catalog.tests.map((t, i) => <option key={i} value={i}>{t.specialization} · {t.grade} · {t.status}</option>)}</Select><Alert kind="info">DEMO-тест показывает результат, но не подтверждает квалификацию и не открывает участие в подборе.</Alert><Button type="submit" loading={action.busy} disabled={!catalog.tests.length}>Начать / продолжить тест</Button></form>
      <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void action.run(() => open(attemptId)); }}><Field id="attempt-id" type="number" min={1} required label="Вернуться по номеру попытки" value={attemptId} onChange={e => setAttemptId(e.target.value)} /><Button className="!w-auto" type="submit" variant="secondary" loading={action.busy}>Открыть</Button></form></>}
    {attempt && <div className="mt-4"><div className="mb-4 flex flex-wrap gap-2"><span className="workspace-badge">Попытка №{attempt.id}</span><span className="workspace-badge">{attempt.assessment.status}</span><span className="workspace-badge">Вариант {attempt.assessment.variant}</span></div>
      {attempt.status === 'active' && <><div className="mb-6"><p className="mb-2 text-sm">Ответов: {answered} / {attempt.assessment.questions.length}</p><progress className="h-2 w-full accent-brand" value={answered} max={attempt.assessment.questions.length} /></div>
        <form onSubmit={e => { e.preventDefault(); setConfirm(true); }} className="space-y-5">
          {attempt.assessment.questions.map((q, index) => <fieldset disabled={action.busy} key={q.id} className="rounded-xl border border-muted/60 bg-white p-4 sm:p-6"><legend className="px-2 text-xs font-semibold text-brand">Вопрос {index + 1}</legend><p className="mb-4 whitespace-pre-wrap text-sm font-semibold leading-relaxed">{q.prompt}</p><div className="space-y-2">{q.options.map(o => <label key={o.id} className={`flex cursor-pointer gap-3 rounded-lg border p-3 text-sm ${answers[q.id] === o.id ? 'border-brand bg-brand-soft' : 'border-muted/50'}`}><input className="mt-1 accent-brand" type="radio" name={q.id} value={o.id} checked={answers[q.id] === o.id} onChange={() => { setAnswers(prev => ({...prev,[q.id]:o.id})); setConfirm(false); }} /><span className="whitespace-pre-wrap">{o.text}</span></label>)}</div></fieldset>)}
          {!confirm ? <Button type="submit" loading={action.busy}>Завершить тест</Button> : <div className="space-y-3"><Alert kind="info">Отправить ответы? Без ответа: {attempt.assessment.questions.length - answered}. После отправки изменения невозможны.</Alert><Button type="button" loading={action.busy} onClick={() => void action.run(async () => {
            const data = await send<{result:Result}>(`/assessments/${attempt.id}/submit`, {answers:attempt.assessment.questions.map(q => ({questionId:q.id,optionId:answers[q.id] || null}))});
            setResult(data.result); setAttempt({...attempt,status:'submitted'}); setConfirm(false);
          })}>Подтвердить отправку</Button><Button type="button" variant="secondary" onClick={() => setConfirm(false)}>Вернуться к ответам</Button></div>}
        </form></>}
      {attempt.status === 'submitted' && !result && <Button loading={action.busy} onClick={() => void action.run(() => open(String(attempt.id)))}>Получить сохранённый результат</Button>}
      {result && <div className="space-y-4"><h3 className="text-2xl font-bold">{{fail:'Порог не пройден',pass:'Тест пройден',high:'Высокий результат'}[result.outcome]}</h3><div className="workspace-grid"><div className="workspace-stat"><span>Технический результат</span><strong>{(result.technicalTotal ?? 0).toFixed(1)}%</strong></div><div className="workspace-stat"><span>Teamwork · диагностика</span><strong>{(result.teamworkSubscore ?? 0).toFixed(1)}%</strong></div></div>
        <Alert kind="info">{result.status === 'DEMO' ? 'Результат DEMO. Эта попытка не подтверждает квалификацию.' : result.verifiedGrade ? `Подтверждённая квалификация: ${result.verifiedSpecialization} · ${result.verifiedGrade}` : 'Квалификация не подтверждена.'}</Alert>
        {result.retestAvailableAt && <p className="text-sm">Повторное тестирование: {new Date(result.retestAvailableAt).toLocaleString('ru-RU')}</p>}{result.retestTargetGrade && <p className="text-sm">Предлагаемый следующий уровень: {result.retestTargetGrade}. Доступность проверит сервер.</p>}
        <Button variant="secondary" onClick={() => {setAttempt(null);setResult(null);}}>К выбору теста</Button></div>}
    </div>}
  </Panel></div>;
}

export function FspInfo() { return <Panel title="Достижения ФСП"><Empty>Подключение подтверждённой истории соревнований пока не доступно через API. Мы не выдаём demo-достижения за подтверждённые. Отсутствие истории ФСП не мешает пройти тестирование и участвовать в подборе при выполнении остальных условий.</Empty></Panel>; }
