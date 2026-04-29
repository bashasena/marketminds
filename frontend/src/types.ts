/** Databento OPRA extras (US SPY/QQQ parent symbology); present on USA snapshots when API key is configured. */
export type DatabentoOptionsBlock = {
  source: string;
  dataset: string;
  parent_symbol: string;
  oi_session_date: string;
  nearest_expiry: string | null;
  spot_for_atm: number | null;
  has_quotes: boolean;
  cleared_volume: { call: number; put: number; pcr: number | null } | null;
  oi_weighted_iv: { calls: number | null; puts: number | null } | null;
  atm: {
    strike: number;
    call_iv: number | null;
    put_iv: number | null;
    call_delta: number | null;
    put_delta: number | null;
  } | null;
  official_prices: {
    oi_weighted_close_call: number | null;
    oi_weighted_close_put: number | null;
    oi_weighted_settlement_call: number | null;
    oi_weighted_settlement_put: number | null;
  } | null;
  note: string;
};

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
  /** USA only: extended OPRA statistics (volume, IV, delta) when `DATABENTO_API_KEY` is set */
  databento_options?: DatabentoOptionsBlock | null;
  options: {
    symbol: string;
    expiry: string | null;
    pcr_oi: number | null;
    call_oi_total: number;
    put_oi_total: number;
    resistance_strike_call_oi: number | null;
    support_strike_put_oi: number | null;
    /** Open interest (contracts) at the call wall strike */
    call_wall_oi?: number;
    /** Open interest (contracts) at the put wall strike */
    put_wall_oi?: number;
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
  meta?: {
    data_warnings?: string[];
    market_id?: string;
    ui?: {
      index_title?: string;
      index_subtitle?: string;
      breadth_subtitle?: string;
      movers_subtitle?: string;
      vix_line?: string;
      fii_title?: string;
      show_fii_card?: boolean;
      global_subtitle?: string;
    };
  };
};
