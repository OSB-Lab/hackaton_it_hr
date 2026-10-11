import { notFound } from 'next/navigation';
import { CabinetStub } from '../../_components/CabinetStub';
export default function EmployerSection({params}:{params:{section:string}}) {
  if(!['dashboard','company','needs','talent','invitations'].includes(params.section)) notFound();
  return <CabinetStub key={params.section} role="employer" section={params.section}/>;
}
