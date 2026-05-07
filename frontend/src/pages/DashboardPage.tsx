import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { LiveIndexOptionsStrip } from "../components/dashboard/LiveIndexOptionsStrip";
import { NewsSection } from "../components/NewsSection";
import { Card } from "../components/ui/Card";
import { fmtDelta, fmtIv, fmtNum, pctChip } from "../lib/format";
import { useMarket } from "../market/MarketContext";
import { MARKETS } from "../market/types";
import type { DatabentoOptionsBlock, Snapshot } from "../types";
import { persistSnapshot, readStoredSnapshot } from "../snapshotStorage";

function DatabentoOptionsSection({ block }: { block: DatabentoOptionsBlock }) {
  const cv = block.cleared_volume;
  const iv = block.oi_weighted_iv;
  const atm = block.atm;
  const off = block.official_prices;
  const subParts = [block.dataset];
  if (block.spot_for_atm != null && block.spot_for_atm > 0) {
    subParts.push(`Spot for ATM: ${fmtNum(block.spot_for_atm, 2)}`);
  }

  return (
    <Card title="Databento OPRA — parent chain" subtitle={subParts.join(" · ")}>
      <p className="text-xs text-slate-500">
        {block.parent_symbol} · Statistics session (T+1 weekday):{" "}
        <span className="text-slate-300">{block.oi_session_date}</span>
        {block.nearest_expiry ? (
          <>
            {" "}
            · Chain expiry: <span className="text-slate-300">{block.nearest_expiry}</span>
          </>
        ) : null}
      </p>

      <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-3">
        {cv ? (
          <>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Cleared vol — calls</p>
              <p className="mt-1 text-xl font-semibold text-white">{fmtNum(cv.call, 0)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Cleared vol — puts</p>
              <p className="mt-1 text-xl font-semibold text-white">{fmtNum(cv.put, 0)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">PCR (cleared volume)</p>
              <p className="mt-1 text-xl font-semibold text-white">{fmtNum(cv.pcr, 3)}</p>
            </div>
          </>
        ) : (
          <div className="rounded-xl border border-slate-800 border-dashed bg-slate-950/20 p-3 md:col-span-3">
            <p className="text-xs text-slate-500">Cleared contract volume</p>
            <p className="mt-1 text-sm text-slate-400">Not published for this slice / session.</p>
          </div>
        )}
      </div>

      {iv ? (
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2">
          <div className="rounded-xl border border-cyan-950/50 bg-slate-950/40 p-3">
            <p className="text-xs text-cyan-200/70">OI-weighted IV — calls</p>
            <p className="mt-1 text-xl font-semibold text-cyan-100">{fmtIv(iv.calls)}</p>
          </div>
          <div className="rounded-xl border border-cyan-950/50 bg-slate-950/40 p-3">
            <p className="text-xs text-cyan-200/70">OI-weighted IV — puts</p>
            <p className="mt-1 text-xl font-semibold text-cyan-100">{fmtIv(iv.puts)}</p>
          </div>
        </div>
      ) : null}

      {atm ? (
        <div className="mt-4">
          <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Near-ATM strike</p>
          <div className="mt-2 grid grid-cols-2 gap-3 md:grid-cols-4">
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Strike</p>
              <p className="mt-1 text-lg font-semibold text-white">{fmtNum(atm.strike, 2)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Call IV</p>
              <p className="mt-1 text-lg font-semibold text-white">{fmtIv(atm.call_iv)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Put IV</p>
              <p className="mt-1 text-lg font-semibold text-white">{fmtIv(atm.put_iv)}</p>
            </div>
            <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
              <p className="text-xs text-slate-500">Δ call / put</p>
              <p className="mt-1 text-sm font-semibold text-slate-100">
                {fmtDelta(atm.call_delta)} / {fmtDelta(atm.put_delta)}
              </p>
            </div>
          </div>
        </div>
      ) : null}

      {off &&
      (off.oi_weighted_close_call != null ||
        off.oi_weighted_close_put != null ||
        off.oi_weighted_settlement_call != null ||
        off.oi_weighted_settlement_put != null) ? (
        <div className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2">
          <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3 text-sm">
            <p className="text-xs text-slate-500">OI-weighted close (prem.)</p>
            <p className="mt-1 text-slate-200">
              Call {fmtNum(off.oi_weighted_close_call, 4)} · Put {fmtNum(off.oi_weighted_close_put, 4)}
            </p>
          </div>
          <div className="rounded-xl border border-slate-800 bg-slate-950/30 p-3 text-sm">
            <p className="text-xs text-slate-500">OI-weighted settlement (prem.)</p>
            <p className="mt-1 text-slate-200">
              Call {fmtNum(off.oi_weighted_settlement_call, 4)} · Put {fmtNum(off.oi_weighted_settlement_put, 4)}
            </p>
          </div>
        </div>
      ) : null}

      {!block.has_quotes ? (
        <p className="mt-4 text-xs text-amber-200/85">
          Extended stats (volume / IV / delta / settlement) were not available in the OPRA statistics feed for this
          session—the venue may only have published open interest for these instruments.
        </p>
      ) : null}

      <p className="mt-4 text-xs leading-relaxed text-slate-500">{block.note}</p>
    </Card>
  );
}

function StickyTopBar() {
  const { market, setMarket } = useMarket();
  return (
    <div className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 px-4 py-3 shadow-md shadow-black/20 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
        <p className="min-w-0 text-xs font-medium uppercase tracking-widest text-slate-400">Daily market snapshot</p>
        <div className="flex flex-wrap items-center gap-2">
          <label className="sr-only" htmlFor="market-select">
            Market
          </label>
          <select
            id="market-select"
            value={market}
            onChange={(e) => setMarket(e.target.value as typeof market)}
            className="max-w-[min(100%,220px)] rounded-lg border border-slate-600 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
          >
            {MARKETS.map((m) => (
              <option key={m.id} value={m.id}>
                {m.label}
              </option>
            ))}
          </select>
          <Link
            to="/admin"
            className="shrink-0 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700"
          >
            Admin
          </Link>
        </div>
      </div>
    </div>
  );
}

export function DashboardPage() {
  const { market } = useMarket();
  /** Page load uses the saved DB snapshot only (`live=false`). Live upstream polls are isolated to the index/OI strip. */
  const [data, setData] = useState<Snapshot | null>(() => readStoredSnapshot(market));
  const [err, setErr] = useState<string | null>(null);
  const [ready, setReady] = useState(false);
  const [needsAdminRefresh, setNeedsAdminRefresh] = useState(false);

  useEffect(() => {
    setData(readStoredSnapshot(market));
    setErr(null);
    setNeedsAdminRefresh(false);
    setReady(false);
    (async () => {
      try {
        const r = await fetch(`/snapshot/today?market=${encodeURIComponent(market)}&live=false`, { cache: "no-store" });
        if (r.status === 404) {
          if (!readStoredSnapshot(market)) {
            setNeedsAdminRefresh(true);
            setErr("No saved snapshot in the database yet. Open Admin and run “Refresh live & save to database”.");
          }
          return;
        }
        if (!r.ok) {
          const msg = `${r.status} ${r.statusText}`;
          if (!readStoredSnapshot(market)) {
            setErr(msg);
          }
          return;
        }
        const j = (await r.json()) as Snapshot;
        setData(j);
        persistSnapshot(j, market);
      } catch (e) {
        if (!readStoredSnapshot(market)) {
          setErr(e instanceof Error ? e.message : "Failed to load snapshot");
        }
      } finally {
        setReady(true);
      }
    })();
  }, [market]);

  if (data) {
    const ui = data.meta?.ui;
    const moversSub = ui?.movers_subtitle ?? "Nifty 50";
    const fiiCardTitle = ui?.fii_title ?? "FII / DII (cash)";
    const showFii = ui?.show_fii_card !== false;
    const globalSub = ui?.global_subtitle ?? "Overnight / cross-asset cues";

    return (
      <div className="min-h-screen bg-slate-950">
        <StickyTopBar />
        <div className="mx-auto max-w-6xl px-4 py-10 pb-16">
          {err ? (
            <div className="mb-6 rounded-xl border border-amber-900/50 bg-amber-950/25 p-4 text-sm text-amber-100/90">
              <span className="font-semibold">Could not sync from server.</span> {err} (showing saved view.)
            </div>
          ) : null}
          <header className="mb-8 border-b border-slate-800 pb-6">
            <h1 className="text-3xl font-semibold text-white md:text-4xl">{data.header.title}</h1>
            <div className="mt-3 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-slate-400">
              <span>{data.header.date}</span>
              {data.generated_at_utc ? <span>Generated UTC: {data.generated_at_utc}</span> : null}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              The top section includes <span className="text-slate-300">index, breadth, VIX, options</span>, and{" "}
              <span className="text-slate-300">composite sentiment</span>. Turn <span className="text-slate-300">Live</span> on there to refresh prices and breadth;
              composite stays aligned with the saved snapshot unless you run a full refresh from Admin.
            </p>
          </header>

          <div className="mb-4">
            <LiveIndexOptionsStrip market={market} base={data} />
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Technical levels" subtitle="Classic pivot (prior session)">
              <div className="overflow-hidden rounded-xl border border-slate-700/50 bg-gradient-to-b from-teal-950/95 via-zinc-950/90 to-red-950/95 text-xs shadow-inner shadow-black/20">
                {(
                  [
                    ["S2", data.technical.s2],
                    ["S1", data.technical.s1],
                    ["P", data.technical.pivot],
                    ["R1", data.technical.r1],
                    ["R2", data.technical.r2],
                  ] as const
                ).map(([k, v], i, arr) => (
                  <div
                    key={String(k)}
                    className={`flex items-center justify-between gap-3 px-3 py-2.5 ${
                      i < arr.length - 1 ? "border-b border-white/[0.06]" : ""
                    }`}
                  >
                    <span
                      className={
                        i <= 1
                          ? "font-medium text-teal-400"
                          : i >= 3
                            ? "font-medium text-red-400"
                            : "font-medium text-amber-300"
                      }
                    >
                      {k}
                    </span>
                    <span
                      className={`text-sm font-semibold tabular-nums ${
                        i <= 1 ? "text-teal-100" : i >= 3 ? "text-red-100" : "text-amber-50"
                      }`}
                    >
                      {fmtNum(v as number | null, 2)}
                    </span>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-sm text-slate-300">{data.technical.note}</p>
            </Card>

            {showFii ? (
              <Card title={fiiCardTitle} subtitle={data.fii_dii.as_of ? `As of ${data.fii_dii.as_of}` : "Latest available"}>
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-500">FII net (₹ cr)</p>
                    <p className="mt-1 text-xl font-semibold text-white">{fmtNum(data.fii_dii.fii_net_crores, 0)}</p>
                  </div>
                  <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                    <p className="text-xs text-slate-500">DII net (₹ cr)</p>
                    <p className="mt-1 text-xl font-semibold text-white">{fmtNum(data.fii_dii.dii_net_crores, 0)}</p>
                  </div>
                </div>
                <p className="mt-3 text-sm text-slate-300">{data.fii_dii.note}</p>
              </Card>
            ) : null}

            {data.databento_options ? (
              <div className="lg:col-span-2">
                <DatabentoOptionsSection block={data.databento_options} />
              </div>
            ) : null}

            <Card title="Global & commodities" subtitle={globalSub}>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {Object.values(data.global).map((g) => (
                  <div key={g.label} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2 text-sm">
                    <div>
                      <div className="text-xs text-slate-500">
                        {g.label}
                        {g.currency ? <span className="ml-1 text-slate-600">({g.currency})</span> : null}
                      </div>
                      <div className="font-medium text-slate-100">{fmtNum(g.last, 2)}</div>
                    </div>
                    <div className="text-right text-xs">{pctChip(g.pct_change)}</div>
                  </div>
                ))}
              </div>
              <p className="mt-3 text-sm text-slate-300">{data.global_note}</p>
            </Card>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Top gainers" subtitle={moversSub}>
              <ul className="divide-y divide-slate-800">
                {data.top_movers.gainers.map((g) => (
                  <li key={g.symbol} className="flex items-center justify-between py-2 text-sm">
                    <span className="font-medium text-slate-100">{g.symbol}</span>
                    {pctChip(g.pct_change)}
                  </li>
                ))}
              </ul>
            </Card>
            <Card title="Top losers" subtitle={moversSub}>
              <ul className="divide-y divide-slate-800">
                {data.top_movers.losers.map((g) => (
                  <li key={g.symbol} className="flex items-center justify-between py-2 text-sm">
                    <span className="font-medium text-slate-100">{g.symbol}</span>
                    {pctChip(g.pct_change)}
                  </li>
                ))}
              </ul>
            </Card>
          </div>

          <Card title="X List sentiment (summary)" subtitle={data.x_sentiment_summary.model}>
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div>
                <p className="text-xs text-slate-500">Aggregate (0–100)</p>
                <p className="text-3xl font-semibold text-white">{fmtNum(data.x_sentiment_summary.aggregate_0_100, 1)}</p>
              </div>
              <div className="text-right text-sm text-slate-400">
                Tweets scored: <span className="text-slate-200">{data.x_sentiment_summary.tweet_count}</span>
              </div>
            </div>
            {data.x_sentiment_summary.error ? (
              <p className="mt-2 text-xs text-amber-200/80">{data.x_sentiment_summary.error}</p>
            ) : null}
          </Card>

          <div className="mt-6">
            <NewsSection market={market} />
          </div>
        </div>
      </div>
    );
  }

  if (!ready) {
    return (
      <div className="min-h-screen bg-slate-950">
        <StickyTopBar />
        <div className="mx-auto max-w-6xl px-4 py-6 pb-10">
          <NewsSection market={market} />
        </div>
      </div>
    );
  }

  if (err) {
    return (
      <div className="min-h-screen bg-slate-950">
        <StickyTopBar />
        <div className="mx-auto max-w-6xl px-4 py-6 pb-16">
          <div className="mb-6">
            <NewsSection market={market} />
          </div>
          <h1 className="text-2xl font-semibold text-white">Could not load</h1>
          <div className="mt-6 rounded-2xl border border-rose-900/50 bg-rose-950/30 p-6 text-rose-200">
            <p className="font-semibold">Snapshot unavailable</p>
            <p className="mt-2 text-sm text-rose-200/80">{err}</p>
            <p className="mt-4 text-xs text-slate-400">
              Ensure the API is running. Open <span className="text-slate-200">/admin</span> to run a live refresh and save data.
            </p>
            <Link to="/admin" className="mt-4 inline-block text-sm text-amber-200 underline hover:text-amber-100">
              Go to Admin
            </Link>
          </div>
        </div>
      </div>
    );
  }

  if (needsAdminRefresh) {
    return (
      <div className="min-h-screen bg-slate-950">
        <StickyTopBar />
        <div className="mx-auto max-w-6xl px-4 py-6 pb-16">
          <div className="mb-8">
            <NewsSection market={market} />
          </div>
          <p className="text-center text-lg text-slate-200">You need to refresh data.</p>
          <p className="mt-2 text-center text-sm text-slate-500">
            Nothing is stored in the database for this app yet, and there is no saved view in the browser.
          </p>
          <div className="mt-6 text-center">
            <Link
              to="/admin"
              className="inline-block rounded-lg border border-amber-600/50 bg-amber-950/40 px-4 py-2 text-sm font-medium text-amber-100 hover:bg-amber-900/50"
            >
              Open Admin to refresh
            </Link>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-slate-950">
      <StickyTopBar />
      <div className="mx-auto max-w-6xl px-4 py-6">
        <NewsSection market={market} />
        <p className="mt-6 text-center text-sm text-slate-500">Something went wrong.</p>
        <p className="mt-2 text-center">
          <Link to="/admin" className="text-amber-200/90 underline">
            Open Admin
          </Link>
        </p>
      </div>
    </div>
  );
}
