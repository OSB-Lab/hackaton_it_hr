import { ApiError, request, tokenStore } from './api';

export interface Catalog {
  version: string;
  specializations: { id: string; name: string; skillIds: string[] }[];
  grades: { id: string; name: string; order: number }[];
  skills: { id: string; name: string }[];
  tests: { specialization: string; grade: string; status: string; version: string }[];
}
export interface Profile {
  fullName: string | null; email: string; phone: string | null; stack: string[];
  role: string | null; experienceMonths: number | null; softSkills: string[];
  specialization: string | null; selfDeclaredGrade: string | null;
  verifiedGrade: string | null; verifiedSpecialization: string | null;
  verifiedSkills: Record<string, number>;
  diagnosticRole: string | null; diagnosticGrade: string | null;
  diagnosticStatus: 'DEMO' | null; diagnosticSkills: Record<string, number>;
  consents: { processing: boolean; publication: boolean }; privacy: { showContacts: boolean };
  fspSource: 'synthetic-demo-not-fsp' | null;
  fspAchievements: { recordId: string; kind: 'competition_result' | 'sport_rank'; result: string;
    role: string; skillIds: string[]; achievedAt: string }[];
  eligibleForEmployerSearch: boolean;
}
export interface Attempt {
  id: number; status: 'active' | 'submitted';
  assessment: { status: string; variant: string; blueprintVersion: string; questions: {
    id: string; prompt: string; options: { id: string; text: string }[];
  }[] };
}
export interface Result {
  outcome: 'fail' | 'pass' | 'high'; status: string; technicalTotal: number | null;
  teamworkSubscore: number | null; verifiedGrade: string | null; verifiedSpecialization: string | null;
  retestAvailableAt: string | null; retestOffer: string | null; retestTargetGrade: string | null;
}
export interface Company { id: number; name: string; description: string | null; contacts: Record<string, unknown> | null }
export interface Need {
  id: number; title: string | null; teamDescription: string | null; specialization: string | null;
  minGrade: string | null; targetGrade: string | null; requiredSkills: string[]; optionalSkills: string[] | null;
}
export interface Item {
  candidate: { id: number; specialization?: string | null; grade?: string | null; stack?: string[]; hasFspAchievements?: boolean; verifiedSkills?: Record<string,number> };
  rank: number | null; score: number;
  components: { skillFit: number; assessmentStrength: number; fspBonus: number } | null;
  filterFit?: number; rankingFit?: number; qualityScore?: number;
  filterFactors?: {code:string; coefficient:number; reason:string}[];
  taxonomyVersion?: string; filterPolicyVersion?: string;
  reasons?: string[];
}
export interface Snapshot { id: number; needId: number; algorithmVersion: string | null; items: Item[] }
export interface Invitation {
  id: number; companyId: number; candidateId: number; offerDescription: string | null; contactMethod: string | null;
  salaryMin: string; salaryMax: string; currency: string; status: 'sent' | 'viewed' | 'accepted' | 'declined';
  contacts?: { email: string; phone: string | null } | null;
}
export const get = <T,>(path: string) => request<T>(path, { auth: true });
export const send = <T,>(path: string, body: unknown, method: 'POST' | 'PATCH' | 'PUT' = 'POST', errors?: Record<number, string>) =>
  request<T>(path, { auth: true, method, body, errors });
export function remember(key: string, value: string) { try { localStorage.setItem(key, value); } catch {} }
export function recalled(key: string) { try { return localStorage.getItem(key) || ''; } catch { return ''; } }
export async function downloadPdf() {
  let response: Response;
  try { response = await fetch('/api/me/profile-pdf', { headers: { Authorization: `Bearer ${tokenStore.get() || ''}` }, cache: 'no-store' }); }
  catch { throw new Error('Нет связи с сервером. Попробуйте ещё раз.'); }
  if (response.status === 401) { tokenStore.clear(); window.location.assign('/login?expired=1'); }
  if (!response.ok) throw new ApiError(response.status, response.status === 404 ? 'Сначала сохраните профиль.' : 'Не удалось скачать PDF. Попробуйте ещё раз.');
  if (!response.headers.get('content-type')?.includes('application/pdf')) throw new Error('Сервер вернул неверный формат файла.');
  const url = URL.createObjectURL(await response.blob());
  const link = document.createElement('a'); link.href = url; link.download = 'candidate-profile.pdf';
  document.body.appendChild(link); link.click(); link.remove(); setTimeout(() => URL.revokeObjectURL(url), 1000);
}
