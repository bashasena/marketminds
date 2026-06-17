import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { DashboardTopBar } from "../components/DashboardTopBar";

type MarketFilter = "nasdaq" | "sp500" | "russell" | "both";
type Signal = "bullish" | "bearish" | "neutral";
type SortKey = "volRatio" | "sym" | "pcr" | "curVol" | "signal";
type SortDir = "desc" | "asc";

type StockData = {
  sym: string;
  name: string;
  avg30: number;
  curVol: number;
  volRatio: number;
  pcr: number;
  oiTrend: string;
  signal: Signal;
};

type WatchEntry = {
  sym: string;
  name: string;
  lastCrossed: number;
  lastRatio: number;
  lastChecked: string;
  avg30: number;
  curVol: number;
  pcr: number;
  oiTrend: string;
  signal: Signal;
};

type Toast = { id: number; sym: string; msg: string };
type LogEntry = { time: string; msg: string; type: "info" | "alert" | "warn" };

const POLL_INTERVAL_MS = 5 * 60 * 1000;   // watchlist frontend refresh
const SCAN_INTERVAL_MS = 5 * 60 * 1000;   // scanner auto-refresh

function fmt(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toString();
}

function formatTime(d = new Date()) {
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}

export function VolumeStrategyPage() {
  const [market, setMarket] = useState<MarketFilter>("both");
  const [thresh, setThresh] = useState(1.0);
  const [pcrMin, setPcrMin] = useState(0);
  const [scanning, setScanning] = useState(false);
  const [statusColor, setStatusColor] = useState("#00c896");
  const [alerts, setAlerts] = useState<StockData[]>([]);
  const [metrics, setMetrics] = useState({ scanned: "—", alerts: "—", bull: "—", bear: "—", time: "—" });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [emptyMessage, setEmptyMessage] = useState("Run a scan to detect volume surges");
  const [sortKey, setSortKey] = useState<SortKey>("volRatio");
  const [sortDir, setSortDir] = useState<SortDir>("desc");
  const [showFilters, setShowFilters] = useState(false);
  const [search, setSearch] = useState("");
  const [watchSearch, setWatchSearch] = useState("");
  const [scanCountdown, setScanCountdown] = useState(SCAN_INTERVAL_MS / 1000);
  const scanCountdownRef = useRef(SCAN_INTERVAL_MS / 1000);

  // Server-side watchlist state
  const [watchlist, setWatchlist] = useState<WatchEntry[]>([]);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const [refreshingPcr, setRefreshingPcr] = useState<Set<string>>(new Set());
  const toastCounter = useRef(0);
  const prevWatchRef = useRef<Record<string, number>>({});

  const appendLog = useCallback((msg: string, type: LogEntry["type"] = "info") => {
    setLogs((prev) => [{ time: formatTime(), msg, type }, ...prev].slice(0, 40));
  }, []);

  // ─── Toast helper ────────────────────────────────────────────────────────────

  const showToast = useCallback((sym: string, msg: string) => {
    const id = ++toastCounter.current;
    setToasts((prev) => [...prev, { id, sym, msg }]);
    setTimeout(() => setToasts((prev) => prev.filter((t) => t.id !== id)), 6000);
  }, []);

  // ─── Server-side watchlist fetch ────────────────────────────────────────────

  const fetchWatchlist = useCallback(async () => {
    try {
      const res = await fetch("/volume/alerts", { cache: "no-store" });
      if (!res.ok) return;
      const data = (await res.json()) as { alerts: WatchEntry[] };
      const entries = data.alerts ?? [];

      // Fire in-browser toast when backend detects a new band crossing
      entries.forEach((e) => {
        const prev = prevWatchRef.current[e.sym] ?? 0;
        if (e.lastCrossed > prev && prev > 0) {
          const msg = `${e.sym} volume crossed ${e.lastCrossed}× average!`;
          showToast(e.sym, msg);
          appendLog(`NOTIFY: ${msg}`, "alert");
        }
        prevWatchRef.current[e.sym] = e.lastCrossed;
      });

      setWatchlist(entries);
    } catch {
      // silent
    }
  }, [appendLog, showToast]);

  // Fetch on mount and poll every 5 min
  useEffect(() => {
    void fetchWatchlist();
    const id = setInterval(() => void fetchWatchlist(), POLL_INTERVAL_MS);
    return () => clearInterval(id);
  }, [fetchWatchlist]);

  // ─── Watchlist CRUD ─────────────────────────────────────────────────────────

  const addToWatchlist = useCallback(
    async (s: StockData) => {
      try {
        await fetch("/volume/alerts", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ sym: s.sym, name: s.name, current_ratio: s.volRatio }),
        });
        appendLog(`Watching ${s.sym} — Telegram alerts enabled`, "info");
        await fetchWatchlist();
      } catch {
        appendLog(`Failed to add ${s.sym} to watchlist`, "warn");
      }
    },
    [appendLog, fetchWatchlist],
  );

  const removeFromWatchlist = useCallback(
    async (sym: string) => {
      try {
        await fetch(`/volume/alerts/${encodeURIComponent(sym)}`, { method: "DELETE" });
        delete prevWatchRef.current[sym];
        await fetchWatchlist();
      } catch {
        appendLog(`Failed to remove ${sym} from watchlist`, "warn");
      }
    },
    [appendLog, fetchWatchlist],
  );

  const refreshPcr = useCallback(
    async (sym: string) => {
      setRefreshingPcr((prev) => new Set(prev).add(sym));
      try {
        const res = await fetch(`/volume/pcr/${encodeURIComponent(sym)}`, { cache: "no-store" });
        if (!res.ok) {
          const err = (await res.json().catch(() => ({}))) as { detail?: string };
          throw new Error(err.detail ?? `HTTP ${res.status}`);
        }
        const data = (await res.json()) as {
          sym: string;
          pcr: number;
          oiTrend: string;
          callOi: number;
          putOi: number;
          nearestExpiry: string | null;
        };
        const now = formatTime().slice(0, 5);
        setWatchlist((prev) =>
          prev.map((e) =>
            e.sym === sym
              ? { ...e, pcr: data.pcr, oiTrend: data.oiTrend, lastChecked: now }
              : e,
          ),
        );
        appendLog(
          `${sym} PCR updated: ${data.pcr.toFixed(2)} | ${data.oiTrend} | Call OI ${data.callOi.toLocaleString()} / Put OI ${data.putOi.toLocaleString()}${data.nearestExpiry ? ` (exp ${data.nearestExpiry})` : ""}`,
          "info",
        );
      } catch (err) {
        appendLog(`${sym} PCR refresh failed: ${err instanceof Error ? err.message : String(err)}`, "warn");
      } finally {
        setRefreshingPcr((prev) => {
          const next = new Set(prev);
          next.delete(sym);
          return next;
        });
      }
    },
    [appendLog],
  );

  const isWatched = useCallback((sym: string) => watchlist.some((e) => e.sym === sym), [watchlist]);

  // ─── Scanner ─────────────────────────────────────────────────────────────────

  const runScan = useCallback(async () => {
    // Reset countdown whenever a scan starts (manual or auto)
    scanCountdownRef.current = SCAN_INTERVAL_MS / 1000;
    setScanCountdown(SCAN_INTERVAL_MS / 1000);
    setScanning(true);
    setStatusColor("#f5a623");
    setEmptyMessage(
      market === "russell" ? "Fetching Russell 2000 volume data (~1,900 stocks)…" : "Fetching live volume data...",
    );
    const activeThresh = showFilters ? thresh : 0;
    const activePcrMin = showFilters ? pcrMin : 0;
    appendLog(
      showFilters
        ? `Scan started — market: ${market.toUpperCase()}, threshold: ${thresh}x, PCR min: ${pcrMin}`
        : `Scan started — market: ${market.toUpperCase()} (no filters)`,
      "info",
    );

    try {
      const url = `/volume/scan?market=${encodeURIComponent(market)}&threshold=${activeThresh}&pcr_min=${activePcrMin}`;
      const res = await fetch(url, { cache: "no-store" });
      if (!res.ok) throw new Error(`API error ${res.status}`);
      const data = (await res.json()) as {
        alerts?: StockData[];
        metrics?: Record<string, number>;
        errors?: { sym: string }[];
      };

      const filtered: StockData[] = data.alerts ?? [];
      const m = data.metrics ?? {};
      const tStr = formatTime().slice(0, 5);

      setMetrics({
        scanned: String(m.scanned ?? filtered.length),
        alerts: String(m.alertCount ?? filtered.length),
        bull: String(m.bullish ?? 0),
        bear: String(m.bearish ?? 0),
        time: tStr,
      });
      setAlerts(filtered);
      setStatusColor("#00c896");
      setEmptyMessage(filtered.length === 0 ? `No stocks exceed ${thresh}x volume threshold right now` : "");

      appendLog(`Scan complete — ${m.scanned ?? "?"} with volume, ${filtered.length} shown`, "alert");
      if (m.skippedNoData) {
        appendLog(`${m.skippedNoData} symbol(s) skipped (no volume / delisted)`, "info");
      }
      filtered.forEach((s) =>
        appendLog(`ALERT: ${s.sym} — Vol ${s.volRatio}x avg | PCR ${s.pcr} | ${s.signal.toUpperCase()}`, "warn"),
      );
      if (data.errors?.length) {
        appendLog(`${data.errors.length} symbol(s) failed to fetch`, "info");
      }
    } catch (err) {
      const msg = err instanceof Error ? err.message : String(err);
      appendLog(`Scan failed: ${msg}`, "warn");
      setEmptyMessage("Scan failed — check backend connection");
      setStatusColor("#ff4f4f");
    } finally {
      setScanning(false);
    }
  }, [appendLog, market, pcrMin, thresh]);

  const handleSort = useCallback((key: SortKey) => {
    setSortKey((prev) => {
      if (prev === key) {
        setSortDir((d) => (d === "desc" ? "asc" : "desc"));
        return prev;
      }
      setSortDir("desc");
      return key;
    });
  }, []);

  const sortedAlerts = useMemo(() => {
    const q = search.trim().toLowerCase();
    const signalOrder: Record<Signal, number> = { bullish: 0, neutral: 1, bearish: 2 };
    return [...alerts]
      .filter((a) => !q || a.sym.toLowerCase().includes(q) || a.name.toLowerCase().includes(q))
      .sort((a, b) => {
        let diff = 0;
        if (sortKey === "volRatio") diff = a.volRatio - b.volRatio;
        else if (sortKey === "sym") diff = a.sym.localeCompare(b.sym);
        else if (sortKey === "pcr") diff = a.pcr - b.pcr;
        else if (sortKey === "curVol") diff = a.curVol - b.curVol;
        else if (sortKey === "signal") diff = signalOrder[a.signal] - signalOrder[b.signal];
        return sortDir === "desc" ? -diff : diff;
      });
  }, [alerts, sortKey, sortDir, search]);

  const filteredWatchlist = useMemo(() => {
    const q = watchSearch.trim().toLowerCase();
    return q ? watchlist.filter((e) => e.sym.toLowerCase().includes(q) || e.name.toLowerCase().includes(q)) : watchlist;
  }, [watchlist, watchSearch]);

  // Initial scan on mount
  useEffect(() => {
    void runScan();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps

  // Auto-scan every 5 min + 1-second countdown ticker
  useEffect(() => {
    scanCountdownRef.current = SCAN_INTERVAL_MS / 1000;
    setScanCountdown(SCAN_INTERVAL_MS / 1000);

    // 1-second ticker for the countdown display
    const ticker = setInterval(() => {
      scanCountdownRef.current -= 1;
      setScanCountdown(scanCountdownRef.current);
      if (scanCountdownRef.current <= 0) {
        scanCountdownRef.current = SCAN_INTERVAL_MS / 1000;
        setScanCountdown(SCAN_INTERVAL_MS / 1000);
      }
    }, 1000);

    // Auto-scan trigger
    const scanner = setInterval(() => {
      void runScan();
      scanCountdownRef.current = SCAN_INTERVAL_MS / 1000;
      setScanCountdown(SCAN_INTERVAL_MS / 1000);
    }, SCAN_INTERVAL_MS);

    return () => {
      clearInterval(ticker);
      clearInterval(scanner);
    };
  }, [runScan]);

  const logColor = (type: LogEntry["type"]) =>
    type === "alert" ? "#00c896" : type === "warn" ? "#f5a623" : "#94a3b8";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <DashboardTopBar hideMarket />

      {/* Toast container */}
      <div className="fixed bottom-5 right-5 z-50 flex flex-col gap-2">
        {toasts.map((t) => (
          <div
            key={t.id}
            className="flex items-start gap-2 rounded-lg border border-emerald-500/30 bg-slate-900 px-4 py-3 shadow-lg text-sm text-emerald-300"
          >
            <span>🔔</span>
            <span>{t.msg}</span>
            <button
              type="button"
              onClick={() => setToasts((prev) => prev.filter((x) => x.id !== t.id))}
              className="ml-2 text-slate-500 hover:text-slate-200 text-xs"
            >
              ✕
            </button>
          </div>
        ))}
      </div>

      <div className="mx-auto max-w-6xl px-4 py-10 pb-16">
        <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
          <Link to="/" className="text-xs text-slate-400 hover:text-slate-200">
            ← Back to dashboard
          </Link>
        </div>

        {/* ─── Telegram channel info banner ─────────────────────────────────── */}
        <div className="mb-6 flex flex-col gap-3 rounded-xl border border-sky-500/20 bg-sky-500/5 px-5 py-4 sm:flex-row sm:items-center sm:justify-between">
          <div className="flex items-start gap-3">
            <span className="mt-0.5 text-2xl">📣</span>
            <div>
              <p className="text-sm font-semibold text-sky-300">Get live volume alerts on Telegram</p>
              <p className="mt-0.5 text-xs text-slate-400">
                Join our channel to receive push notifications whenever a stock crosses a new volume threshold.
                <br className="hidden sm:block" />
                You can also add your own watch alerts from the scanner below — they'll post to this channel.
              </p>
            </div>
          </div>
          <a
            href="https://t.me/trader_mind_alert"
            target="_blank"
            rel="noopener noreferrer"
            className="flex shrink-0 items-center gap-2 rounded-lg border border-sky-500/40 bg-sky-500/15 px-4 py-2 text-sm font-semibold text-sky-300 transition-colors hover:bg-sky-500/25"
          >
            <svg className="h-4 w-4" viewBox="0 0 24 24" fill="currentColor">
              <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248-2.012 9.483c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L7.19 14.447l-2.95-.924c-.64-.204-.654-.64.136-.948l11.52-4.44c.537-.194 1.006.131.666.113z"/>
            </svg>
            Join @trader_mind_alert
          </a>
        </div>

        <div className="volume-scanner">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: statusColor, boxShadow: `0 0 0 0 ${statusColor}80`, animation: "pulse 1.6s ease-in-out infinite" }}
              />
              <h1 className="text-lg font-medium tracking-tight text-white">Volume Surge Scanner</h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value as MarketFilter)}
                className="rounded-md border border-slate-600 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
              >
                <option value="nasdaq">NASDAQ 100</option>
                <option value="sp500">S&amp;P 500</option>
                <option value="russell">Russell 2000 (IWM)</option>
                <option value="both">NASDAQ + S&amp;P 500</option>
              </select>
              {market === "russell" ? (
                <span className="text-[11px] text-slate-500">
                  ~1,900 stocks · scan may take a few minutes · PCR via + Alert / watchlist
                </span>
              ) : null}
              <button
                type="button"
                onClick={() => void runScan()}
                disabled={scanning}
                className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-sm font-medium text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-60"
              >
                {scanning ? "Scanning…" : "Scan Now"}
              </button>
              {!scanning && (
                <span className="text-[11px] text-slate-500 tabular-nums">
                  next in {Math.floor(scanCountdown / 60)}:{String(scanCountdown % 60).padStart(2, "0")}
                </span>
              )}
              <label className="flex cursor-pointer items-center gap-1.5 text-xs text-slate-400 select-none">
                <input
                  type="checkbox"
                  checked={showFilters}
                  onChange={(e) => { setShowFilters(e.target.checked); setTimeout(() => void runScan(), 0); }}
                  className="h-3.5 w-3.5 accent-emerald-500"
                />
                Filters
              </label>
            </div>
          </div>

          {showFilters && (
            <div className="mb-6 flex flex-wrap items-center gap-3 text-sm text-slate-400">
              <label>Volume threshold:</label>
              <input
                type="range"
                min={1}
                max={5}
                step={0.1}
                value={thresh}
                onChange={(e) => setThresh(parseFloat(e.target.value))}
                className="w-36"
              />
              <span className="font-mono text-sm font-medium text-emerald-400">{thresh.toFixed(1)}x</span>
              <label className="ml-3">Min PCR filter:</label>
              <input
                type="range"
                min={0}
                max={5}
                step={0.1}
                value={pcrMin}
                onChange={(e) => setPcrMin(parseFloat(e.target.value))}
                className="w-36"
              />
              <span className="font-mono text-sm font-medium text-emerald-400">{pcrMin.toFixed(1)}</span>
            </div>
          )}

          {/* ─── Alert Watchlist (server-side) ────────────────────────────── */}
          {watchlist.length > 0 && (
            <div className="mb-8">
              <div className="mb-2.5 flex flex-wrap items-center justify-between gap-2">
                <p className="text-xs font-medium uppercase tracking-wide text-slate-400">
                  🔔 Alert Watchlist
                  <span className="ml-2 rounded-full bg-emerald-500/20 px-2 py-0.5 text-[10px] text-emerald-400">
                    live refresh every 5 min
                  </span>
                  <span className="ml-1.5 rounded-full bg-slate-700 px-2 py-0.5 text-[10px] text-slate-300">
                    {watchlist.length} watching
                  </span>
                </p>
                {/* Watchlist search */}
                <div className="relative">
                  <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-slate-500">
                    <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                      <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                    </svg>
                  </span>
                  <input
                    type="text"
                    value={watchSearch}
                    onChange={(e) => setWatchSearch(e.target.value)}
                    placeholder="Filter watchlist…"
                    className="rounded-md border border-slate-700 bg-slate-900 py-1.5 pl-8 pr-3 text-xs text-slate-100 placeholder-slate-500 focus:border-emerald-500/50 focus:outline-none w-44"
                  />
                  {watchSearch && (
                    <button
                      type="button"
                      onClick={() => setWatchSearch("")}
                      className="absolute inset-y-0 right-2 flex items-center text-slate-500 hover:text-slate-200"
                    >
                      ✕
                    </button>
                  )}
                </div>
              </div>
              {/* Watchlist header */}
              <div className="mb-1 grid grid-cols-[70px_1fr_90px_90px_90px_90px_90px_100px] gap-2.5 px-3.5 text-xs font-medium text-slate-500">
                <span>SYMBOL</span>
                <span>VOLUME vs 30D AVG</span>
                <span>PCR</span>
                <span>VOL RATIO</span>
                <span>OI TREND</span>
                <span>SIGNAL</span>
                <span>REFRESH</span>
                <span>REMOVE</span>
              </div>
              <div className="flex flex-col gap-2">
                {filteredWatchlist.length === 0 ? (
                  <div className="rounded-lg border border-dashed border-slate-700 py-4 text-center text-xs text-slate-500">
                    No watchlist entries match "{watchSearch}"
                  </div>
                ) : (
                  filteredWatchlist.map((entry) => {
                    const scale = Math.max(entry.curVol, entry.avg30) || 1;
                    const dailyPct = Math.round((entry.curVol / scale) * 100);
                    const avgPct = Math.round((entry.avg30 / scale) * 100);
                    const dailyColor =
                      entry.signal === "bullish" ? "#00c896" : entry.signal === "bearish" ? "#ff4f4f" : "#f5a623";
                    const pcrClass = entry.pcr < 0.8 ? "bull" : entry.pcr > 1.3 ? "bear" : "neut";
                    const pcrLabel = entry.pcr < 0.8 ? "Bullish" : entry.pcr > 1.3 ? "Bearish" : "Neutral";
                    const oiColor =
                      entry.oiTrend === "Rising" ? "#00c896" : entry.oiTrend === "Falling" ? "#ff4f4f" : "#94a3b8";
                    return (
                      <div
                        key={entry.sym}
                        className={`grid grid-cols-[70px_1fr_90px_90px_90px_90px_90px_100px] items-center gap-2.5 rounded-lg border border-slate-700 bg-slate-900/60 px-3.5 py-2.5 border-l-[3px] ${
                          entry.signal === "bullish"
                            ? "border-l-emerald-500"
                            : entry.signal === "bearish"
                              ? "border-l-red-500"
                              : "border-l-amber-500"
                        }`}
                      >
                        <div className="flex flex-col">
                          <span className="font-mono text-sm font-semibold">{entry.sym}</span>
                          <span className="text-[10px] text-slate-500">{entry.lastChecked}</span>
                        </div>
                        <div className="flex flex-col gap-1.5">
                          <div className="flex items-center gap-1.5">
                            <span className="w-[34px] shrink-0 font-mono text-[10px] text-slate-400">Daily</span>
                            <div className="relative h-2 flex-1 overflow-hidden rounded-sm bg-slate-800">
                              <div className="h-full rounded-sm transition-all duration-500" style={{ width: `${dailyPct}%`, background: dailyColor }} />
                            </div>
                            <span className="w-[36px] shrink-0 text-right font-mono text-[10px]" style={{ color: dailyColor }}>{fmt(entry.curVol)}</span>
                          </div>
                          <div className="flex items-center gap-1.5">
                            <span className="w-[34px] shrink-0 font-mono text-[10px] text-slate-500">30D avg</span>
                            <div className="relative h-2 flex-1 overflow-hidden rounded-sm bg-slate-800">
                              <div className="h-full rounded-sm bg-slate-600 transition-all duration-500" style={{ width: `${avgPct}%` }} />
                            </div>
                            <span className="w-[36px] shrink-0 text-right font-mono text-[10px] text-slate-500">{fmt(entry.avg30)}</span>
                          </div>
                        </div>
                        <span className={`rounded px-2 py-1 text-center font-mono text-xs font-medium ${pcrClass === "bull" ? "bg-emerald-500/10 text-emerald-400" : pcrClass === "bear" ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"}`}>
                          {entry.pcr.toFixed(2)}
                          <br />
                          <span className="text-[10px] opacity-70">{pcrLabel}</span>
                        </span>
                        <span className={`text-center font-mono text-sm font-semibold ${entry.lastRatio >= 2.5 ? "text-emerald-400" : "text-amber-400"}`}>
                          {entry.lastRatio.toFixed(2)}x
                        </span>
                        <span className="text-center text-xs font-medium" style={{ color: oiColor }}>{entry.oiTrend}</span>
                        <span className={`rounded-full px-2 py-0.5 text-center text-[11px] font-medium ${entry.signal === "bullish" ? "bg-emerald-500/10 text-emerald-400" : entry.signal === "bearish" ? "bg-red-500/10 text-red-400" : "bg-amber-500/10 text-amber-400"}`}>
                          {entry.signal.charAt(0).toUpperCase() + entry.signal.slice(1)}
                        </span>
                        {/* Update PCR button */}
                        <button
                          type="button"
                          disabled={refreshingPcr.has(entry.sym)}
                          onClick={() => void refreshPcr(entry.sym)}
                          title="Fetch latest PCR for this symbol"
                          className="flex items-center justify-center gap-1 rounded-md border border-sky-500/30 bg-sky-500/10 px-2 py-1 text-[11px] font-medium text-sky-400 hover:bg-sky-500/20 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
                        >
                          <span
                            className={refreshingPcr.has(entry.sym) ? "animate-spin inline-block" : "inline-block"}
                            style={{ display: "inline-block" }}
                          >
                            ↻
                          </span>
                          {refreshingPcr.has(entry.sym) ? "…" : "PCR"}
                        </button>
                        {/* Remove button */}
                        <button
                          type="button"
                          onClick={() => void removeFromWatchlist(entry.sym)}
                          className="rounded-md border border-red-500/30 bg-red-500/10 px-2 py-1 text-[11px] font-medium text-red-400 hover:bg-red-500/20 transition-colors"
                        >
                          Remove
                        </button>
                      </div>
                    );
                  })
                )}
              </div>
            </div>
          )}

          {/* ─── Metrics ──────────────────────────────────────────────────────── */}
          <div className="mb-6 grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-2.5">
            {[
              ["Stocks Scanned", metrics.scanned, ""],
              ["Alerts Fired", metrics.alerts, "text-emerald-400"],
              ["Bullish Signals", metrics.bull, "text-emerald-400"],
              ["Bearish Signals", metrics.bear, "text-red-400"],
              ["Last Scan", metrics.time, "text-sm"],
            ].map(([label, val, cls]) => (
              <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                <p className="text-xs text-slate-500">{label}</p>
                <p className={`mt-1 font-mono text-xl font-medium text-white ${cls}`}>{val}</p>
              </div>
            ))}
          </div>

          {/* ─── Results table ────────────────────────────────────────────────── */}
          <div className="mb-3 flex items-center justify-between gap-3">
            <p className="text-xs font-medium uppercase tracking-wide text-slate-500">Alert Results</p>
            <div className="relative">
              <span className="pointer-events-none absolute inset-y-0 left-2.5 flex items-center text-slate-500">
                <svg className="h-3.5 w-3.5" fill="none" stroke="currentColor" strokeWidth="2" viewBox="0 0 24 24">
                  <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
                </svg>
              </span>
              <input
                type="text"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
                placeholder="Search symbol or name…"
                className="rounded-md border border-slate-700 bg-slate-900 py-1.5 pl-8 pr-3 text-xs text-slate-100 placeholder-slate-500 focus:border-emerald-500/50 focus:outline-none w-52"
              />
              {search && (
                <button
                  type="button"
                  onClick={() => setSearch("")}
                  className="absolute inset-y-0 right-2 flex items-center text-slate-500 hover:text-slate-200"
                >
                  ✕
                </button>
              )}
            </div>
          </div>
          <div className="mb-1 grid grid-cols-[70px_1fr_90px_90px_90px_90px_70px] gap-2.5 px-3.5 text-xs font-medium text-slate-500">
            {(
              [
                ["sym", "SYMBOL"],
                [null, "VOLUME vs 30D AVG"],
                ["pcr", "PCR"],
                ["volRatio", "VOL RATIO"],
                [null, "OI TREND"],
                ["signal", "SIGNAL"],
                [null, "ALERT"],
              ] as [SortKey | null, string][]
            ).map(([key, label]) =>
              key ? (
                <button
                  key={label}
                  type="button"
                  onClick={() => handleSort(key)}
                  className="flex items-center gap-1 text-left hover:text-slate-200 transition-colors"
                >
                  {label}
                  <span className="font-mono text-[10px]">
                    {sortKey === key ? (sortDir === "desc" ? "↓" : "↑") : "↕"}
                  </span>
                </button>
              ) : (
                <span key={label}>{label}</span>
              )
            )}
          </div>

          {sortedAlerts.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-700 py-8 text-center text-sm text-slate-400">
              {search.trim()
                ? `No results matching "${search.trim()}" — try a different symbol or name`
                : emptyMessage}
            </div>
          ) : (
            <div className="mb-6 flex flex-col gap-2">
              {sortedAlerts.map((s, i) => {
                const scale = Math.max(s.curVol, s.avg30) || 1;
                const dailyPct = Math.round((s.curVol / scale) * 100);
                const avgPct = Math.round((s.avg30 / scale) * 100);
                const dailyColor =
                  s.signal === "bullish" ? "#00c896" : s.signal === "bearish" ? "#ff4f4f" : "#f5a623";
                const pcrUnavailable = s.pcr <= 0 || s.oiTrend === "N/A";
                const pcrClass = pcrUnavailable ? "neut" : s.pcr < 0.8 ? "bull" : s.pcr > 1.3 ? "bear" : "neut";
                const pcrLabel = pcrUnavailable ? "N/A" : s.pcr < 0.8 ? "Bullish" : s.pcr > 1.3 ? "Bearish" : "Neutral";
                const oiColor =
                  s.oiTrend === "Rising" ? "#00c896" : s.oiTrend === "Falling" ? "#ff4f4f" : "#94a3b8";
                const watched = isWatched(s.sym);
                return (
                  <div
                    key={`${s.sym}-${i}`}
                    className={`grid grid-cols-[70px_1fr_90px_90px_90px_90px_70px] items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/40 px-3.5 py-2.5 border-l-[3px] ${
                      s.signal === "bullish"
                        ? "border-l-emerald-500"
                        : s.signal === "bearish"
                          ? "border-l-red-500"
                          : "border-l-amber-500"
                    }`}
                  >
                    <span className="font-mono text-sm font-semibold">{s.sym}</span>
                    <div className="flex flex-col gap-1.5">
                      <div className="flex items-center gap-1.5">
                        <span className="w-[34px] shrink-0 font-mono text-[10px] text-slate-400">Daily</span>
                        <div className="relative h-2 flex-1 overflow-hidden rounded-sm bg-slate-800">
                          <div
                            className="h-full rounded-sm transition-all duration-500"
                            style={{ width: `${dailyPct}%`, background: dailyColor }}
                          />
                        </div>
                        <span className="w-[36px] shrink-0 text-right font-mono text-[10px]" style={{ color: dailyColor }}>
                          {fmt(s.curVol)}
                        </span>
                      </div>
                      <div className="flex items-center gap-1.5">
                        <span className="w-[34px] shrink-0 font-mono text-[10px] text-slate-500">30D avg</span>
                        <div className="relative h-2 flex-1 overflow-hidden rounded-sm bg-slate-800">
                          <div
                            className="h-full rounded-sm bg-slate-600 transition-all duration-500"
                            style={{ width: `${avgPct}%` }}
                          />
                        </div>
                        <span className="w-[36px] shrink-0 text-right font-mono text-[10px] text-slate-500">
                          {fmt(s.avg30)}
                        </span>
                      </div>
                    </div>
                    <span
                      className={`rounded px-2 py-1 text-center font-mono text-xs font-medium ${
                        pcrClass === "bull"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : pcrClass === "bear"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {pcrUnavailable ? "—" : s.pcr}
                      <br />
                      <span className="text-[10px] opacity-70">{pcrLabel}</span>
                    </span>
                    <span
                      className={`text-center font-mono text-sm font-semibold ${s.volRatio >= 2.5 ? "text-emerald-400" : "text-amber-400"}`}
                    >
                      {s.volRatio}x
                    </span>
                    <span className="text-center text-xs font-medium" style={{ color: oiColor }}>
                      {s.oiTrend}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-center text-[11px] font-medium ${
                        s.signal === "bullish"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : s.signal === "bearish"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {s.signal.charAt(0).toUpperCase() + s.signal.slice(1)}
                    </span>
                    <button
                      type="button"
                      onClick={() => (watched ? void removeFromWatchlist(s.sym) : void addToWatchlist(s))}
                      title={watched ? "Remove alert" : "Add alert"}
                      className={`rounded-md px-2 py-1 text-[11px] font-medium transition-colors ${
                        watched
                          ? "border border-emerald-500/40 bg-emerald-500/15 text-emerald-400 hover:bg-red-500/15 hover:text-red-400 hover:border-red-500/40"
                          : "border border-slate-600 bg-slate-800 text-slate-400 hover:border-emerald-500/40 hover:bg-emerald-500/10 hover:text-emerald-400"
                      }`}
                    >
                      {watched ? "🔔 On" : "+ Alert"}
                    </button>
                  </div>
                );
              })}
            </div>
          )}

          {/* ─── Activity Log ─────────────────────────────────────────────────── */}
          <p className="mb-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Activity Log</p>
          <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/40 p-3">
            {logs.length === 0 ? (
              <p className="font-mono text-xs text-slate-500">Waiting for scan...</p>
            ) : (
              logs.map((entry, i) => (
                <div key={i} className="border-b border-slate-800 py-1 font-mono text-xs last:border-b-0">
                  <span className="mr-2 text-emerald-400">{entry.time}</span>
                  <span style={{ color: logColor(entry.type) }}>{entry.msg}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(0, 200, 150, 0.5); }
          50% { box-shadow: 0 0 0 5px rgba(0, 200, 150, 0); }
        }
      `}</style>
    </div>
  );
}
