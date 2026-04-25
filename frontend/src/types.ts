export type Snapshot = {
  snapshot_date: string;
  generated_at_utc?: string | null;
  header: { title: string; date: string };
  index: {
    name: string;
    open: number | null;
    high: number | null;
    low: number | null;
    close: number | null;
    pct_change: number | null;
    advances: number;
    declines: number;
    unchanged: number;
    narrative: string;
  };
  breadth: { advances: number; declines: number; unchanged: number };
  top_movers: {
    gainers: { symbol: string; pct_change: number; last_price: number | null }[];
    losers: { symbol: string; pct_change: number; last_price: number | null }[];
  };
  technical: {
    pivot: number | null;
    s1: number | null;
    s2: number | null;
    r1: number | null;
    r2: number | null;
    prev_ohlc: { o: number; h: number; l: number; c: number } | null;
    note: string;
  };
  vix: { level: number | null; pct_change: number | null };
  fii_dii: {
    as_of: string | null;
    fii_net_crores: number | null;
    dii_net_crores: number | null;
    note: string;
  };
  options: {
    symbol: string;
    expiry: string | null;
    pcr_oi: number | null;
    call_oi_total: number;
    put_oi_total: number;
    resistance_strike_call_oi: number | null;
    support_strike_put_oi: number | null;
    note: string;
  };
  global: Record<
    string,
    { symbol: string; label: string; last: number | null; pct_change: number | null; currency: string | null }
  >;
  global_note: string;
  composite: {
    score_0_100: number;
    label: string;
    components: Record<string, number>;
    weights: Record<string, number>;
    explanation: string;
  };
  x_sentiment_summary: {
    aggregate_0_100: number;
    tweet_count: number;
    model: string;
    error: string | null;
  };
  meta?: { data_warnings?: string[] };
};
