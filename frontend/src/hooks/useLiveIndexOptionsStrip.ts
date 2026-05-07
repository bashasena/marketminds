import { useCallback, useEffect, useMemo, useState } from "react";
import type { MarketId } from "../market/types";
import type { Snapshot } from "../types";
import { mergeIndexOptionsFromLive } from "../components/dashboard/mergeIndexOptions";

const STORAGE_PREFIX = "dashboard_strip_live_v1_";

function readPref(market: MarketId): boolean {
  try {
    return sessionStorage.getItem(STORAGE_PREFIX + market) === "1";
  } catch {
    return false;
  }
}

function persistPref(market: MarketId, v: boolean) {
  try {
    sessionStorage.setItem(STORAGE_PREFIX + market, v ? "1" : "0");
  } catch {
    /* ignore */
  }
}

export function useLiveIndexOptionsStrip(market: MarketId, base: Snapshot) {
  const [liveOn, setLiveOnState] = useState(() => readPref(market));
  const [overlay, setOverlay] = useState<Snapshot | null>(null);
  const [liveErr, setLiveErr] = useState<string | null>(null);
  const [polling, setPolling] = useState(false);

  useEffect(() => {
    setLiveOnState(readPref(market));
    setOverlay(null);
    setLiveErr(null);
  }, [market]);

  const setLiveOn = useCallback(
    (v: boolean) => {
      setLiveOnState(v);
      persistPref(market, v);
      if (!v) {
        setOverlay(null);
        setLiveErr(null);
      }
    },
    [market],
  );

  useEffect(() => {
    if (!liveOn) return;

    let cancelled = false;

    const tick = async () => {
      setPolling(true);
      try {
        const r = await fetch(
          `/snapshot/today?market=${encodeURIComponent(market)}&live=true&strip=true`,
          { cache: "no-store" },
        );
        if (!r.ok) {
          if (!cancelled) setLiveErr(`${r.status} ${r.statusText}`);
          return;
        }
        const j = (await r.json()) as Snapshot;
        if (!cancelled) {
          setOverlay(j);
          setLiveErr(null);
        }
      } catch (e) {
        if (!cancelled) setLiveErr(e instanceof Error ? e.message : "Live fetch failed");
      } finally {
        if (!cancelled) setPolling(false);
      }
    };

    void tick();
    const id = window.setInterval(tick, 15_000);
    return () => {
      cancelled = true;
      window.clearInterval(id);
    };
  }, [liveOn, market]);

  const stripSnapshot = useMemo(
    () => (liveOn && overlay ? mergeIndexOptionsFromLive(base, overlay) : base),
    [liveOn, overlay, base],
  );

  return { liveOn, setLiveOn, stripSnapshot, liveErr, polling };
}
