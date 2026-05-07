import { Card } from "../ui/Card";
import { fmtNum, pctChip } from "../../lib/format";
import { MarketBreadthPanel } from "./MarketBreadthPanel";

type Props = {
  indexTitle: string;
  indexSub: string;
  close: number | null;
  pctChange: number | null;
  open: number | null;
  high: number | null;
  low: number | null;
  narrative: string;
  breadthSubtitle: string;
  vixLine: string;
  advances: number;
  declines: number;
  unchanged: number;
  vixLevel: number | null;
  vixPctChange: number | null;
};

export function IndexSnapshotCard({
  indexTitle,
  indexSub,
  close,
  pctChange,
  open,
  high,
  low,
  narrative,
  breadthSubtitle,
  vixLine,
  advances,
  declines,
  unchanged,
  vixLevel,
  vixPctChange,
}: Props) {
  return (
    <Card title={indexTitle} subtitle={indexSub}>
      <div className="flex items-end justify-between gap-3">
        <div>
          <p className="text-4xl font-semibold tracking-tight text-white">{fmtNum(close, 2)}</p>
          <p className="mt-2 text-sm text-slate-300">{pctChip(pctChange)} day</p>
        </div>
        <div className="text-right text-xs text-slate-400">
          <div>O {fmtNum(open)}</div>
          <div>H {fmtNum(high)}</div>
          <div>L {fmtNum(low)}</div>
        </div>
      </div>
      <p className="mt-4 text-sm leading-relaxed text-slate-300">{narrative}</p>

      <div className="mt-5 border-t border-slate-800 pt-4">
        <MarketBreadthPanel
          subtitle={breadthSubtitle}
          vixLine={vixLine}
          advances={advances}
          declines={declines}
          unchanged={unchanged}
          vixLevel={vixLevel}
          vixPctChange={vixPctChange}
        />
      </div>
    </Card>
  );
}
