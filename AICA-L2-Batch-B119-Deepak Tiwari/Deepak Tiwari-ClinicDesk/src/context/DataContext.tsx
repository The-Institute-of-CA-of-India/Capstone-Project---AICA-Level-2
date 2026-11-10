import { createContext, useContext, useMemo, type ReactNode } from 'react';
import { usePatientsLive, useServicesLive } from '../data/hooks';
import type { Patient, Service } from '../types';

interface DataApi {
  patients: Patient[];
  services: Service[];
  loading: boolean;
  error: string;
  patientById: (id: string) => Patient | undefined;
}
const Ctx = createContext<DataApi | null>(null);
export const useData = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error('useData outside provider');
  return v;
};

export function DataProvider({ children }: { children: ReactNode }) {
  const p = usePatientsLive(true);
  const s = useServicesLive(true);
  const api = useMemo<DataApi>(() => {
    const patients = [...p.data].sort((a, b) => a.name.localeCompare(b.name));
    const map = new Map(patients.map((x) => [x.id, x]));
    return {
      patients, services: s.data, loading: p.loading || s.loading, error: p.error || s.error,
      patientById: (id) => map.get(id)
    };
  }, [p, s]);
  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}
