/**
 * IndexedDB service for offline-first crowd reporting.
 *
 * Edge 5.9: Timestamp-based conflict resolution with "last write wins" strategy.
 * Reports are stored locally and synced when connectivity is restored.
 */

import { openDB } from 'idb';

const DB_NAME = 'locats-reports';
const DB_VERSION = 1;
const STORE_NAME = 'reports';

let db = null;

export async function initDB() {
  db = await openDB(DB_NAME, DB_VERSION, {
    upgrade(database) {
      if (!database.objectStoreNames.contains(STORE_NAME)) {
        const store = database.createObjectStore(STORE_NAME, { keyPath: 'id' });
        store.createIndex('sync_status', 'sync_status');
        store.createIndex('timestamp', 'timestamp');
        store.createIndex('client_timestamp', 'client_timestamp');
      }
    },
  });
}

export async function saveReport(report) {
  if (!db) await initDB();

  const tx = db.transaction(STORE_NAME, 'readwrite');
  const store = tx.objectStore(STORE_NAME);

  // Edge 5.9: Check for conflicts with existing reports
  const existingReports = await store.index('timestamp').getAll();
  const conflicting = existingReports.filter(
    (r) =>
      r.reporter_id === report.reporter_id &&
      r.hazard_type === report.hazard_type &&
      Math.abs(r.client_timestamp - report.client_timestamp) < 60000 // within 60s
  );

  if (conflicting.length > 0) {
    // Last write wins (edge 5.9)
    for (const old of conflicting) {
      if (report.client_timestamp >= old.client_timestamp) {
        await store.delete(old.id);
      } else {
        // Old report wins, don't save new one
        await tx.done;
        return { status: 'conflict_resolved', resolution: 'old_write_wins' };
      }
    }
  }

  await store.put(report);
  await tx.done;

  // Try to sync if online
  if (navigator.onLine) {
    await syncSingleReport(report);
  }

  return { status: 'saved', sync_status: report.sync_status };
}

export async function getAllReports() {
  if (!db) await initDB();
  const tx = db.transaction(STORE_NAME, 'readonly');
  const store = tx.objectStore(STORE_NAME);
  return store.getAll();
}

export async function getSyncStatus() {
  if (!db) await initDB();
  const all = await getAllReports();
  return {
    pending: all.filter((r) => r.sync_status === 'pending').length,
    synced: all.filter((r) => r.sync_status === 'synced').length,
    conflict: all.filter((r) => r.sync_status === 'conflict').length,
  };
}

export async function syncReports() {
  if (!db || !navigator.onLine) return;

  const all = await getAllReports();
  const pending = all.filter((r) => r.sync_status === 'pending');

  for (const report of pending) {
    await syncSingleReport(report);
  }
}

async function syncSingleReport(report) {
  try {
    const payload = {
      reporter_id: report.reporter_id,
      hazard_type: report.hazard_type,
      severity_estimate: report.severity_estimate,
      description: report.description || '',
      lat: report.location?.lat || 0,
      lon: report.location?.lon || 0,
    };

    const res = await fetch('/api/hazard/crowd-report', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload),
    });

    if (res.ok) {
      // Mark as synced
      const tx = db.transaction(STORE_NAME, 'readwrite');
      const store = tx.objectStore(STORE_NAME);
      const existing = await store.get(report.id);
      if (existing) {
        existing.sync_status = 'synced';
        await store.put(existing);
      }
      await tx.done;
    }
  } catch (err) {
    // Will retry on next sync attempt
    console.log('Sync failed, will retry:', err.message);
  }
}
