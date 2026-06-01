import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { useMarket } from "../market/MarketContext";
import { MARKETS } from "../market/types";

export function DashboardTopBar({ hideMarket = false }: { hideMarket?: boolean }) {
  const { market, setMarket } = useMarket();
  const [strategiesOpen, setStrategiesOpen] = useState(false);
  const strategiesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!strategiesOpen) return;
    const onPointerDown = (e: MouseEvent) => {
      if (strategiesRef.current && !strategiesRef.current.contains(e.target as Node)) {
        setStrategiesOpen(false);
      }
    };
    document.addEventListener("mousedown", onPointerDown);
    return () => document.removeEventListener("mousedown", onPointerDown);
  }, [strategiesOpen]);

  return (
    <div className="sticky top-0 z-50 border-b border-slate-800 bg-slate-950/95 px-4 py-3 shadow-md shadow-black/20 backdrop-blur">
      <div className="mx-auto flex max-w-6xl flex-wrap items-center justify-between gap-3">
        <p className="min-w-0 text-xs font-medium uppercase tracking-widest text-slate-400">Daily market snapshot</p>
        <div className="flex flex-wrap items-center gap-2">
          {!hideMarket && (
            <>
              <label className="sr-only" htmlFor="market-select">Market</label>
              <select
                id="market-select"
                value={market}
                onChange={(e) => setMarket(e.target.value as typeof market)}
                className="max-w-[min(100%,220px)] rounded-lg border border-slate-600 bg-slate-900 px-2 py-1.5 text-xs text-slate-100 focus:border-slate-500 focus:outline-none focus:ring-1 focus:ring-slate-500"
              >
                {MARKETS.map((m) => (
                  <option key={m.id} value={m.id}>{m.label}</option>
                ))}
              </select>
            </>
          )}
          <div className="relative" ref={strategiesRef}>
            <button
              type="button"
              onClick={() => setStrategiesOpen((open) => !open)}
              className="shrink-0 rounded-lg border border-slate-600 bg-slate-800/80 px-3 py-1.5 text-xs font-medium text-slate-100 hover:bg-slate-700"
              aria-expanded={strategiesOpen}
              aria-haspopup="menu"
            >
              Strategies
            </button>
            {strategiesOpen ? (
              <div
                role="menu"
                className="absolute right-0 top-full z-50 mt-1 min-w-[160px] rounded-lg border border-slate-700 bg-slate-900 py-1 shadow-lg shadow-black/30"
              >
                <Link
                  to="/volume-strategy"
                  role="menuitem"
                  className="block px-3 py-2 text-xs text-slate-100 hover:bg-slate-800"
                  onClick={() => setStrategiesOpen(false)}
                >
                  Volume strategy
                </Link>
              </div>
            ) : null}
          </div>
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
