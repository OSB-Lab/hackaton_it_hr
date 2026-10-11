'use client';
import { useEffect, useState } from 'react';
import { ApiError, type Role } from '../_lib/api';
import { get, send, type Invitation, type Company } from '../_lib/platform';
import { Alert, Badge, Button, Field } from './ui';
import { Empty, Panel, Textarea, useAction } from './workspace';

const statusLabel = {sent:'Отправлено',viewed:'Просмотрено',accepted:'Принято',declined:'Отклонено'};
const statusTone = {sent:'brand',viewed:'neutral',accepted:'success',declined:'warning'} as const;
export function Invitations({role}:{role:Role}) {
  const [items,setItems] = useState<Invitation[] | null>(null);
  const [detail,setDetail] = useState<Invitation | null>(null);
  const action = useAction();
  async function load() { setDetail(null); setItems(await get<Invitation[]>('/invitations')); }
  useEffect(() => { void action.run(load); }, []);
  // Contact permissions may be revoked in another tab. Never keep an open disclosure
  // indefinitely; refetch on focus and clear contacts before every subsequent action.
  useEffect(() => { const clear = () => setDetail(null); window.addEventListener('blur',clear); return () => window.removeEventListener('blur',clear); }, []);
  async function open(id:number) { setDetail(null); const d = await get<Invitation>(`/invitations/${id}`); setDetail(d); setItems(prev => prev?.map(i => i.id===id ? {...i,status:d.status} : i) || null); }
  return <Panel title={role === 'candidate' ? 'Входящие приглашения' : 'Отправленные предложения'} description="Зарплата и условия доступны сразу. Принятие приглашения не отменяет ваши настройки приватности.">
    <div className="mb-5 flex justify-end"><Button className="!w-auto" variant="secondary" loading={action.busy} onClick={() => void action.run(load)}>Обновить список</Button></div>{action.feedback}
    {items === null ? <p className="mt-4 text-sm">{action.busy ? 'Загрузка приглашений…' : 'Нажмите «Обновить список», чтобы повторить запрос.'}</p> : items.length === 0 ? <Empty>Приглашений пока нет. {role === 'candidate' ? 'Для участия в подборе нужны подтверждённые email, квалификация и согласие на публикацию.' : 'Создайте предложение из карточки кандидата в подборке.'}</Empty> : <div className="mt-5 grid gap-4 lg:grid-cols-[1fr_1fr]">
      <div className="space-y-3">{items.map(item => <button disabled={action.busy} key={item.id} onClick={() => void action.run(() => open(item.id))} className={`w-full rounded-xl border p-5 text-left transition hover:border-brand ${detail?.id === item.id ? 'border-brand bg-brand-soft' : 'border-muted/60 bg-white'}`}><Badge tone={statusTone[item.status]}>{statusLabel[item.status]}</Badge><h3 className="mt-3 font-bold">Предложение №{item.id}</h3><p className="mt-2 line-clamp-2 text-sm text-ink/70">{item.offerDescription}</p><p className="mt-3 text-sm font-semibold">{item.salaryMin} — {item.salaryMax} {item.currency}</p></button>)}</div>
      <div>{!detail ? <Empty>Выберите предложение для просмотра. У кандидата просмотр переведёт новое приглашение в статус «Просмотрено».</Empty> : <article className="rounded-xl border border-muted/60 p-5"><Badge tone={statusTone[detail.status]}>{statusLabel[detail.status]}</Badge><h3 className="my-4 text-lg font-bold">Предложение №{detail.id}</h3><p className="whitespace-pre-wrap text-sm leading-relaxed">{detail.offerDescription}</p><p className="mt-4 font-bold">{detail.salaryMin} — {detail.salaryMax} {detail.currency}</p><p className="mt-3 text-sm">Связь: {detail.contactMethod || 'Не указана'}</p>
        {role==='candidate' && (detail.status==='sent'||detail.status==='viewed') && <div className="mt-6 space-y-3"><Alert kind="info">После принятия контакты будут доступны этой компании только при включённом раскрытии и действующих согласиях.</Alert><div className="flex gap-3">{(['accept','decline'] as const).map(decision => <Button key={decision} variant={decision==='accept'?'primary':'secondary'} loading={action.busy} onClick={() => void action.run(async () => { await send(`/invitations/${detail.id}/${decision}`,undefined); await open(detail.id); }, decision==='accept'?'Приглашение принято.':'Приглашение отклонено.')}>{decision==='accept'?'Принять':'Отклонить'}</Button>)}</div></div>}
        {role==='employer' && <div className="mt-6 rounded-lg bg-surface/60 p-4">{detail.contacts ? <><h4 className="mb-2 font-bold">Разрешённые контакты</h4><p className="break-all text-sm">{detail.contacts.email}</p>{detail.contacts.phone && <p className="mt-2 text-sm">{detail.contacts.phone}</p>}</> : <p className="text-sm leading-relaxed">Контакты скрыты. Они доступны после принятия приглашения при действующих согласиях и разрешении кандидата.</p>}<button className="mt-3 text-sm font-semibold text-brand underline" disabled={action.busy} onClick={() => void action.run(() => open(detail.id))}>Проверить доступ заново</button></div>}
      </article>}</div>
    </div>}
  </Panel>;
}

