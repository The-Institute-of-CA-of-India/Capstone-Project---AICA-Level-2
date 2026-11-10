import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState, type ReactNode } from 'react';
import {
  GoogleAuthProvider, RecaptchaVerifier, createUserWithEmailAndPassword, getRedirectResult, onAuthStateChanged,
  sendEmailVerification, sendPasswordResetEmail, signInWithEmailAndPassword, signInWithPhoneNumber, signInWithPopup,
  signInWithRedirect, signOut as fbSignOut, updateProfile, type ConfirmationResult, type User
} from 'firebase/auth';
import { getAuthClient } from '../firebase/client';
import { bootstrapClinic, createProfile, getInvite, getProfile, isInitialised, touchLogin, type Identity } from '../data/db';
import { defaultSettings } from '../config/defaults';
import type { CountryCode, UserProfile } from '../types';

export type AuthState =
  | { kind: 'loading' }
  | { kind: 'signedOut' }
  | { kind: 'needsVerify'; user: User }
  | { kind: 'firstRun'; user: User; identity: Identity }
  | { kind: 'pending'; user: User; profile: UserProfile }
  | { kind: 'disabled'; user: User; profile: UserProfile }
  | { kind: 'ready'; user: User; profile: UserProfile }
  | { kind: 'error'; message: string };

interface AuthApi {
  state: AuthState;
  signInGoogle(): Promise<void>;
  signInEmail(email: string, password: string): Promise<void>;
  signUpEmail(name: string, email: string, password: string): Promise<void>;
  resetPassword(email: string): Promise<void>;
  sendVerification(): Promise<void>;
  recheck(): Promise<void>;
  startPhone(e164: string, container: HTMLElement): Promise<void>;
  confirmPhone(code: string): Promise<void>;
  completeFirstRun(c: CountryCode, clinicName: string, sampleServices: boolean): Promise<void>;
  signOut(): Promise<void>;
}
const Ctx = createContext<AuthApi | null>(null);
export const useAuth = () => {
  const v = useContext(Ctx);
  if (!v) throw new Error('useAuth outside provider');
  return v;
};

export function authErrorMessage(e: unknown): string {
  const code = (e as { code?: string })?.code || '';
  const map: Record<string, string> = {
    'auth/invalid-credential': 'That email or password is not right.',
    'auth/wrong-password': 'That email or password is not right.',
    'auth/user-not-found': 'That email or password is not right.',
    'auth/invalid-email': 'Enter a valid email address.',
    'auth/email-already-in-use': 'An account with this email already exists. Try signing in, or use "Forgot password".',
    'auth/weak-password': 'Choose a password with at least 8 characters.',
    'auth/too-many-requests': 'Too many attempts. Please wait a few minutes and try again.',
    'auth/network-request-failed': 'No internet connection. Check your network and try again.',
    'auth/popup-closed-by-user': 'The Google sign-in window was closed before finishing.',
    'auth/cancelled-popup-request': 'The Google sign-in window was closed before finishing.',
    'auth/account-exists-with-different-credential': 'This email is already registered with another sign-in method. Sign in with that method first.',
    'auth/invalid-phone-number': 'That phone number is not valid. Include the country code, e.g. +254712345678.',
    'auth/missing-phone-number': 'Enter your mobile number.',
    'auth/invalid-verification-code': 'That code is not right. Check the SMS and try again.',
    'auth/code-expired': 'That code has expired. Request a new one.',
    'auth/quota-exceeded': 'The daily SMS limit for this project has been reached. Use Google or email sign-in, or try tomorrow.',
    'auth/captcha-check-failed': 'The security check failed. Reload the page and try again.',
    'auth/operation-not-allowed': 'This sign-in method is not switched on in Firebase yet (Authentication → Sign-in method).',
    'auth/unauthorized-domain': 'This web address is not authorised in Firebase (Authentication → Settings → Authorized domains).',
    'auth/user-disabled': 'This account has been disabled.',
    'auth/requires-recent-login': 'Please sign in again and retry.',
    'auth/billing-not-enabled': 'SMS sign-in needs the Firebase Blaze plan, or a test phone number. See the README.'
  };
  return map[code] || (e instanceof Error ? e.message : 'Something went wrong. Please try again.');
}

