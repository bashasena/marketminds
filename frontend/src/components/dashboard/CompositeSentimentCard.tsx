import { Card } from "../ui/Card";
import { fmtNum } from "../../lib/format";
import type { Snapshot } from "../../types";

type Props = {
  composite: Snapshot["composite"];
};

export function CompositeSentimentCard({ composite }: Props) {
  const score = composite.score_0_100;
  const meterColor =
    score >= 62
      ? "from-emerald-500/30 to-emerald-400/10"
      : score <= 42
        ? "from-rose-500/30 to-rose-400/10"
        : "from-amber-500/25 to-amber-400/10";

  return (
    <Card title="Composite sentiment" subtitle="0–100 (Bearish → Bullish)">
      <div className={`rounded-xl border border-slate-800 bg-gradient-to-br ${meterColor} p-4`}>
        <div className="flex items-center justify-between">
          <p className="text-5xl font-semibold text-white">{fmtNum(score, 1)}</p>
          <span className="rounded-full border border-slate-700 bg-slate-950/40 px-3 py-1 text-xs font-medium text-slate-200">
            {composite.label}
          </span>
        </div>
        <div className="mt-3 h-2 w-full overflow-hidden rounded-full bg-slate-900">
          <div
            className="h-full rounded-full bg-gradient-to-r from-rose-500 via-amber-400 to-emerald-400"
            style={{ width: `${Math.min(100, Math.max(0, score))}%` }}
          />
        </div>
        <p className="mt-3 text-sm text-slate-200/90">{composite.explanation}</p>
        <div className="mt-3 grid grid-cols-2 gap-2 text-[11px] text-slate-400">
          {Object.entries(composite.components).map(([k, v]) => (
            <div key={k} className="flex justify-between rounded-lg bg-slate-950/40 px-2 py-1">
              <span className="capitalize">{k}</span>
              <span className="text-slate-200">{v.toFixed(1)}</span>
            </div>
          ))}
        </div>
      </div>
    </Card>
  );
}
