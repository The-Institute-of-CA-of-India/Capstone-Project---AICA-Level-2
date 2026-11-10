import type { Role } from '../types';

export type Perm =
  | 'settings' | 'users' | 'services.edit' | 'void' | 'prescribe'
  | 'patients.write' | 'billing.write' | 'reports' | 'files.delete' | 'activity';

const ALL: Perm[] = ['settings', 'users', 'services.edit', 'void', 'prescribe', 'patients.write', 'billing.write', 'reports', 'files.delete', 'activity'];
const MATRIX: Record<Role, Perm[]> = {
  owner: ALL,
  doctor: ['prescribe', 'patients.write', 'billing.write', 'reports', 'files.delete'],
  reception: ['patients.write', 'billing.write'],
  none: []
};
/** UI gate only. The same rules are enforced for real in firestore.rules / storage.rules. */
export const can = (role: Role | undefined, p: Perm) => !!role && MATRIX[role].includes(p);
export const ROLE_LABEL: Record<Role, string> = { owner: 'Owner', doctor: 'Doctor', reception: 'Front desk', none: 'No access' };
export const ROLE_HELP: Record<Role, string> = {
  owner: 'Everything, including Settings, prices, users and voiding invoices.',
  doctor: 'Patients, visits, prescriptions, billing and reports. No Settings, users or voiding.',
  reception: 'Patients, appointments, visits, payments and invoices. No reports, Settings, price changes or voiding.',
  none: 'Waiting for the owner to approve access.'
};