let recaptcha: RecaptchaVerifier | null = null;
let confirmation: ConfirmationResult | null = null;

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<AuthState>({ kind: 'loading' });
  const seq = useRef(0);

  const evaluate = useCallback(async (user: User | null) => {
    const my = ++seq.current;
    const set = (s: AuthState) => { if (my === seq.current) setState(s); };
    if (!user) { set({ kind: 'signedOut' }); return; }
    try {
      const usesPassword = user.providerData.some((p) => p.providerId === 'password');
      if (usesPassword && !user.emailVerified) { set({ kind: 'needsVerify', user }); return; }

      const identity: Identity = { uid: user.uid, displayName: user.displayName || '', email: (user.email || '').toLowerCase(), phone: user.phoneNumber || '' };
      let profile = await getProfile(user.uid);

      if (!profile) {
        if (!(await isInitialised())) { set({ kind: 'firstRun', user, identity }); return; }
        // Is this person invited (by verified e-mail or by phone number)?
        const keys = [user.emailVerified && identity.email ? identity.email : '', identity.phone].filter(Boolean);
        for (const k of keys) {
          const inv = await getInvite(k);
          if (inv) {
            try { profile = await createProfile(identity, inv.role, 'active'); break; } catch { /* fall through to a request */ }
          }
        }
        if (!profile) profile = await createProfile(identity, 'none', 'pending');
      }

      if (profile.status === 'disabled') { set({ kind: 'disabled', user, profile }); return; }
      if (profile.status === 'pending' || profile.role === 'none') { set({ kind: 'pending', user, profile }); return; }
      void touchLogin(user.uid);
      set({ kind: 'ready', user, profile });
    } catch (e) {
      set({ kind: 'error', message: authErrorMessage(e) });
    }
  }, []);

  useEffect(() => {
    const auth = getAuthClient();
    getRedirectResult(auth).catch(() => { /* surfaced by the next sign-in attempt */ });
    return onAuthStateChanged(auth, (u) => { void evaluate(u); });
  }, [evaluate]);

  const api = useMemo<AuthApi>(() => ({
    state,
    async signInGoogle() {
      const auth = getAuthClient();
      const provider = new GoogleAuthProvider();
      provider.setCustomParameters({ prompt: 'select_account' });
      try { await signInWithPopup(auth, provider); }
      catch (e) {
        const code = (e as { code?: string }).code;
        // Some phones / installed apps / embedded previews block pop-ups: use a full-page redirect instead.
        if (code === 'auth/popup-blocked' || code === 'auth/operation-not-supported-in-this-environment') await signInWithRedirect(auth, provider);
        else throw e;
      }
    },
    async signInEmail(email, password) { await signInWithEmailAndPassword(getAuthClient(), email.trim(), password); },
    async signUpEmail(name, email, password) {
      const cred = await createUserWithEmailAndPassword(getAuthClient(), email.trim(), password);
      if (name.trim()) await updateProfile(cred.user, { displayName: name.trim() });
      await sendEmailVerification(cred.user);
      await evaluate(cred.user);
    },
    async resetPassword(email) { await sendPasswordResetEmail(getAuthClient(), email.trim()); },
    async sendVerification() { const u = getAuthClient().currentUser; if (u) await sendEmailVerification(u); },
    async recheck() {
      const u = getAuthClient().currentUser;
      if (u) { await u.reload(); await u.getIdToken(true); await evaluate(getAuthClient().currentUser); }
    },
    async startPhone(e164, container) {
      const auth = getAuthClient();
      if (recaptcha) { try { recaptcha.clear(); } catch { /* ignore */ } recaptcha = null; }
      container.innerHTML = '';
      const holder = document.createElement('div');
      container.appendChild(holder);
      recaptcha = new RecaptchaVerifier(auth, holder, { size: 'invisible' });
      try { confirmation = await signInWithPhoneNumber(auth, e164, recaptcha); }
      catch (e) { try { recaptcha.clear(); } catch { /* ignore */ } recaptcha = null; throw e; }
    },
    async confirmPhone(code) {
      if (!confirmation) throw new Error('Request a new code first.');
      await confirmation.confirm(code.trim());
      confirmation = null;
    },
    async completeFirstRun(c, clinicName, sampleServices) {
      if (state.kind !== 'firstRun') return;
      const settings = defaultSettings(c, clinicName.trim());
      const profile = await bootstrapClinic(state.identity, settings, sampleServices);
      setState({ kind: 'ready', user: state.user, profile });
    },
    async signOut() { await fbSignOut(getAuthClient()); }
  }), [state, evaluate]);

  return <Ctx.Provider value={api}>{children}</Ctx.Provider>;
}

