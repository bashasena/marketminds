import type { Snapshot } from "./types";

export const SNAPSHOT_STORAGE_KEY = "market_snapshot_cache_v1";

export function readStoredSnapshot(): Snapshot | null {
  try {
    const raw = localStorage.getItem(SNAPSHOT_STORAGE_KEY);
    if (!raw) return null;
    return JSON.parse(raw) as Snapshot;
  } catch {
    return null;
  }
}

export function persistSnapshot(s: Snapshot) {
  try {
    localStorage.setItem(SNAPSHOT_STORAGE_KEY, JSON.stringify(s));
  } catch {
    /* ignore quota / private mode */
  }
}
