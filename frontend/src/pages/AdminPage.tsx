import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { useMarket } from "../market/MarketContext";
import { MARKETS } from "../market/types";
import type { Snapshot } from "../types";
import { persistSnapshot, readStoredSnapshot } from "../snapshotStorage";

export function AdminPage() {
  const { market, setMarket } = useMarket();
  const [fromDb, setFromDb] = useState<Snapshot | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshErr, setRefreshErr] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<string | null>(null);
  const [xSyncing, setXSyncing] = useState(false);
  const [xErr, setXErr] = useState<string | null>(null);
  const [xOk, setXOk] = useState<string | null>(null);
  const [xSummary, setXSummary] = useState<{ aggregate?: number; tweets?: number; err?: string | null } | null>(null);
  const [nseFile, setNseFile] = useState<File | null>(null);
  const [nseUploading, setNseUploading] = useState(false);
  const [nseErr, setNseErr] = useState<string | null>(null);
  const [nseOk, setNseOk] = useState<string | null>(null);

  // PCR refresh interval settings
  const [pcrInterval, setPcrInterval] = useState<number | null>(null);
  const [pcrSaving, setPcrSaving] = useState(false);
  const [pcrErr, setPcrErr] = useState<string | null>(null);
  const [pcrOk, setPcrOk] = useState<string | null>(null);
  const PCR_OPTIONS = [5, 10, 30, 60];

  // Load PCR interval from backend on mount
  useEffect(() => {
    (async () => {
      try {
        const r = await fetch("/admin/settings");
        if (r.ok) {
          const j = (await r.json()) as { pcr_refresh_interval_minutes: number };
          setPcrInterval(j.pcr_refresh_interval_minutes);
        }
      } catch {
        // non-fatal
      }
    })();
  }, []);

  const savePcrInterval = async () => {
    if (pcrInterval == null) return;
    setPcrSaving(true);
    setPcrErr(null);
    setPcrOk(null);
    try {
      const r = await fetch("/admin/settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ pcr_refresh_interval_minutes: pcrInterval }),
      });
      const j = (await r.json()) as { ok?: boolean; message?: string; detail?: string };
      if (!r.ok) {
        setPcrErr(String(j.detail ?? `${r.status} ${r.statusText}`));
      } else {
        setPcrOk(j.message ?? "Saved.");
      }
    } catch (e) {
      setPcrErr(e instanceof Error ? e.message : "Save failed");
    } finally {
      setPcrSaving(false);
    }
  };

  useEffect(() => {
    (async () => {
      setLoadErr(null);
      setReady(false);
      try {
        const r = await fetch(`/snapshot/today?market=${encodeURIComponent(market)}&live=false`);
        if (r.status === 404) {
          setFromDb(null);
        } else if (!r.ok) {
          setLoadErr(`${r.status} ${r.statusText}`);
        } else {
          const j = (await r.json()) as Snapshot;
          setFromDb(j);
        }
      } catch (e) {
        setLoadErr(e instanceof Error ? e.message : "Request failed");
      } finally {
        setReady(true);
      }
    })();
  }, [market]);

  const runLiveRefresh = async () => {
    setRefreshErr(null);
    setLastOk(null);
    setRefreshing(true);
    try {
      const r = await fetch(
        `/snapshot/today?live=true&persist=true&market=${encodeURIComponent(market)}`,
      );
      if (!r.ok) {
        setRefreshErr(`${r.status} ${r.statusText}`);
        return;
      }
      const j = (await r.json()) as Snapshot;
      persistSnapshot(j, market);
      setFromDb(j);
      setLastOk(`Saved ${market} snapshot for ${j.header?.date ?? (j as { snapshot_date?: string }).snapshot_date ?? "?"}.`);
    } catch (e) {
      setRefreshErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const runXSyncOnly = async (patchDb: boolean) => {
    setXErr(null);
    setXOk(null);
    setXSummary(null);
    setXSyncing(true);
    try {
      const q = new URLSearchParams();
      if (patchDb) {
        q.set("persist", "true");
        q.set("market", market);
      } else {
        q.set("persist", "false");
      }
      const r = await fetch(`/x/sync?${q.toString()}`, { method: "POST" });
      const j = (await r.json()) as {
        ok?: boolean;
        x_sentiment_summary?: {
          aggregate_0_100?: number;
          tweet_count?: number;
          error?: string | null;
        };
        message?: string;
        persisted?: boolean;
        detail?: string;
      };
      if (!r.ok) {
        const d = j.detail;
        const msg = Array.isArray(d) ? d.map((e: { msg?: string }) => e.msg).join(" ") : d;
        setXErr(msg != null && String(msg) ? String(msg) : `${r.status} ${r.statusText}`);
        return;
      }
      setXOk(j.message ?? "X sync finished.");
      setXSummary({
        aggregate: j.x_sentiment_summary?.aggregate_0_100,
        tweets: j.x_sentiment_summary?.tweet_count,
        err: j.x_sentiment_summary?.error ?? null,
      });
      if (j.persisted) {
        const rr = await fetch(`/snapshot/today?market=${encodeURIComponent(market)}&live=false`);
        if (rr.ok) {
          const snap = (await rr.json()) as Snapshot;
          setFromDb(snap);
          persistSnapshot(snap, market);
        }
      }
    } catch (e) {
      setXErr(e instanceof Error ? e.message : "X sync failed");
    } finally {
      setXSyncing(false);
    }
  };

  const uploadNseOptionsJson = async () => {
    if (market !== "in_nifty" || !nseFile) return;
    setNseErr(null);
    setNseOk(null);
    setNseUploading(true);
    try {
      const text = await nseFile.text();
      JSON.parse(text);
      const r = await fetch(
        `/snapshot/options/from-nse-json?market=${encodeURIComponent(market)}&symbol=NIFTY&persist=true`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: text,
        },
      );
      const j = (await r.json()) as {
        ok?: boolean;
        options?: { pcr_oi?: number | null; call_oi_total?: number; put_oi_total?: number };
        patched_snapshot_date?: string;
        detail?: string | { msg?: string }[];
      };
      if (!r.ok) {
        const d = j.detail;
        const msg = Array.isArray(d) ? d.map((e) => e.msg).filter(Boolean).join(" ") : d;
        setNseErr(msg != null && String(msg) ? String(msg) : `${r.status} ${r.statusText}`);
        return;
      }
      const pcr = j.options?.pcr_oi;
      setNseOk(
        `Options merged into snapshot ${j.patched_snapshot_date ?? "?"}. PCR (OI): ${pcr != null ? pcr.toFixed(3) : "—"}.`,
      );
      const rr = await fetch(`/snapshot/today?market=${encodeURIComponent(market)}&live=false`);
      if (rr.ok) {
        const snap = (await rr.json()) as Snapshot;
        setFromDb(snap);
        persistSnapshot(snap, market);
      }
    } catch (e) {
      setNseErr(e instanceof Error ? e.message : "Invalid JSON or upload failed");
    } finally {
      setNseUploading(false);
    }
  };

  const local = readStoredSnapshot(market);
  const marketLabel = MARKETS.find((m) => m.id === market)?.label ?? market;

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 px-4 py-3 shadow-md shadow-black/20 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <p className="min-w-0 text-xs font-medium uppercase tracking-widest text-slate-400">Admin</p>
          <div className="flex flex-wrap items-center gap-2">
            <label className="sr-only" htmlFor="admin-market">
              Market
            </label>
            <select
              id="admin-market"
              value={market}
              onChange={(e) => setMarket(e.target.value as typeof market)}
              className="max-w-[min(100%,240px)] rounded-lg border border-slate-600 bg-slate-900 px-2 py-1.5 text-xs text-slate-100"
            >
              {MARKETS.map((m) => (
                <option key={m.id} value={m.id}>
                  {m.label}
                </option>
              ))}
            </select>
            <Link
              to="/"
              className="shrink-0 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700"
            >
              Back to dashboard
            </Link>
          </div>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-10 pb-16">
        <h1 className="text-2xl font-semibold text-white">Data refresh</h1>
        <p className="mt-2 text-sm text-slate-400">
          Fetches live data for <span className="text-slate-200">{marketLabel}</span>, computes the snapshot, and
          saves it to the database. This can take a few minutes.
        </p>
        <p className="mt-2 text-sm text-slate-500">
          X (Twitter) List + FinBERT is available separately — it does not run Yahoo or NSE. Use the buttons below to
          test or patch only sentiment.
        </p>

        {market === "in_nifty" ? (
          <div className="mt-6 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">NSE option chain (JSON file)</p>

            <div className="space-y-2 rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 text-sm text-slate-300">
              <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">How to download the JSON</p>
              <ol className="list-decimal space-y-2 pl-5 text-slate-400 leading-relaxed">
                <li>
                  On a device where the NSE site loads the chain (often easiest from an Indian network or VPN), open{" "}
                  <a
                    className="text-sky-400 underline decoration-slate-600 underline-offset-2 hover:text-sky-300"
                    href="https://www.nseindia.com/option-chain"
                    target="_blank"
                    rel="noreferrer"
                  >
                    nseindia.com/option-chain
                  </a>
                  , set the symbol to <span className="text-slate-200">NIFTY</span>, and let the table load.
                </li>
                <li>
                  Open the browser’s developer tools: <span className="text-slate-200">F12</span> or right-click the page
                  and choose <span className="text-slate-200">Inspect</span>, then open the <span className="text-slate-200">Network</span>{" "}
                  tab.
                </li>
                <li>
                  Refresh the page or change expiry so the list reloads. In the request list, find the call whose name
                  or URL includes{" "}
                  <span className="font-mono text-xs text-slate-200">option-chain-indices</span> and query{" "}
                  <span className="font-mono text-xs text-slate-200">symbol=NIFTY</span> (filter by &quot;indices&quot; or
                  &quot;NIFTY&quot; if the list is long).
                </li>
                <li>
                  Click that request, open the <span className="text-slate-200">Response</span> (or preview) panel. You
                  should see JSON starting with <span className="font-mono text-xs text-slate-200">"records"</span> (and
                  often <span className="font-mono text-xs text-slate-200">"filtered"</span>).
                </li>
                <li>
                  Right-click the response body → <span className="text-slate-200">Copy</span> →{" "}
                  <span className="text-slate-200">Copy response</span> (or save as a <span className="text-slate-200">.json</span>{" "}
                  file if your browser offers it). That file is what you upload below.
                </li>
              </ol>
              <p className="pt-1 text-xs text-amber-200/80">
                If the response is empty <span className="font-mono text-[11px]">{"{}"}</span> when you are not in India,
                try from an Indian network or another machine where the chain actually loads, then copy the file here.
              </p>
            </div>

            <p className="text-sm text-slate-400">
              Upload that raw NSE response below. It is merged into the <span className="text-slate-200">same</span> saved
              snapshot the main dashboard uses by default. You need a snapshot in the database first: run a live refresh
              below if the database is still empty.
            </p>
            {nseErr ? <p className="text-sm text-rose-300">{nseErr}</p> : null}
            {nseOk ? <p className="text-sm text-emerald-300/90">{nseOk}</p> : null}
            <div className="flex flex-wrap items-center gap-3">
              <input
                type="file"
                accept=".json,application/json"
                className="max-w-full text-xs text-slate-300 file:mr-2 file:rounded-md file:border file:border-slate-600 file:bg-slate-800 file:px-2 file:py-1.5 file:text-slate-200"
                onChange={(e) => {
                  setNseFile(e.target.files?.[0] ?? null);
                  setNseErr(null);
                  setNseOk(null);
                }}
              />
              <button
                type="button"
                disabled={!nseFile || nseUploading || refreshing || xSyncing}
                onClick={() => void uploadNseOptionsJson()}
                className="rounded-lg border border-emerald-600/50 bg-emerald-950/40 px-4 py-2 text-sm font-medium text-emerald-100 hover:bg-emerald-900/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {nseUploading ? "Uploading…" : "Merge into saved snapshot"}
              </button>
            </div>
          </div>
        ) : null}

        <div className="mt-8 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Current status (database / cache read)</p>
          {!ready ? <p className="text-sm text-slate-500">Checking stored snapshot…</p> : null}
          {ready && loadErr ? <p className="text-sm text-rose-300">{loadErr}</p> : null}
          {ready && !loadErr && fromDb ? (
            <p className="text-sm text-slate-200">
              Latest stored: <span className="text-white">{fromDb.header?.date ?? "—"}</span> ({fromDb.meta?.market_id ?? market})
            </p>
          ) : null}
          {ready && !loadErr && !fromDb ? (
            <p className="text-sm text-amber-200/90">No snapshot in the database for this market yet. Run a live refresh below.</p>
          ) : null}
          {local && (
            <p className="text-xs text-slate-500">Browser has a cached copy for date {local.header?.date ?? "—"}.</p>
          )}
          {ready && !loadErr && fromDb && (fromDb.meta?.data_warnings?.length ?? 0) > 0 ? (
            <div className="mt-4 rounded-xl border border-amber-900/40 bg-amber-950/20 p-4 text-xs text-amber-100/90">
              <p className="text-[11px] font-medium uppercase tracking-wide text-amber-200/80">Data notes (saved snapshot)</p>
              <ul className="mt-2 list-disc space-y-1.5 pl-4 leading-relaxed">
                {(fromDb.meta?.data_warnings ?? []).map((w, i) => (
                  <li key={`adm-dw-${i}`}>{w}</li>
                ))}
              </ul>
              <p className="mt-2 text-[11px] text-slate-500">
                Pipeline warnings from the API (e.g. upstream feeds). The main dashboard no longer shows this block.
              </p>
            </div>
          ) : null}
        </div>

        <div className="mt-6 space-y-6">
          <div>
            {refreshing ? <p className="mb-3 text-sm text-slate-500">Refreshing live data… (this may take several minutes)</p> : null}
            {refreshErr ? <p className="mb-3 text-sm text-rose-300">{refreshErr}</p> : null}
            {lastOk ? <p className="mb-3 text-sm text-emerald-300/90">{lastOk}</p> : null}
            <button
              type="button"
              disabled={refreshing || xSyncing}
              onClick={() => void runLiveRefresh()}
              className="rounded-lg border border-amber-600/50 bg-amber-950/40 px-4 py-2.5 text-sm font-semibold text-amber-100 hover:bg-amber-900/50 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {refreshing ? "Refreshing…" : "Refresh live & save to database"}
            </button>
          </div>

          <div className="border-t border-slate-800 pt-6">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">X (Twitter) only</p>
            <p className="mt-1 text-sm text-slate-400">
              Calls the X List API and sentiment scoring by itself. Does not fetch prices or news.
            </p>
            {xSyncing ? <p className="mt-2 text-sm text-slate-500">Syncing X…</p> : null}
            {xErr ? <p className="mt-2 text-sm text-rose-300">{xErr}</p> : null}
            {xOk ? <p className="mt-2 text-sm text-emerald-300/90">{xOk}</p> : null}
            {xSummary ? (
              <p className="mt-2 text-sm text-slate-300">
                Aggregate (0–100): <span className="text-white">{xSummary.aggregate != null ? xSummary.aggregate.toFixed(1) : "—"}</span>
                {" · "}
                Tweets: <span className="text-white">{xSummary.tweets ?? "—"}</span>
                {xSummary.err ? <span className="block text-xs text-amber-200/80">Note: {xSummary.err}</span> : null}
              </p>
            ) : null}
            <div className="mt-3 flex flex-wrap gap-2">
              <button
                type="button"
                disabled={xSyncing || refreshing}
                onClick={() => void runXSyncOnly(false)}
                className="rounded-lg border border-slate-600 bg-slate-800/80 px-4 py-2 text-sm font-medium text-slate-100 hover:bg-slate-700 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {xSyncing ? "…" : "Run X / List sync only"}
              </button>
              <button
                type="button"
                disabled={xSyncing || refreshing}
                onClick={() => void runXSyncOnly(true)}
                className="rounded-lg border border-sky-600/50 bg-sky-950/40 px-4 py-2 text-sm font-medium text-sky-100 hover:bg-sky-900/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {xSyncing ? "…" : "Sync X and patch latest DB row"}
              </button>
            </div>
            <p className="mt-2 text-xs text-slate-500">
              "Patch latest DB row" merges new X scores into the most recent saved snapshot for the selected market
              (recomputes composite). Run a full refresh first if you have no data yet.
            </p>
          </div>

          {/* ─── PCR Refresh Interval ─────────────────────────────────────────── */}
          <div className="border-t border-slate-800 pt-6">
            <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Watchlist — Refresh &amp; Alert Interval</p>
            <p className="mt-1 text-sm text-slate-400">
              How often the backend fetches fresh volume + PCR for all watched symbols, checks thresholds, and fires Telegram alerts.
              Changes take effect immediately without restarting the server.
            </p>
            {pcrErr ? <p className="mt-2 text-sm text-rose-300">{pcrErr}</p> : null}
            {pcrOk ? <p className="mt-2 text-sm text-emerald-300/90">{pcrOk}</p> : null}
            <div className="mt-3 flex flex-wrap items-center gap-3">
              {PCR_OPTIONS.map((mins) => (
                <button
                  key={mins}
                  type="button"
                  onClick={() => { setPcrInterval(mins); setPcrOk(null); setPcrErr(null); }}
                  className={`rounded-lg border px-4 py-2 text-sm font-medium transition-colors ${
                    pcrInterval === mins
                      ? "border-emerald-500/60 bg-emerald-500/15 text-emerald-300"
                      : "border-slate-600 bg-slate-800/60 text-slate-300 hover:bg-slate-700"
                  }`}
                >
                  {mins} min
                </button>
              ))}
              <button
                type="button"
                disabled={pcrSaving || pcrInterval == null}
                onClick={() => void savePcrInterval()}
                className="rounded-lg border border-sky-600/50 bg-sky-950/40 px-4 py-2 text-sm font-semibold text-sky-100 hover:bg-sky-900/50 disabled:cursor-not-allowed disabled:opacity-50"
              >
                {pcrSaving ? "Saving…" : "Save"}
              </button>
            </div>
            {pcrInterval != null && (
              <p className="mt-2 text-xs text-slate-500">
                Currently set to <span className="text-slate-300">{pcrInterval} minutes</span>.
              </p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
