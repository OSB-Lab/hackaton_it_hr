import { notFound } from 'next/navigation';
import { CabinetStub } from '../../_components/CabinetStub';
export default function CandidateSection({params}:{params:{section:string}}) {
  if(!['dashboard','profile','assessment','invitations','fsp'].includes(params.section)) notFound();
  return <CabinetStub key={params.section} role="candidate" section={params.section}/>;
}
