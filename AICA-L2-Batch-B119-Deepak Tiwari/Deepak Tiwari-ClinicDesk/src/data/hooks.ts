import { useEffect, useState } from 'react';
import { collection, doc, limit, onSnapshot, orderBy, query, where, type DocumentData, type Query } from 'firebase/firestore';
import { getDb } from '../firebase/client';
import { C } from './db';
import type { Appointment, Invite, LogEntry, Patient, PatientFile, Prescription, Service, UserProfile, Visit } from '../types';

export interface Live<T> { data: T[]; loading: boolean; error: string }

/** Subscribes to a query and keeps the result in React state. Pass a stable `key` that changes with the query. */
export function useLive<T>(make: () => Query<DocumentData> | null, key: string, enabled = true): Live<T> {
  const [state, setState] = useState<Live<T>>({ data: [], loading: true, error: '' });
  useEffect(() => {
    if (!enabled) { setState({ data: [], loading: false, error: '' }); return; }
    const q = make();
    if (!q) { setState({ data: [], loading: false, error: '' }); return; }
    setState((s) => ({ ...s, loading: true, error: '' }));
    const off = onSnapshot(
      q,
      (snap) => setState({ data: snap.docs.map((d) => ({ ...(d.data() as object), id: d.id }) as T), loading: false, error: '' }),
      (err) => setState({ data: [], loading: false, error: err.code === 'permission-denied' ? 'You do not have permission to view this.' : err.message })
    );
    return off;
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, enabled]);
  return state;
}

const col = (n: string) => collection(getDb(), n);

export const usePatientsLive = (enabled: boolean) => useLive<Patient>(() => col(C.patients), 'patients', enabled);
export const useServicesLive = (enabled: boolean) => useLive<Service>(() => col(C.services), 'services', enabled);

export const useVisitsRange = (from: string, to: string, enabled = true) =>
  useLive<Visit>(() => query(col(C.visits), where('date', '>=', from), where('date', '<=', to)), `v:${from}:${to}`, enabled);
export const useOutstanding = (enabled = true) =>
  useLive<Visit>(() => query(col(C.visits), where('status', 'in', ['Unpaid', 'Part-paid'])), 'outstanding', enabled);
export const useVisitsForPatient = (pid: string) =>
  useLive<Visit>(() => query(col(C.visits), where('patientId', '==', pid)), `pv:${pid}`);

export const useApptsRange = (from: string, to: string, enabled = true) =>
  useLive<Appointment>(() => query(col(C.appointments), where('date', '>=', from), where('date', '<=', to)), `a:${from}:${to}`, enabled);
export const useApptsForPatient = (pid: string) =>
  useLive<Appointment>(() => query(col(C.appointments), where('patientId', '==', pid)), `pa:${pid}`);

export const usePrescriptionsForPatient = (pid: string, enabled = true) =>
  useLive<Prescription>(() => query(col(C.prescriptions), where('patientId', '==', pid)), `rx:${pid}`, enabled);
export const usePatientFiles = (pid: string) =>
  useLive<PatientFile>(() => collection(getDb(), C.patients, pid, 'files'), `files:${pid}`);

export const useUsersLive = (enabled: boolean) => useLive<UserProfile & { id: string }>(() => col(C.users), 'users', enabled);
export const useInvitesLive = (enabled: boolean) => useLive<Invite>(() => col(C.invites), 'invites', enabled);

/** Live profile of one user (used by the "waiting for approval" screen). */
export function useProfileDoc(uid: string | null) {
  const [p, setP] = useState<UserProfile | null>(null);
  useEffect(() => {
    if (!uid) return;
    return onSnapshot(doc(getDb(), C.users, uid), (s) => setP(s.exists() ? ({ ...(s.data() as UserProfile), uid }) : null), () => {});
  }, [uid]);
  return p;
}

export const useActivityLive = (enabled: boolean) =>
  useLive<LogEntry>(() => query(col(C.activityLog), orderBy('at', 'desc'), limit(60)), 'activity', enabled);

/** One invoice, kept live (so the invoice window updates after a payment is added). */
export function useVisitDoc(id: string | null) {
  const [v, setV] = useState<Visit | null>(null);
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    if (!id) { setV(null); setLoading(false); return; }
    setLoading(true);
    return onSnapshot(doc(getDb(), C.visits, id), (s) => { setV(s.exists() ? ({ ...(s.data() as Visit), id }) : null); setLoading(false); }, () => setLoading(false));
  }, [id]);
  return { visit: v, loading };
}
