import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { NewsSection } from "../components/NewsSection";
import { Card } from "../components/ui/Card";
import { useMarket } from "../market/MarketContext";
import { MARKETS } from "../market/types";
import type { Snapshot } from "../types";
import { persistSnapshot, readStoredSnapshot } from "../snapshotStorage";

function fmtNum(n: number | null | undefined, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}

function pctChip(pct: number | null | undefined) {
  if (pct === null || pct === undefined) return <span className="text-slate-400">—</span>;
  const up = pct >= 0;
  return (
    <span className={up ? "text-emerald-400" : "text-rose-400"}>
      {up ? "+" : ""}
      {pct.toFixed(2)}%
    </span>
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
        // live=true: recompute from Yahoo (etc.); omit persist so we do not write DB on every view — Admin "Refresh" saves.
        const r = await fetch(
          `/snapshot/today?market=${encodeURIComponent(market)}&live=true`,
          { cache: "no-store" },
        );
        if (r.status === 404) {
          if (!readStoredSnapshot(market)) {
            setNeedsAdminRefresh(true);
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
    const comp = data.composite;
    const score = comp.score_0_100;
    const ui = data.meta?.ui;
    const indexTitle = ui?.index_title ?? "Nifty 50";
    const indexSub = ui?.index_subtitle ?? "Cash index";
    const breadthSub = ui?.breadth_subtitle ?? "Nifty 50 constituents";
    const moversSub = ui?.movers_subtitle ?? "Nifty 50";
    const vixLine = ui?.vix_line ?? "India VIX";
    const fiiCardTitle = ui?.fii_title ?? "FII / DII (cash)";
    const showFii = ui?.show_fii_card !== false;
    const globalSub = ui?.global_subtitle ?? "Overnight / cross-asset cues";
    const meterColor =
      score >= 62 ? "from-emerald-500/30 to-emerald-400/10" : score <= 42 ? "from-rose-500/30 to-rose-400/10" : "from-amber-500/25 to-amber-400/10";

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
            {data.meta?.data_warnings?.length ? (
              <div className="mt-4 rounded-xl border border-amber-900/40 bg-amber-950/20 p-3 text-xs text-amber-100/90">
                {data.meta.data_warnings.join(" · ")}
              </div>
            ) : null}
          </header>

          <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
            <Card title={indexTitle} subtitle={indexSub}>
              <div className="flex items-end justify-between gap-3">
                <div>
                  <p className="text-4xl font-semibold tracking-tight text-white">{fmtNum(data.index.close, 2)}</p>
                  <p className="mt-2 text-sm text-slate-300">{pctChip(data.index.pct_change)} day</p>
                </div>
                <div className="text-right text-xs text-slate-400">
                  <div>O {fmtNum(data.index.open)}</div>
                  <div>H {fmtNum(data.index.high)}</div>
                  <div>L {fmtNum(data.index.low)}</div>
                </div>
              </div>
              <p className="mt-4 text-sm leading-relaxed text-slate-300">{data.index.narrative}</p>
            </Card>

            <Card title="Composite sentiment" subtitle="0–100 (Bearish → Bullish)">
              <div className={`rounded-xl border border-slate-800 bg-gradient-to-br ${meterColor} p-4`}>
                <div className="flex items-center justify-between">
                  <p className="text-5xl font-semibold text-white">{fmtNum(score, 1)}</p>
                  <span className="rounded-full border border-slate-700 bg-slate-950/40 px-3 py-1 text-xs font-medium text-slate-200">
                    {comp.label}
                  </span>
                </div>
                <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-900">
                  <div
                    className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400"
                    style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
                  />
                </div>
                <p className="mt-3 text-sm text-slate-200/90">{comp.explanation}</p>
                <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
                  {Object.entries(comp.components).map(([k, v]) => (
                    <div key={k} className="flex justify-between rounded-lg bg-slate-950/40 px-2 py-1">
                      <span className="capitalize">{k}</span>
                      <span className="text-slate-200">{v.toFixed(1)}</span>
                    </div>
                  ))}
                </div>
              </div>
            </Card>

            <Card title="Market breadth" subtitle={breadthSub}>
              <div className="grid grid-cols-3 gap-3 text-center">
                <div className="rounded-xl bg-emerald-950/30 p-3">
                  <p className="text-xs text-emerald-200/70">Advances</p>
                  <p className="text-2xl font-semibold text-emerald-200">{data.breadth.advances}</p>
                </div>
                <div className="rounded-xl bg-rose-950/30 p-3">
                  <p className="text-xs text-rose-200/70">Declines</p>
                  <p className="text-2xl font-semibold text-rose-200">{data.breadth.declines}</p>
                </div>
                <div className="rounded-xl bg-slate-800/60 p-3">
                  <p className="text-xs text-slate-400">Unch.</p>
                  <p className="text-2xl font-semibold text-slate-200">{data.breadth.unchanged}</p>
                </div>
              </div>
              <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
                <span>
                  {vixLine}: {fmtNum(data.vix.level, 2)}
                </span>
                {data.vix.pct_change !== null ? <span className="text-slate-300">({pctChip(data.vix.pct_change)} day)</span> : null}
              </p>
            </Card>
          </div>

          <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
            <Card title="Technical levels" subtitle="Classic pivot (prior session)">
              <div className="grid grid-cols-5 gap-2 text-center text-xs">
                {(
                  [
                    ["S2", data.technical.s2],
                    ["S1", data.technical.s1],
                    ["P", data.technical.pivot],
                    ["R1", data.technical.r1],
                    ["R2", data.technical.r2],
                  ] as const
                ).map(([k, v]) => (
                  <div key={String(k)} className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                    <div className="text-slate-500">{k}</div>
                    <div className="mt-1 text-sm font-semibold text-slate-100">{fmtNum(v as number | null, 2)}</div>
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

            <Card title="Options positioning" subtitle={`${data.options.symbol}${data.options.expiry ? ` · ${data.options.expiry}` : ""}`}>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs text-slate-500">PCR (OI)</p>
                  <p className="mt-1 text-xl font-semibold text-white">{fmtNum(data.options.pcr_oi, 3)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs text-slate-500">Put OI wall (support)</p>
                  <p className="mt-1 text-xl font-semibold text-white">{fmtNum(data.options.support_strike_put_oi, 0)}</p>
                </div>
                <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
                  <p className="text-xs text-slate-500">Call OI wall (resistance)</p>
                  <p className="mt-1 text-xl font-semibold text-white">{fmtNum(data.options.resistance_strike_call_oi, 0)}</p>
                </div>
              </div>
              <p className="mt-3 text-sm text-slate-300">{data.options.note}</p>
            </Card>

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
