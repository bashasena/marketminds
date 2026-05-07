import { fmtNum, pctChip } from "../../lib/format";

type Props = {
  subtitle: string;
  vixLine: string;
  advances: number;
  declines: number;
  unchanged: number;
  vixLevel: number | null;
  vixPctChange: number | null;
};

/** Breadth + VIX strip for use inside the index card (no outer Card wrapper). */
export function MarketBreadthPanel({
  subtitle,
  vixLine,
  advances,
  declines,
  unchanged,
  vixLevel,
  vixPctChange,
}: Props) {
  return (
    <>
      <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">Market breadth</p>
      <p className="mt-0.5 text-xs text-slate-500">{subtitle}</p>
      <div className="mt-3 grid grid-cols-3 gap-2 text-center sm:gap-3">
        <div className="rounded-xl bg-emerald-950/30 p-2.5 sm:p-3">
          <p className="text-[11px] text-emerald-200/70 sm:text-xs">Advances</p>
          <p className="text-xl font-semibold tabular-nums text-emerald-200 sm:text-2xl">{advances}</p>
        </div>
        <div className="rounded-xl bg-rose-950/30 p-2.5 sm:p-3">
          <p className="text-[11px] text-rose-200/70 sm:text-xs">Declines</p>
          <p className="text-xl font-semibold tabular-nums text-rose-200 sm:text-2xl">{declines}</p>
        </div>
        <div className="rounded-xl bg-slate-800/60 p-2.5 sm:p-3">
          <p className="text-[11px] text-slate-400 sm:text-xs">Unch.</p>
          <p className="text-xl font-semibold tabular-nums text-slate-200 sm:text-2xl">{unchanged}</p>
        </div>
      </div>
      <p className="mt-3 flex flex-wrap items-center gap-2 text-xs text-slate-500">
        <span>
          {vixLine}: {fmtNum(vixLevel, 2)}
        </span>
        {vixPctChange !== null ? <span className="text-slate-300">({pctChip(vixPctChange)} day)</span> : null}
      </p>
    </>
  );
}
