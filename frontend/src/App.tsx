import { useEffect, useState } from "react";
import type { Snapshot } from "./types";

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

function Card({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-gradient-to-b from-slate-900/70 to-slate-950/40 p-5 shadow-lg shadow-black/30">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-sm font-semibold tracking-wide text-slate-200">{title}</h2>
          {subtitle ? <p className="mt-1 text-xs text-slate-500">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

export default function App() {
  const [data, setData] = useState<Snapshot | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  const load = async (live: boolean) => {
    setLoading(true);
    setErr(null);
    try {
      const url = live ? "/snapshot/today?live=true" : "/snapshot/today";
      const r = await fetch(url);
      if (!r.ok) throw new Error(`${r.status} ${r.statusText}`);
      const j = (await r.json()) as Snapshot;
      setData(j);
    } catch (e) {
      setErr(e instanceof Error ? e.message : "Failed to load snapshot");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    void load(false);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (loading) {
    return (
      <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-4">
        <p className="text-sm text-slate-400">Loading market snapshot…</p>
      </div>
    );
  }

  if (err || !data) {
    return (
      <div className="mx-auto max-w-6xl px-4 py-16">
        <div className="rounded-2xl border border-rose-900/50 bg-rose-950/30 p-6 text-rose-200">
          <p className="font-semibold">Could not load snapshot</p>
          <p className="mt-2 text-sm text-rose-200/80">{err ?? "Unknown error"}</p>
          <p className="mt-4 text-xs text-slate-400">
            Ensure the API is running and CORS allows this origin. For local dev, run the FastAPI server on port 8000
            with Vite proxy enabled.
          </p>
        </div>
      </div>
    );
  }

  const comp = data.composite;
  const score = comp.score_0_100;
  const meterColor =
    score >= 62 ? "from-emerald-500/30 to-emerald-400/10" : score <= 42 ? "from-rose-500/30 to-rose-400/10" : "from-amber-500/25 to-amber-400/10";

  return (
    <div className="mx-auto max-w-6xl px-4 py-10 pb-16">
      <header className="mb-8 border-b border-slate-800 pb-6">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Daily market snapshot</p>
          <button
            type="button"
            onClick={() => void load(true)}
            className="rounded-lg border border-slate-700 bg-slate-900 px-3 py-1 text-xs font-medium text-slate-200 hover:bg-slate-800"
          >
            Refresh live
          </button>
        </div>
        <h1 className="mt-2 text-3xl font-semibold text-white md:text-4xl">{data.header.title}</h1>
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
        <Card title="Nifty 50" subtitle="Cash index">
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

        <Card title="Market breadth" subtitle="Nifty 50 constituents">
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
            <span>India VIX: {fmtNum(data.vix.level, 2)}</span>
            {data.vix.pct_change !== null ? <span className="text-slate-300">({pctChip(data.vix.pct_change)} day)</span> : null}
          </p>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Technical levels" subtitle="Classic pivot (prior session)">
          <div className="grid grid-cols-5 gap-2 text-center text-xs">
            {[
              ["S2", data.technical.s2],
              ["S1", data.technical.s1],
              ["P", data.technical.pivot],
              ["R1", data.technical.r1],
              ["R2", data.technical.r2],
            ].map(([k, v]) => (
              <div key={String(k)} className="rounded-lg border border-slate-800 bg-slate-950/40 p-2">
                <div className="text-slate-500">{k}</div>
                <div className="mt-1 text-sm font-semibold text-slate-100">{fmtNum(v as number | null, 2)}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-300">{data.technical.note}</p>
        </Card>

        <Card title="FII / DII (cash)" subtitle={data.fii_dii.as_of ? `As of ${data.fii_dii.as_of}` : "Latest available"}>
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

        <Card title="Global & commodities" subtitle="Overnight / cross-asset cues">
          <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
            {Object.values(data.global).map((g) => (
              <div key={g.label} className="flex items-center justify-between rounded-lg border border-slate-800 bg-slate-950/30 px-3 py-2 text-sm">
                <div>
                  <div className="text-xs text-slate-500">{g.label}</div>
                  <div className="font-medium text-slate-100">{fmtNum(g.last, g.currency === "INR" ? 2 : 2)}</div>
                </div>
                <div className="text-right text-xs">{pctChip(g.pct_change)}</div>
              </div>
            ))}
          </div>
          <p className="mt-3 text-sm text-slate-300">{data.global_note}</p>
        </Card>
      </div>

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card title="Top gainers" subtitle="Nifty 50">
          <ul className="divide-y divide-slate-800">
            {data.top_movers.gainers.map((g) => (
              <li key={g.symbol} className="flex items-center justify-between py-2 text-sm">
                <span className="font-medium text-slate-100">{g.symbol}</span>
                {pctChip(g.pct_change)}
              </li>
            ))}
          </ul>
        </Card>
        <Card title="Top losers" subtitle="Nifty 50">
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
    </div>
  );
}
