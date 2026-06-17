import { DashboardTopBar } from "../components/DashboardTopBar";

const CYCLE_PHASES = [
  {
    phase: "Expansion",
    color: "text-emerald-400",
    border: "border-emerald-700",
    bg: "bg-emerald-950/40",
    description: "GDP rising, unemployment falling, consumer confidence high.",
    sectors: ["Technology", "Consumer Discretionary", "Industrials", "Financials"],
    avoid: ["Utilities", "Consumer Staples"],
  },
  {
    phase: "Peak",
    color: "text-yellow-400",
    border: "border-yellow-700",
    bg: "bg-yellow-950/40",
    description: "Growth slows, inflation peaks, interest rates at highs.",
    sectors: ["Energy", "Materials", "Healthcare"],
    avoid: ["Real Estate", "Technology"],
  },
  {
    phase: "Contraction",
    color: "text-red-400",
    border: "border-red-700",
    bg: "bg-red-950/40",
    description: "GDP falling, unemployment rising, consumer spending drops.",
    sectors: ["Consumer Staples", "Utilities", "Healthcare"],
    avoid: ["Financials", "Industrials", "Consumer Discretionary"],
  },
  {
    phase: "Trough",
    color: "text-sky-400",
    border: "border-sky-700",
    bg: "bg-sky-950/40",
    description: "GDP bottoms, rate cuts begin, early leading indicators turn up.",
    sectors: ["Financials", "Real Estate", "Consumer Discretionary"],
    avoid: ["Energy", "Materials"],
  },
];

const SECTOR_ETFS: Record<string, { etf: string; name: string }> = {
  Technology: { etf: "XLK", name: "SPDR Technology" },
  "Consumer Discretionary": { etf: "XLY", name: "SPDR Cons. Discretionary" },
  Industrials: { etf: "XLI", name: "SPDR Industrials" },
  Financials: { etf: "XLF", name: "SPDR Financials" },
  Energy: { etf: "XLE", name: "SPDR Energy" },
  Materials: { etf: "XLB", name: "SPDR Materials" },
  Healthcare: { etf: "XLV", name: "SPDR Healthcare" },
  "Consumer Staples": { etf: "XLP", name: "SPDR Cons. Staples" },
  Utilities: { etf: "XLU", name: "SPDR Utilities" },
  "Real Estate": { etf: "XLRE", name: "SPDR Real Estate" },
};

export function CycleStrategyPage() {
  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <DashboardTopBar hideMarket />

      <div className="mx-auto max-w-5xl px-4 py-8 space-y-8">
        {/* Header */}
        <div>
          <h1 className="text-2xl font-bold text-slate-100 tracking-tight">Cycle Strategy</h1>
          <p className="mt-1 text-sm text-slate-400">
            Sector rotation guide based on economic cycle phases. Rotate into favored sectors as the cycle shifts.
          </p>
        </div>

        {/* Cycle wheel overview */}
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {CYCLE_PHASES.map(({ phase, color, border, bg }) => (
            <div key={phase} className={`rounded-xl border ${border} ${bg} p-4 text-center`}>
              <span className={`text-sm font-semibold ${color}`}>{phase}</span>
            </div>
          ))}
        </div>

        {/* Phase cards */}
        <div className="space-y-6">
          {CYCLE_PHASES.map(({ phase, color, border, bg, description, sectors, avoid }) => (
            <div key={phase} className={`rounded-xl border ${border} ${bg} p-5 space-y-4`}>
              <div>
                <h2 className={`text-lg font-bold ${color}`}>{phase}</h2>
                <p className="mt-1 text-xs text-slate-400">{description}</p>
              </div>

              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {/* Favored sectors */}
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Favor</p>
                  <div className="space-y-1">
                    {sectors.map((s) => {
                      const etf = SECTOR_ETFS[s];
                      return (
                        <div key={s} className="flex items-center justify-between rounded-lg bg-slate-900/60 px-3 py-2">
                          <span className="text-xs text-slate-200">{s}</span>
                          {etf && (
                            <span className="text-xs font-mono text-emerald-400">{etf.etf}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>

                {/* Sectors to avoid */}
                <div>
                  <p className="mb-2 text-xs font-semibold uppercase tracking-wider text-slate-400">Avoid</p>
                  <div className="space-y-1">
                    {avoid.map((s) => {
                      const etf = SECTOR_ETFS[s];
                      return (
                        <div key={s} className="flex items-center justify-between rounded-lg bg-slate-900/60 px-3 py-2">
                          <span className="text-xs text-slate-200">{s}</span>
                          {etf && (
                            <span className="text-xs font-mono text-red-400">{etf.etf}</span>
                          )}
                        </div>
                      );
                    })}
                  </div>
                </div>
              </div>
            </div>
          ))}
        </div>

        {/* Sector ETF quick reference */}
        <div>
          <h2 className="mb-3 text-sm font-semibold uppercase tracking-wider text-slate-400">Sector ETF Reference</h2>
          <div className="grid grid-cols-2 gap-2 sm:grid-cols-3 md:grid-cols-5">
            {Object.entries(SECTOR_ETFS).map(([sector, { etf, name }]) => (
              <div key={etf} className="rounded-lg border border-slate-800 bg-slate-900 px-3 py-2">
                <p className="text-sm font-mono font-bold text-sky-400">{etf}</p>
                <p className="text-xs text-slate-400 truncate">{name}</p>
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
