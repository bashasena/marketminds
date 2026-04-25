import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { DEFAULT_MARKET, MARKET_STORAGE_KEY, type MarketId } from "./types";

function readStoredMarket(): MarketId {
  try {
    const raw = localStorage.getItem(MARKET_STORAGE_KEY);
    if (raw === "in_nifty" || raw === "us_broad") return raw;
  } catch {
    /* ignore */
  }
  return DEFAULT_MARKET;
}

function persistMarket(id: MarketId) {
  try {
    localStorage.setItem(MARKET_STORAGE_KEY, id);
  } catch {
    /* ignore */
  }
}

type MarketContextValue = {
  market: MarketId;
  setMarket: (id: MarketId) => void;
};

const MarketContext = createContext<MarketContextValue | null>(null);

export function MarketProvider({ children }: { children: ReactNode }) {
  const [market, setMarketState] = useState<MarketId>(() => readStoredMarket());

  const setMarket = useCallback((id: MarketId) => {
    setMarketState(id);
    persistMarket(id);
  }, []);

  const value = useMemo(() => ({ market, setMarket }), [market, setMarket]);

  return <MarketContext.Provider value={value}>{children}</MarketContext.Provider>;
}

export function useMarket(): MarketContextValue {
  const ctx = useContext(MarketContext);
  if (!ctx) {
    throw new Error("useMarket must be used within MarketProvider");
  }
  return ctx;
}
