/**
 * Where the Firebase web-app settings come from (first match wins):
 *   1. VITE_FIREBASE_* environment variables  (.env.local, or your host's build settings)
 *   2. src/config/firebase.config.json        (copy firebase.config.example.json and fill it in)
 *   3. firebase-applet-config.json in the project root (if your AI Studio Firebase integration creates one)
 *
 * These values identify YOUR Firebase project to the browser. They are not secrets - what protects
 * your data is Authentication plus the Firestore/Storage rules in this repo. No project ID, API key
 * or other credential is included in this code base.
 */
import type { FirebaseOptions } from 'firebase/app';

type Raw = Record<string, string | undefined>;

const files = import.meta.glob(['../config/firebase.config.json', '/firebase-applet-config.json'], {
  eager: true,
  import: 'default'
}) as Record<string, Raw>;
const fromFile: Raw = Object.values(files)[0] || {};
const env = import.meta.env as Record<string, string | undefined>;

const pick = (envKey: string, fileKey: string) => (env[envKey] || fromFile[fileKey] || '').trim();

export const firebaseOptions: FirebaseOptions = {
  apiKey: pick('VITE_FIREBASE_API_KEY', 'apiKey'),
  authDomain: pick('VITE_FIREBASE_AUTH_DOMAIN', 'authDomain'),
  projectId: pick('VITE_FIREBASE_PROJECT_ID', 'projectId'),
  storageBucket: pick('VITE_FIREBASE_STORAGE_BUCKET', 'storageBucket'),
  messagingSenderId: pick('VITE_FIREBASE_MESSAGING_SENDER_ID', 'messagingSenderId'),
  appId: pick('VITE_FIREBASE_APP_ID', 'appId')
};
/** Optional named Firestore database. Empty = the "(default)" database. */
export const firestoreDatabaseId = pick('VITE_FIREBASE_FIRESTORE_DB_ID', 'firestoreDatabaseId');

const PLACEHOLDER = /^(your|xxx|todo|changeme|<)/i;
export const missingConfig: string[] = (
  [['apiKey', 'VITE_FIREBASE_API_KEY'], ['authDomain', 'VITE_FIREBASE_AUTH_DOMAIN'], ['projectId', 'VITE_FIREBASE_PROJECT_ID'],
   ['storageBucket', 'VITE_FIREBASE_STORAGE_BUCKET'], ['appId', 'VITE_FIREBASE_APP_ID']] as const
).filter(([k]) => {
  const v = (firebaseOptions as Record<string, string | undefined>)[k] || '';
  return !v || PLACEHOLDER.test(v);
}).map(([, e]) => e);

export const isConfigured = missingConfig.length === 0;
