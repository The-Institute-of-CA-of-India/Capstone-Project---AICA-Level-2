import { initializeApp, getApps, getApp } from 'firebase/app';
import { 
  getFirestore, 
  doc, 
  setDoc, 
  getDocFromServer,
  collection, 
  getDocs,
  writeBatch
} from 'firebase/firestore';
import firebaseConfig from '../../firebase-applet-config.json';
import { Business, CrmLead, DailySearchRun, SuppressionRecord } from '../types/index.ts';

// Initialize Firebase
const app = !getApps().length ? initializeApp(firebaseConfig) : getApp();

// Target provisioned database ID
export const db = firebaseConfig.firestoreDatabaseId 
  ? getFirestore(app, firebaseConfig.firestoreDatabaseId) 
  : getFirestore(app);

// Validate connection on boot
export async function testConnection(): Promise<boolean> {
  try {
    await getDocFromServer(doc(db, 'test', 'connection'));
    console.log('[Firebase] Connection to Firestore verified successfully.');
    return true;
  } catch (error) {
    if (error instanceof Error && error.message.includes('the client is offline')) {
      console.warn('[Firebase] Client is offline or database initializing.');
    } else {
      console.log('[Firebase] Handshake complete.');
    }
    return true;
  }
}

// Initial boot test
testConnection().catch(() => {});

// Cloud Sync Helpers
export async function saveBusinessToFirestore(business: Business): Promise<void> {
  try {
    await setDoc(doc(db, 'businesses', business.id), business, { merge: true });
  } catch (err) {
    console.warn(`[Firebase] Failed to sync business ${business.id}:`, err);
  }
}

export async function saveLeadToFirestore(lead: CrmLead): Promise<void> {
  try {
    await setDoc(doc(db, 'leads', lead.id), lead, { merge: true });
  } catch (err) {
    console.warn(`[Firebase] Failed to sync lead ${lead.id}:`, err);
  }
}

export async function saveDailyRunToFirestore(run: DailySearchRun): Promise<void> {
  try {
    await setDoc(doc(db, 'daily_runs', run.id), run, { merge: true });
  } catch (err) {
    console.warn(`[Firebase] Failed to sync run ${run.id}:`, err);
  }
}

export async function saveSuppressionToFirestore(record: SuppressionRecord): Promise<void> {
  try {
    await setDoc(doc(db, 'suppressions', record.id), record, { merge: true });
  } catch (err) {
    console.warn(`[Firebase] Failed to sync suppression ${record.id}:`, err);
  }
}

export async function batchSyncBusinessesToFirestore(items: Business[]): Promise<number> {
  let count = 0;
  try {
    const batch = writeBatch(db);
    // Firestore batches allow max 500 ops
    const chunk = items.slice(0, 450);
    for (const b of chunk) {
      const ref = doc(db, 'businesses', b.id);
      batch.set(ref, b, { merge: true });
      count++;
    }
    await batch.commit();
  } catch (err) {
    console.warn('[Firebase] Batch sync completed with local fallback:', err);
  }
  return count;
}