export function Offer({candidateId,onClose}:{candidateId:number;onClose:()=>void}) {
  const [description,setDescription]=useState(''); const [contact,setContact]=useState('');
  const [min,setMin]=useState(''); const [max,setMax]=useState(''); const [sent,setSent]=useState(false);
  const action=useAction();
  return <section className="mt-5 rounded-xl border border-brand bg-brand-soft/40 p-5" aria-label="Создать приглашение"><h3 className="mb-4 font-bold">Предложение кандидату №{candidateId}</h3>{action.feedback}
    {!sent && <form className="space-y-4" onSubmit={e => { e.preventDefault(); void action.run(async () => {
      if (!/^\d+(\.\d{1,2})?$/.test(min)||!/^\d+(\.\d{1,2})?$/.test(max)||Number(min)<=0||Number(max)<Number(min)) throw new Error('Укажите положительную зарплату; максимум не меньше минимума (до двух знаков после точки).');
      let company:Company; try { company=await get<Company>('/employer/company'); } catch(e) { if(e instanceof ApiError && e.status===404) throw new Error('Сначала заполните профиль компании.'); throw e; }
      await send('/invitations',{companyId:company.id,candidateId,offerDescription:description,contactMethod:contact,salaryMin:min,salaryMax:max,currency:'RUB'},'POST',{409:'Активное приглашение этому кандидату уже существует.',503:'Нет достоверной подтверждённой квалификации кандидата. Приглашение недоступно.',404:'Кандидат или компания недоступны. Обновите подборку.'}); setSent(true);
    },'Предложение отправлено. Его статус доступен в разделе «Приглашения».'); }}><Textarea label="Описание предложения" required value={description} onChange={setDescription} /><Field id={`offer-contact-${candidateId}`} label="Как связаться с вашей компанией" required maxLength={200} value={contact} onChange={e=>setContact(e.target.value)} /><div className="workspace-grid"><Field id={`offer-min-${candidateId}`} label="Зарплата от, RUB" required inputMode="decimal" value={min} onChange={e=>setMin(e.target.value)} /><Field id={`offer-max-${candidateId}`} label="Зарплата до, RUB" required inputMode="decimal" value={max} onChange={e=>setMax(e.target.value)} /></div><Button type="submit" variant="accent" loading={action.busy}>Отправить предложение</Button></form>}
    <button className="mt-4 text-sm font-semibold underline" onClick={onClose} disabled={action.busy}>Закрыть</button></section>;
}
