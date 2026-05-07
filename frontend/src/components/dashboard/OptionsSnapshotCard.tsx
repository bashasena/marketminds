import { Card } from "../ui/Card";
import { fmtNum } from "../../lib/format";
import type { Snapshot } from "../../types";
import { usOptionsEmptyFollowUp } from "./optionsEmptyHints";

type Props = {
  /** Snapshot slice used for options + meta (warnings, market_id); typically merged when live strip is on. */
  data: Snapshot;
};

export function OptionsSnapshotCard({ data }: Props) {
  const o = data.options;
  return (
    <Card title="Options positioning" subtitle={`${o.symbol}${o.expiry ? ` · ${o.expiry}` : ""}`}>
      <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
          <p className="text-xs text-slate-500">PCR (OI)</p>
          <p className="mt-1 text-xl font-semibold text-white">{fmtNum(o.pcr_oi, 3)}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
          <p className="text-xs text-slate-500">Total call OI</p>
          <p className="mt-1 text-xl font-semibold text-white">{fmtNum(o.call_oi_total, 0)}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3">
          <p className="text-xs text-slate-500">Total put OI</p>
          <p className="mt-1 text-xl font-semibold text-white">{fmtNum(o.put_oi_total, 0)}</p>
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 md:col-span-1">
          <p className="text-xs text-slate-500">Put OI wall (support)</p>
          <p className="mt-1 text-xl font-semibold text-white">{fmtNum(o.support_strike_put_oi, 0)}</p>
          {o.put_wall_oi != null && o.put_wall_oi > 0 ? <p className="mt-0.5 text-xs text-slate-500">Max OI: {fmtNum(o.put_wall_oi, 0)}</p> : null}
        </div>
        <div className="rounded-xl border border-slate-800 bg-slate-950/40 p-3 md:col-span-1">
          <p className="text-xs text-slate-500">Call OI wall (resistance)</p>
          <p className="mt-1 text-xl font-semibold text-white">{fmtNum(o.resistance_strike_call_oi, 0)}</p>
          {o.call_wall_oi != null && o.call_wall_oi > 0 ? <p className="mt-0.5 text-xs text-slate-500">Max OI: {fmtNum(o.call_wall_oi, 0)}</p> : null}
        </div>
      </div>
      <p className="mt-3 text-sm text-slate-300">{o.note}</p>
      {o.pcr_oi == null && o.call_oi_total === 0 && o.put_oi_total === 0 ? (
        data.meta?.market_id === "us_broad" || data.meta?.market_id === "usa_nasdaq" ? (
          usOptionsEmptyFollowUp(data)
        ) : (
          <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
            If this never populates, the backend likely got an empty response from NSE (common when the server runs outside India or NSE blocks automated
            access). Check the amber notice under the page title, use <span className="text-slate-300">Live</span> on the strip above, or run the stack from a
            network that can open the NSE option chain in a browser.
          </p>
        )
      ) : null}
    </Card>
  );
}
