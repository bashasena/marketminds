import { useLiveIndexOptionsStrip } from "../../hooks/useLiveIndexOptionsStrip";
import type { MarketId } from "../../market/types";
import type { Snapshot } from "../../types";
import { CompositeSentimentCard } from "./CompositeSentimentCard";
import { IndexSnapshotCard } from "./IndexSnapshotCard";
import { OptionsSnapshotCard } from "./OptionsSnapshotCard";

type Props = {
  market: MarketId;
  /** Saved snapshot for this market (`live=false`); live mode overlays index/options only. */
  base: Snapshot;
};

export function LiveIndexOptionsStrip({ market, base }: Props) {
  const { liveOn, setLiveOn, stripSnapshot, liveErr, polling } = useLiveIndexOptionsStrip(market, base);
  const ui = stripSnapshot.meta?.ui;
  const indexTitle = ui?.index_title ?? "Nifty 50";
  const indexSub = ui?.index_subtitle ?? "Cash index";
  const breadthSub = ui?.breadth_subtitle ?? "Nifty 50 constituents";
  const vixLine = ui?.vix_line ?? "India VIX";

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/25 p-4 shadow-inner shadow-black/10">
      <div className="flex flex-wrap items-center justify-between gap-3 border-b border-slate-800/80 pb-3">
        <div className="min-w-0">
          <p className="text-xs font-medium uppercase tracking-widest text-slate-500">Index, breadth &amp; option OI</p>
          <p className="mt-0.5 text-xs text-slate-500">
            <span className="text-slate-400">Live off</span> uses the saved database snapshot (refresh via Admin).{" "}
            <span className="text-slate-400">Live on</span> refreshes index, market breadth, VIX, and option OI every 15 seconds.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-3">
          {polling ? <span className="text-xs tabular-nums text-slate-500">Updating…</span> : null}
          <div className="flex items-center gap-2 rounded-lg border border-slate-600 bg-slate-950/50 px-2 py-1.5">
            <span className={`text-xs font-medium ${liveOn ? "text-slate-500" : "text-emerald-300/90"}`}>Off</span>
            <button
              type="button"
              role="switch"
              aria-checked={liveOn}
              onClick={() => setLiveOn(!liveOn)}
              className={`relative h-7 w-12 shrink-0 rounded-full transition-colors focus:outline-none focus:ring-2 focus:ring-amber-500/50 ${
                liveOn ? "bg-amber-600/90" : "bg-slate-600"
              }`}
            >
              <span
                className={`absolute top-0.5 left-0.5 block h-6 w-6 rounded-full bg-white shadow transition-transform ${
                  liveOn ? "translate-x-5" : "translate-x-0"
                }`}
              />
            </button>
            <span className={`text-xs font-medium ${liveOn ? "text-amber-200" : "text-slate-500"}`}>Live</span>
          </div>
        </div>
      </div>

      {liveErr ? (
        <div className="mt-3 rounded-lg border border-rose-900/40 bg-rose-950/20 px-3 py-2 text-xs text-rose-200/90">
          Live strip could not refresh: {liveErr}. Showing saved values until the next successful poll.
        </div>
      ) : null}

      <div className="mt-4 grid grid-cols-1 gap-4 lg:grid-cols-2">
        <IndexSnapshotCard
          indexTitle={indexTitle}
          indexSub={indexSub}
          close={stripSnapshot.index.close}
          pctChange={stripSnapshot.index.pct_change}
          open={stripSnapshot.index.open}
          high={stripSnapshot.index.high}
          low={stripSnapshot.index.low}
          narrative={stripSnapshot.index.narrative}
          breadthSubtitle={breadthSub}
          vixLine={vixLine}
          advances={stripSnapshot.breadth.advances}
          declines={stripSnapshot.breadth.declines}
          unchanged={stripSnapshot.breadth.unchanged}
          vixLevel={stripSnapshot.vix.level}
          vixPctChange={stripSnapshot.vix.pct_change}
        />
        <OptionsSnapshotCard data={stripSnapshot} />
      </div>

      <div className="mt-4">
        <CompositeSentimentCard composite={stripSnapshot.composite} />
      </div>
    </section>
  );
}
