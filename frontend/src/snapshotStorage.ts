import type { MarketId } from "./market/types";
import type { Snapshot } from "./types";

const LEGACY_KEY = "market_snapshot_cache_v1";

export function storageKeyForMarket(m: MarketId): string {
  return `market_snapshot_cache_v1_${m}`;
}

export function readStoredSnapshot(market: MarketId): Snapshot | null {
  try {
    const key = storageKeyForMarket(market);
    let raw = localStorage.getItem(key);
    if (!raw && market === "in_nifty") {
      raw = localStorage.getItem(LEGACY_KEY);
      if (raw) {
        localStorage.setItem(key, raw);
        localStorage.removeItem(LEGACY_KEY);
      }
    }
    if (!raw) return null;
    return JSON.parse(raw) as Snapshot;
  } catch {
    return null;
  }
}

export function persistSnapshot(s: Snapshot, market: MarketId) {
  try {
    localStorage.setItem(storageKeyForMarket(market), JSON.stringify(s));
  } catch {
    /* ignore */
  }
}
