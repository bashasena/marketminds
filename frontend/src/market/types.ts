/** Extend as you add pipelines (e.g. us_spy) and wire snapshot builders per id. */
export type MarketId = "in_nifty" | "us_broad" | "usa_nasdaq";

export type MarketOption = {
  id: MarketId;
  label: string;
  shortLabel: string;
  /** Snapshot API is implemented for this market (other UIs may show a placeholder). */
  snapshotReady: boolean;
};

export const MARKETS: MarketOption[] = [
  { id: "in_nifty", label: "India — Nifty 50", shortLabel: "India", snapshotReady: true },
  { id: "us_broad", label: "USA — S&P 500 (broad)", shortLabel: "USA S&P", snapshotReady: true },
  { id: "usa_nasdaq", label: "USA — NASDAQ", shortLabel: "NASDAQ", snapshotReady: true },
];

export const DEFAULT_MARKET: MarketId = "in_nifty";

export const MARKET_STORAGE_KEY = "market_snapshot_market_v1";
