import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import type { Snapshot } from "../types";
import { persistSnapshot, readStoredSnapshot } from "../snapshotStorage";

export function AdminPage() {
  const [fromDb, setFromDb] = useState<Snapshot | null>(null);
  const [loadErr, setLoadErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [refreshing, setRefreshing] = useState(false);
  const [refreshErr, setRefreshErr] = useState<string | null>(null);
  const [lastOk, setLastOk] = useState<string | null>(null);

  useEffect(() => {
    (async () => {
      setLoadErr(null);
      try {
        const r = await fetch("/snapshot/today");
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
  }, []);

  const runLiveRefresh = async () => {
    setRefreshErr(null);
    setLastOk(null);
    setRefreshing(true);
    try {
      const r = await fetch("/snapshot/today?live=true&persist=true");
      if (!r.ok) {
        setRefreshErr(`${r.status} ${r.statusText}`);
        return;
      }
      const j = (await r.json()) as Snapshot;
      persistSnapshot(j);
      setFromDb(j);
      setLastOk(`Saved snapshot for ${j.header?.date ?? (j as { snapshot_date?: string }).snapshot_date ?? "?"}.`);
    } catch (e) {
      setRefreshErr(e instanceof Error ? e.message : "Refresh failed");
    } finally {
      setRefreshing(false);
    }
  };

  const local = readStoredSnapshot();

  return (
    <div className="min-h-screen bg-slate-950">
      <div className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 px-4 py-3 shadow-md shadow-black/20 backdrop-blur">
        <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
          <p className="min-w-0 text-xs font-medium uppercase tracking-widest text-slate-400">Admin</p>
          <Link
            to="/"
            className="shrink-0 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700"
          >
            Back to dashboard
          </Link>
        </div>
      </div>

      <div className="mx-auto max-w-2xl px-4 py-10 pb-16">
        <h1 className="text-2xl font-semibold text-white">Data refresh</h1>
        <p className="mt-2 text-sm text-slate-400">
          Fetches live market data, computes the snapshot, and saves it to the database. This can take a few minutes.
        </p>

        <div className="mt-8 space-y-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-6">
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Current status (database / cache read)</p>
          {!ready ? <p className="text-sm text-slate-500">Checking stored snapshot…</p> : null}
          {ready && loadErr ? <p className="text-sm text-rose-300">{loadErr}</p> : null}
          {ready && !loadErr && fromDb ? (
            <p className="text-sm text-slate-200">
              Latest stored: <span className="text-white">{fromDb.header?.date ?? "—"}</span>
            </p>
          ) : null}
          {ready && !loadErr && !fromDb ? (
            <p className="text-sm text-amber-200/90">No snapshot in the database yet. Run a live refresh below.</p>
          ) : null}
          {local && (
            <p className="text-xs text-slate-500">Browser has a cached copy for date {local.header?.date ?? "—"}.</p>
          )}
        </div>

        <div className="mt-6">
          {refreshing ? <p className="mb-3 text-sm text-slate-500">Refreshing live data… (this may take several minutes)</p> : null}
          {refreshErr ? <p className="mb-3 text-sm text-rose-300">{refreshErr}</p> : null}
          {lastOk ? <p className="mb-3 text-sm text-emerald-300/90">{lastOk}</p> : null}
          <button
            type="button"
            disabled={refreshing}
            onClick={() => void runLiveRefresh()}
            className="rounded-lg border border-amber-600/50 bg-amber-950/40 px-4 py-2.5 text-sm font-semibold text-amber-100 hover:bg-amber-900/50 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {refreshing ? "Refreshing…" : "Refresh live & save to database"}
          </button>
        </div>
      </div>
    </div>
  );
}
