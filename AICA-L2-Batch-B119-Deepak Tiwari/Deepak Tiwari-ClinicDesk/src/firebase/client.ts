import { initializeApp, type FirebaseApp } from 'firebase/app';
import { getAuth, type Auth } from 'firebase/auth';
import { initializeFirestore, memoryLocalCache, type Firestore } from 'firebase/firestore';
import { getStorage, type FirebaseStorage } from 'firebase/storage';
import { firebaseOptions, firestoreDatabaseId, isConfigured } from './config';

interface Fb { app: FirebaseApp; auth: Auth; db: Firestore; storage: FirebaseStorage }
let fb: Fb | null = null;

/** Lazily creates the Firebase clients. Only call after checking isConfigured (the App does). */
export function getFb(): Fb {
  if (fb) return fb;
  if (!isConfigured) throw new Error('Firebase is not configured. See README.md, step 4.');
  const app = initializeApp(firebaseOptions);
  const auth = getAuth(app);
  auth.useDeviceLanguage();
  // Memory-only cache on purpose: patient data is never written to the device's disk, because
  // clinic tablets and front-desk PCs are shared. (The original system made the same choice.)
  // Long-polling auto-detect keeps the app working behind strict proxies and in embedded previews.
  const db = initializeFirestore(
    app,
    { localCache: memoryLocalCache(), experimentalAutoDetectLongPolling: true, ignoreUndefinedProperties: true },
    firestoreDatabaseId || undefined
  );
  const storage = getStorage(app);
  fb = { app, auth, db, storage };
  return fb;
}
export const getDb = () => getFb().db;
export const getAuthClient = () => getFb().auth;
export const getStore = () => getFb().storage;
