/** Shared number / percent formatting for dashboard cards. */

export function fmtNum(n: number | null | undefined, digits = 2) {
  if (n === null || n === undefined || Number.isNaN(n)) return "—";
  return n.toLocaleString(undefined, { maximumFractionDigits: digits });
}

/** Many venues encode IV as decimal (0.22 = 22%). */
export function fmtIv(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  if (v >= 0 && v <= 1) return `${(v * 100).toFixed(1)}%`;
  if (v > 1 && v <= 100) return `${v.toFixed(1)}%`;
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

export function fmtDelta(v: number | null | undefined) {
  if (v === null || v === undefined || Number.isNaN(v)) return "—";
  return v.toLocaleString(undefined, { maximumFractionDigits: 3 });
}

export function pctChip(pct: number | null | undefined) {
  if (pct === null || pct === undefined) return <span className="text-slate-400">—</span>;
  const up = pct >= 0;
  return (
    <span className={up ? "text-emerald-400" : "text-rose-400"}>
      {up ? "+" : ""}
      {pct.toFixed(2)}%
    </span>
  );
}
