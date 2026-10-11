'use client';
import { useEffect, useState } from 'react';
import { ApiError } from '../_lib/api';
import { checkEligibility, get, send, recalled, remember, type Catalog, type Company, type Eligibility, type Need, type Snapshot, type Item } from '../_lib/platform';
import { Badge, Button, Field, Alert, MetricBar, Tag } from './ui';
import { Empty, Panel, Select, Skills, Textarea, useAction } from './workspace';
import { Offer } from './InvitationsWorkspace';

export function CompanyProfile() {
  const [company,setCompany]=useState<Company|null>(null); const [loaded,setLoaded]=useState(false);
  const [name,setName]=useState(''); const [description,setDescription]=useState(''); const [email,setEmail]=useState(''); const [phone,setPhone]=useState('');
  const action=useAction();
  async function load() { try {const c=await get<Company>('/employer/company');setCompany(c);setName(c.name);setDescription(c.description||'');setEmail(typeof c.contacts?.email==='string'?c.contacts.email:'');setPhone(typeof c.contacts?.phone==='string'?c.contacts.phone:'');} catch(e) {if(!(e instanceof ApiError && e.status===404)) throw e;}setLoaded(true); }
  useEffect(()=>{void action.run(load);},[]);
  return <Panel title="Профиль компании" description="Компания принадлежит вашему аккаунту. Заполните её перед созданием потребностей.">{action.feedback}{!loaded ? <Button variant="secondary" loading={action.busy} onClick={()=>void action.run(load)}>Загрузить компанию</Button> : <form className="mt-5 space-y-5" onSubmit={e=>{e.preventDefault();void action.run(async()=>{setCompany(await send<Company>('/employer/company',{name,description,contacts:{...company?.contacts,email,phone}},'PUT'));},'Компания сохранена.');}}><Field id="company-name" label="Название компании" required value={name} onChange={e=>setName(e.target.value)} /><Textarea label="О компании и команде" value={description} onChange={setDescription}/><div className="workspace-grid"><Field id="company-email" label="Email компании" type="email" value={email} onChange={e=>setEmail(e.target.value)} /><Field id="company-phone" label="Телефон компании" type="tel" value={phone} onChange={e=>setPhone(e.target.value)} /></div><Button type="submit" loading={action.busy}>Сохранить компанию</Button></form>}</Panel>;
}

