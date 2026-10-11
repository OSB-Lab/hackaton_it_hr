'use client';
import { useEffect, useState } from 'react';
import { Badge, Button, Field, Alert, ProgressBar } from './ui';
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
    <div className="mb-6 flex flex-wrap gap-2">
      <Badge tone={profile.verifiedGrade ? 'success' : 'neutral'} dot>{profile.verifiedGrade ? `${profile.verifiedSpecialization} · ${profile.verifiedGrade}` : 'Квалификация не подтверждена'}</Badge>
      <Badge tone={profile.eligibleForEmployerSearch ? 'success' : 'warning'} dot>{profile.eligibleForEmployerSearch ? 'Доступен для подбора' : 'Пока не участвует в подборе'}</Badge>
    </div>
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
  const [current, setCurrent] = useState(0);
  const action = useAction();
  const key = `fsp_attempt_${userId}`;
  async function open(id: string) {
    if (!/^\d+$/.test(id) || Number(id) < 1) throw new Error('Укажите номер попытки.');
    const a = await get<Attempt>(`/assessments/${id}`); setAttempt(a); setAnswers({}); setResult(null); setConfirm(false); setCurrent(0); setAttemptId(String(a.id)); remember(key, String(a.id));
    if (a.status === 'submitted') { const saved = await send<{ result: Result }>(`/assessments/${a.id}/submit`, { answers: [] }); setResult(saved.result); }
  }
  useEffect(() => { const id = recalled(key); if (id) { setAttemptId(id); void action.run(() => open(id)); } }, [key]);
  const answered = Object.values(answers).filter(Boolean).length;
  return <div className="space-y-5"><Panel title="Тест и квалификация" description="Одна активная попытка. Вариант выбирает сервер; после отправки ответы изменить нельзя.">
    {action.feedback}
    {!attempt && <><form className="mt-4 space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => {
      const t = catalog.tests[Number(test)]; if (!t) throw new Error('Нет доступного теста.');
      const a = await send<Attempt>('/assessments/start', { specialization: t.specialization, grade: t.grade }, 'POST', {409:'Нельзя начать попытку: сохраните профиль, проверьте текущую попытку или срок повторного теста.'});
      setAttempt(a); setResult(null); setAnswers({}); setCurrent(0); setAttemptId(String(a.id)); remember(key, String(a.id));
    }); }}><Select required label="Доступный тест" value={test} onChange={setTest}>{catalog.tests.map((t, i) => <option key={i} value={i}>{t.specialization} · {t.grade} · {t.status}</option>)}</Select><Alert kind="info">DEMO-тест показывает результат, но не подтверждает квалификацию и не открывает участие в подборе.</Alert><Button type="submit" loading={action.busy} disabled={!catalog.tests.length}>Начать / продолжить тест</Button></form>
      <form className="mt-6 flex flex-wrap items-end gap-3" onSubmit={e => { e.preventDefault(); void action.run(() => open(attemptId)); }}><Field id="attempt-id" type="number" min={1} required label="Вернуться по номеру попытки" value={attemptId} onChange={e => setAttemptId(e.target.value)} /><Button className="!w-auto" type="submit" variant="secondary" loading={action.busy}>Открыть</Button></form></>}
    {attempt && <div className="mt-4"><div className="mb-4 flex flex-wrap gap-2"><span className="workspace-badge">Попытка №{attempt.id}</span><span className="workspace-badge">{attempt.assessment.status}</span><span className="workspace-badge">Вариант {attempt.assessment.variant}</span></div>
      {attempt.status === 'active' && <><div className="mb-5"><div className="mb-1.5 flex items-center justify-between text-sm"><span className="text-ink/60">Отвечено {answered} из {attempt.assessment.questions.length}</span><span className="font-semibold tabular-nums">{attempt.assessment.questions.length ? Math.round((answered / attempt.assessment.questions.length) * 100) : 0}%</span></div><ProgressBar value={answered} max={attempt.assessment.questions.length} /><div className="mt-4 flex flex-wrap gap-2">{attempt.assessment.questions.map((q, index) => <button key={q.id} type="button" onClick={() => { setCurrent(index); setConfirm(false); }} aria-label={`Вопрос ${index + 1}`} className={`h-8 w-8 rounded-lg border text-xs font-semibold transition ${index === current ? 'border-brand bg-brand text-white' : answers[q.id] ? 'border-brand/40 bg-brand-soft text-brand' : 'border-border text-ink/70 hover:border-brand/40'}`}>{index + 1}</button>)}</div></div>
        {(() => { const q = attempt.assessment.questions[current]; return <fieldset disabled={action.busy} className="rounded-xl border border-border bg-canvas p-5 sm:p-6"><legend className="px-2 text-xs font-semibold text-brand">Вопрос {current + 1} из {attempt.assessment.questions.length}</legend><p className="mb-5 whitespace-pre-wrap text-base font-semibold leading-relaxed">{q.prompt}</p><div className="space-y-2">{q.options.map(o => <label key={o.id} className={`flex cursor-pointer gap-3 rounded-lg border p-3 text-sm transition ${answers[q.id] === o.id ? 'border-brand bg-brand-soft' : 'border-border hover:border-brand/40'}`}><input className="mt-0.5 accent-brand" type="radio" name={q.id} value={o.id} checked={answers[q.id] === o.id} onChange={() => { setAnswers(prev => ({...prev,[q.id]:o.id})); setConfirm(false); }} /><span className="whitespace-pre-wrap">{o.text}</span></label>)}</div></fieldset>; })()}
        <div className="mt-5 flex flex-wrap items-center justify-between gap-3"><div className="flex gap-2"><Button className="!w-auto" variant="secondary" size="sm" disabled={current === 0} onClick={() => setCurrent(c => Math.max(0, c - 1))}>← Назад</Button><Button className="!w-auto" variant="secondary" size="sm" disabled={current === attempt.assessment.questions.length - 1} onClick={() => setCurrent(c => Math.min(attempt.assessment.questions.length - 1, c + 1))}>Далее →</Button></div><Button className="!w-auto" onClick={() => setConfirm(true)}>Завершить тест</Button></div>
        {confirm && <div className="mt-4 space-y-3 rounded-xl border border-border bg-canvas p-5"><Alert kind="info">Отправить ответы? Без ответа: {attempt.assessment.questions.length - answered}. После отправки изменения невозможны.</Alert><div className="flex flex-wrap gap-3"><Button className="!w-auto" type="button" loading={action.busy} onClick={() => void action.run(async () => {
            const data = await send<{result:Result}>(`/assessments/${attempt.id}/submit`, {answers:attempt.assessment.questions.map(q => ({questionId:q.id,optionId:answers[q.id] || null}))});
            setResult(data.result); setAttempt({...attempt,status:'submitted'}); setConfirm(false);
          })}>Подтвердить отправку</Button><Button className="!w-auto" type="button" variant="secondary" onClick={() => setConfirm(false)}>Вернуться к ответам</Button></div></div>}
      </>}
      {attempt.status === 'submitted' && !result && <Button loading={action.busy} onClick={() => void action.run(() => open(String(attempt.id)))}>Получить сохранённый результат</Button>}
      {result && <div className="space-y-4"><div className="flex flex-wrap items-center gap-3"><h3 className="text-2xl font-bold">{{fail:'Порог не пройден',pass:'Тест пройден',high:'Высокий результат'}[result.outcome]}</h3><Badge tone={result.outcome === 'fail' ? 'warning' : 'success'} dot>{result.outcome === 'high' ? 'Высокий результат' : result.outcome === 'pass' ? 'Пройден' : 'Не пройден'}</Badge>{result.status === 'DEMO' && <Badge tone="neutral">DEMO</Badge>}</div><div className="workspace-grid"><div className="workspace-stat"><span>Технический результат</span><strong>{(result.technicalTotal ?? 0).toFixed(1)}%</strong></div><div className="workspace-stat"><span>Teamwork · диагностика</span><strong>{(result.teamworkSubscore ?? 0).toFixed(1)}%</strong></div></div>
        <Alert kind={result.status === 'DEMO' ? 'warning' : 'info'}>{result.status === 'DEMO' ? 'Результат DEMO. Эта попытка не подтверждает квалификацию.' : result.verifiedGrade ? `Подтверждённая квалификация: ${result.verifiedSpecialization} · ${result.verifiedGrade}` : 'Квалификация не подтверждена.'}</Alert>
        {result.retestAvailableAt && <p className="text-sm">Повторное тестирование: {new Date(result.retestAvailableAt).toLocaleString('ru-RU')}</p>}{result.retestTargetGrade && <p className="text-sm">Предлагаемый следующий уровень: {result.retestTargetGrade}. Доступность проверит сервер.</p>}
        <Button variant="secondary" onClick={() => {setAttempt(null);setResult(null);}}>К выбору теста</Button></div>}
    </div>}
  </Panel></div>;
}

export function FspInfo() { return <Panel title="Достижения ФСП"><Empty>Подключение подтверждённой истории соревнований пока не доступно через API. Мы не выдаём demo-достижения за подтверждённые. Отсутствие истории ФСП не мешает пройти тестирование и участвовать в подборе при выполнении остальных условий.</Empty></Panel>; }