const emptyNeed = (): Omit<Need,'id'> => ({title:'',teamDescription:'',specialization:'',minGrade:'',targetGrade:'',requiredSkills:[],optionalSkills:[]});
export function Needs({catalog}:{catalog:Catalog}) {
  const [needs,setNeeds]=useState<Need[]|null>(null); const [editing,setEditing]=useState<number|null>(null); const [draft,setDraft]=useState(emptyNeed);
  const action=useAction();
  async function load(){setNeeds(await get<Need[]>('/employer/needs'));}
  useEffect(()=>{void action.run(load);},[]);
  function change<K extends keyof typeof draft>(key:K,value:(typeof draft)[K]){setDraft(p=>({...p,[key]:value}));}
  const skillIds=catalog.specializations.find(s=>s.id===draft.specialization)?.skillIds||[];
  const choices=catalog.skills.filter(s=>s.id!=='teamwork'&&skillIds.includes(s.id));
  function edit(n:Need){setEditing(n.id);const {id,...rest}=n;setDraft({...rest,optionalSkills:rest.optionalSkills||[]});}
  return <div className="space-y-5"><Panel title="Потребности в специалистах" description="Укажите технические навыки и минимальный подтверждённый уровень.">{action.feedback}<div className="my-4 flex flex-wrap gap-3"><Button className="!w-auto" variant="secondary" loading={action.busy} onClick={()=>void action.run(load)}>Обновить</Button><Button className="!w-auto" onClick={()=>{setEditing(null);setDraft(emptyNeed());}}>Новая потребность</Button></div>{needs?.length===0&&<Empty>Потребностей пока нет. Заполните форму ниже; профиль компании должен быть сохранён.</Empty>}<div className="grid gap-3 sm:grid-cols-2">{needs?.map(n=><button key={n.id} onClick={()=>edit(n)} className={`rounded-xl border p-5 text-left ${editing===n.id?'border-brand bg-brand-soft':'border-muted/60'}`}><h3 className="font-bold">{n.title||'Без названия'}</h3><p className="mt-2 text-xs text-ink/65">{n.specialization||'Не указана'} · {n.minGrade||'Минимальный уровень не указан'} → {n.targetGrade||'—'}</p></button>)}</div></Panel>
    <Panel title={editing?`Редактирование потребности №${editing}`:'Новая потребность'}><form className="space-y-5" onSubmit={e=>{e.preventDefault();void action.run(async()=>{
      const order=Object.fromEntries(catalog.grades.map(g=>[g.id,g.order]));if(order[draft.minGrade||'']>order[draft.targetGrade||''])throw new Error('Минимальный уровень не может быть выше целевого.');
      await send(editing?`/employer/needs/${editing}`:'/employer/needs',draft,editing?'PATCH':'POST',{409:'Сначала создайте компанию. Также проверьте, нет ли потребности с таким названием.'});await load();setEditing(null);setDraft(emptyNeed());
    },'Потребность сохранена. Теперь можно запустить подбор.');}}><Field id="need-title" label="Название роли / вакансии" required value={draft.title||''} onChange={e=>change('title',e.target.value)}/><Textarea label="Команда и задачи" value={draft.teamDescription||''} onChange={v=>change('teamDescription',v)} />
    <Select required label="Специализация" value={draft.specialization||''} onChange={v=>setDraft(p=>({...p,specialization:v,requiredSkills:[],optionalSkills:[]}))}><option value="">Выберите специализацию</option>{catalog.specializations.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</Select>
    <div className="workspace-grid">{(['minGrade','targetGrade'] as const).map(key=><Select key={key} required label={key==='minGrade'?'Минимальный грейд':'Целевой грейд'} value={draft[key]||''} onChange={v=>change(key,v)}><option value="">Выберите уровень</option>{catalog.grades.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</Select>)}</div>
    <Skills label="Обязательные технические навыки" choices={choices} values={draft.requiredSkills} onChange={v=>setDraft(p=>({...p,requiredSkills:v,optionalSkills:(p.optionalSkills||[]).filter(s=>!v.includes(s))}))}/>
    <Skills label="Желательные технические навыки" choices={choices.filter(s=>!draft.requiredSkills.includes(s.id))} values={draft.optionalSkills||[]} onChange={v=>change('optionalSkills',v)} />
    <Button type="submit" loading={action.busy}>Сохранить потребность</Button></form></Panel></div>;
}

export function TalentBank({catalog,userId}:{catalog:Catalog;userId:number}) {
  const [needs,setNeeds]=useState<Need[]>([]); const [needId,setNeedId]=useState(''); const [snapshotId,setSnapshotId]=useState('');
  const [snapshot,setSnapshot]=useState<Snapshot|null>(null); const [items,setItems]=useState<Item[]>([]); const [offer,setOffer]=useState<number|null>(null);
  const [specialization,setSpecialization]=useState('');const [grade,setGrade]=useState('');const [stack,setStack]=useState<string[]>([]);const [fsp,setFsp]=useState('');
  const action=useAction();
  useEffect(()=>{void action.run(async()=>{setNeeds(await get<Need[]>('/employer/needs'));});},[]);
  const base=`/employer/needs/${needId}/recommendations`;
  function selectNeed(value:string){setNeedId(value);setSnapshot(null);setItems([]);setOffer(null);setSnapshotId(recalled(`fsp_snapshot_${userId}_${value}`));resetFields();}
  function resetFields(){setSpecialization('');setGrade('');setStack([]);setFsp('');}
  async function display(s:Snapshot) {setSnapshot(s);setSnapshotId(String(s.id));remember(`fsp_snapshot_${userId}_${needId}`,String(s.id));resetFields();const view=await get<{items:Item[]}>(`${base}/${s.id}/items`);setItems(view.items);}
  return <div className="space-y-5"><Panel title="Подборка и банк талантов" description="Сначала создайте подборку для потребности. Фильтры меняют только её отображение, не баллы и порядок.">{action.feedback}
    <div className="mt-5 space-y-4"><Select label="Потребность" value={needId} onChange={selectNeed}><option value="">Выберите потребность</option>{needs.map(n=><option key={n.id} value={n.id}>{n.title||`Потребность №${n.id}`}</option>)}</Select>{!needs.length&&<Empty>Сначала создайте потребность в разделе «Потребности».</Empty>}
    <Button disabled={!needId} loading={action.busy} onClick={()=>void action.run(async()=>{setSnapshot(null);setItems([]);setOffer(null);await display(await send<Snapshot>(base,undefined,'POST',{422:'Заполните специализацию, минимальный грейд и канонические технические навыки потребности.',503:'Подбор временно недоступен. Проверьте доступность каталога.'}));})}>Создать новую подборку</Button>
    <form className="flex flex-wrap items-end gap-3" onSubmit={e=>{e.preventDefault();void action.run(async()=>{if(!/^\d+$/.test(snapshotId)||Number(snapshotId)<1)throw new Error('Введите номер сохранённой подборки.');setSnapshot(null);setItems([]);setOffer(null);await display(await get<Snapshot>(`${base}/${snapshotId}`));});}}><Field id="snapshot-id" label="Сохранённая подборка №" type="number" min={1} required value={snapshotId} onChange={e=>setSnapshotId(e.target.value)}/><Button className="!w-auto" type="submit" variant="secondary" disabled={!needId} loading={action.busy}>Открыть без пересчёта</Button></form><p className="text-xs text-ink/60">Последний номер запоминается на этом устройстве. Сервер проверяет владельца каждой подборки.</p></div></Panel>
    {snapshot&&<Panel title={`Подборка №${snapshot.id}`} description={`Версия алгоритма: ${snapshot.algorithmVersion||'историческая'}. Порядок и баллы сохранены.`}>
      <form className="space-y-4" onSubmit={e=>{e.preventDefault();void action.run(async()=>{setItems([]);setOffer(null);const query=new URLSearchParams();if(specialization)query.set('specialization',specialization);if(grade)query.set('grade',grade);stack.forEach(s=>query.append('stack',s));if(fsp)query.set('hasFspAchievements',fsp);setItems((await get<{items:Item[]}>(`${base}/${snapshot.id}/items?${query}`)).items);});}}>
        <div className="workspace-grid"><Select label="Специализация" value={specialization} onChange={setSpecialization}><option value="">Все</option>{catalog.specializations.map(s=><option key={s.id} value={s.id}>{s.name}</option>)}</Select><Select label="Подтверждённый грейд" value={grade} onChange={setGrade}><option value="">Все</option>{catalog.grades.map(g=><option key={g.id} value={g.id}>{g.name}</option>)}</Select><Select label="История достижений ФСП" value={fsp} onChange={setFsp}><option value="">Не важно</option><option value="true">Есть история</option><option value="false">Нет истории</option></Select></div>
        <Skills label="Навыки: все выбранные (AND)" choices={catalog.skills.filter(s=>s.id!=='teamwork')} values={stack} onChange={setStack}/><p className="text-xs text-ink/60">Отдельный фильтр category недоступен: его справочник ещё не определён.</p><div className="flex gap-3"><Button type="submit" loading={action.busy}>Применить фильтры</Button><Button type="button" variant="secondary" loading={action.busy} onClick={()=>void action.run(async()=>{resetFields();setItems([]);setOffer(null);setItems((await get<{items:Item[]}>(`${base}/${snapshot.id}/items`)).items);})}>Сбросить фильтры</Button></div></form>
      <div className="mt-6 space-y-4">{!items.length?<Empty>{action.busy?'Загрузка…':snapshot.items.length?'Нет кандидатов по выбранным фильтрам или доступ к данным изменился.':'Подходящих кандидатов пока нет. Нужны подтверждённые email и квалификация, публикация профиля и соответствие потребности. Результат DEMO не даёт допуска к подбору.'}</Empty>:items.map(item=><article key={item.candidate.id} className="rounded-xl border border-muted/60 p-5"><div className="flex flex-wrap items-start justify-between gap-3"><div><Badge tone="brand">Место {item.rank??'—'}</Badge><h3 className="mt-3 text-lg font-bold">Кандидат <span className="font-mono">№{item.candidate.id}</span></h3><p className="mt-1 text-sm text-ink/65">{item.candidate.specialization||'Специализация не указана'} · {item.candidate.grade||'Нет подтверждённого грейда'}</p></div><div className="text-right"><span className="text-xs text-ink/60">Сохранённый балл</span><p className="text-2xl font-bold tabular-nums text-brand">{item.score.toFixed(3)}</p></div></div>
        <div className="my-4 flex flex-wrap gap-2">{item.candidate.stack?.map(s=><Tag key={s}>{s}</Tag>)}</div>
        {item.components&&<div className="space-y-2.5"><MetricBar label="Навыки" value={item.components.skillFit} /><MetricBar label="Сила теста" value={item.components.assessmentStrength} className="bg-brand-dark" /><MetricBar label="Бонус ФСП" value={item.components.fspBonus} className="bg-accent" /></div>}
        {item.filterFit !== undefined&&<div className="mt-3 text-xs text-ink/65"><p>Похожие кандидаты · соответствие фильтру: {item.filterFit.toFixed(3)} · балл качества: {item.qualityScore?.toFixed(3)} · коэффициент порядка: {item.rankingFit?.toFixed(3)}</p><ul>{item.filterFactors?.filter(f=>f.coefficient<1).map(f=><li key={f.code}>{f.code}: {f.coefficient.toFixed(2)} — {f.reason}</li>)}</ul><p>Стек используется для поиска, но не умножает балл повторно; достижения учтены только в бонусе.</p></div>}
        <ul className="my-4 space-y-1 text-xs text-ink/65">{(snapshot.items.find(i=>i.candidate.id===item.candidate.id)?.reasons||[]).map((r,i)=><li key={i}>{r.replace('Required skill evidence:','Подтверждённое покрытие навыков:').replace('Technical test:','Технический тест:').replace('Verified FSP bonus:','Подтверждённый бонус ФСП:').replace('Demo FSP bonus:','Демо-бонус ФСП (синтетические данные):')}</li>)}</ul>
        <p className="mb-4 text-xs text-ink/60">Контакты скрыты. Доступ возможен только через принятое приглашение и действующие согласия.</p><Button variant="accent" onClick={()=>setOffer(item.candidate.id)}>Пригласить кандидата</Button><CandidateEligibility needId={Number(needId)} candidateId={item.candidate.id} />{offer===item.candidate.id&&<Offer candidateId={offer} onClose={()=>setOffer(null)}/>}</article>)}</div></Panel>}
  </div>;
}

const REASON_LABELS: Record<string, string> = {
  SPECIALIZATION_MISMATCH: 'Специализация кандидата не совпадает с потребностью.',
  GRADE_BELOW_MINIMUM: 'Подтверждённый грейд ниже минимального для потребности.',
  REQUIRED_SKILL_EVIDENCE_MISSING: 'Нет подтверждённых данных по обязательным навыкам.',
  REQUIRED_SKILL_EVIDENCE_INVALID: 'Данные по обязательному навыку некорректны.',
  REQUIRED_SKILL_BELOW_THRESHOLD: 'Подтверждённое покрытие обязательного навыка ниже порога.',
};

// Диагностика формального фильтра для конкретного кандидата из подборки.
// candidateId приходит из API (TalentItemDTO.candidate.id), а не из ручного ввода.
function CandidateEligibility({ needId, candidateId }: { needId: number; candidateId: number }) {
  const [result, setResult] = useState<Eligibility | null>(null);
  const action = useAction();
  return (
    <div className="mt-3 space-y-3">
      <Button className="!w-auto" variant="secondary" loading={action.busy} onClick={() => void action.run(async () => { setResult(await checkEligibility(needId, candidateId)); })}>Проверить соответствие</Button>
      {action.feedback}
      {result && (
        <div className="space-y-2 rounded-lg bg-surface/60 p-4 text-sm">
          <Alert kind={result.eligible ? 'success' : 'info'}>{result.eligible ? 'Кандидат проходит формальный фильтр потребности.' : 'Кандидат не проходит формальный фильтр по причинам ниже.'}</Alert>
          {result.reasonCodes.length > 0 && <ul className="space-y-1 text-xs text-ink/70">{result.reasonCodes.map(code => <li key={code} className="flex gap-2"><span className="mt-1 h-1.5 w-1.5 shrink-0 bg-accent" aria-hidden="true" />{REASON_LABELS[code] ?? code}</li>)}</ul>}
          {result.missingRequiredSkills.length > 0 && <div><p className="mb-1 text-xs font-semibold uppercase tracking-wide text-ink/60">Неподтверждённые обязательные навыки</p><div className="flex flex-wrap gap-2">{result.missingRequiredSkills.map(s => <span key={s} className="workspace-badge">{s}</span>)}</div></div>}
          <p className="text-xs text-ink/60">Версия политики: {result.policyVersion}</p>
        </div>
      )}
    </div>
  );
}
