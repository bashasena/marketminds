import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { DashboardTopBar } from "../components/DashboardTopBar";

type MarketFilter = "nse" | "nasdaq" | "both";
type Signal = "bullish" | "bearish" | "neutral";

type Stock = { sym: string; name: string };
type StockData = Stock & {
  avg30: number;
  curVol: number;
  volRatio: number;
  pcr: number;
  oiTrend: string;
  signal: Signal;
};

type LogEntry = { time: string; msg: string; type: "info" | "alert" | "warn" };

const NSE_STOCKS: Stock[] = [
  { sym: "RELIANCE", name: "Reliance Industries" },
  { sym: "TCS", name: "Tata Consultancy" },
  { sym: "HDFCBANK", name: "HDFC Bank" },
  { sym: "INFY", name: "Infosys" },
  { sym: "ICICIBANK", name: "ICICI Bank" },
  { sym: "HINDUNILVR", name: "HUL" },
  { sym: "ITC", name: "ITC Ltd" },
  { sym: "KOTAKBANK", name: "Kotak Mahindra" },
  { sym: "LT", name: "L&T" },
  { sym: "AXISBANK", name: "Axis Bank" },
  { sym: "BAJFINANCE", name: "Bajaj Finance" },
  { sym: "WIPRO", name: "Wipro" },
  { sym: "SBIN", name: "SBI" },
  { sym: "MARUTI", name: "Maruti Suzuki" },
  { sym: "TITAN", name: "Titan" },
  { sym: "ASIANPAINT", name: "Asian Paints" },
  { sym: "SUNPHARMA", name: "Sun Pharma" },
  { sym: "NTPC", name: "NTPC" },
  { sym: "POWERGRID", name: "Power Grid" },
  { sym: "ADANIENT", name: "Adani Enterprises" },
];

const NASDAQ_STOCKS: Stock[] = [
  { sym: "AAPL", name: "Apple" },
  { sym: "MSFT", name: "Microsoft" },
  { sym: "NVDA", name: "NVIDIA" },
  { sym: "AMZN", name: "Amazon" },
  { sym: "META", name: "Meta" },
  { sym: "GOOGL", name: "Alphabet" },
  { sym: "TSLA", name: "Tesla" },
  { sym: "AVGO", name: "Broadcom" },
  { sym: "COST", name: "Costco" },
  { sym: "NFLX", name: "Netflix" },
  { sym: "AMD", name: "AMD" },
  { sym: "ADBE", name: "Adobe" },
  { sym: "QCOM", name: "Qualcomm" },
  { sym: "INTC", name: "Intel" },
  { sym: "CSCO", name: "Cisco" },
];

function rnd(min: number, max: number) {
  return Math.random() * (max - min) + min;
}

function fmt(n: number) {
  if (n >= 1e9) return `${(n / 1e9).toFixed(2)}B`;
  if (n >= 1e6) return `${(n / 1e6).toFixed(1)}M`;
  if (n >= 1e3) return `${(n / 1e3).toFixed(0)}K`;
  return n.toString();
}

function generateStockData(stock: Stock): StockData {
  const avg30 = Math.round(rnd(2e6, 80e6));
  const volRatio = rnd(0.6, 5.5);
  const curVol = Math.round(avg30 * volRatio);
  const pcr = parseFloat(rnd(0.4, 2.2).toFixed(2));
  const oiTrend = ["Rising", "Falling", "Flat"][Math.floor(rnd(0, 3))];
  let signal: Signal = "neutral";
  if (pcr < 0.8 && volRatio > 1.5) signal = "bullish";
  else if (pcr > 1.3 && volRatio > 1.5) signal = "bearish";
  return { ...stock, avg30, curVol, volRatio: parseFloat(volRatio.toFixed(2)), pcr, oiTrend, signal };
}

function formatTime(d = new Date()) {
  return `${d.getHours().toString().padStart(2, "0")}:${d.getMinutes().toString().padStart(2, "0")}:${d.getSeconds().toString().padStart(2, "0")}`;
}

export function VolumeStrategyPage() {
  const [market, setMarket] = useState<MarketFilter>("nse");
  const [thresh, setThresh] = useState(1.5);
  const [pcrMin, setPcrMin] = useState(0.7);
  const [scanning, setScanning] = useState(false);
  const [statusColor, setStatusColor] = useState("#00c896");
  const [alerts, setAlerts] = useState<StockData[]>([]);
  const [metrics, setMetrics] = useState({ scanned: "—", alerts: "—", bull: "—", bear: "—", time: "—" });
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [emptyMessage, setEmptyMessage] = useState("Run a scan to detect volume surges");

  const appendLog = useCallback((msg: string, type: LogEntry["type"] = "info") => {
    setLogs((prev) => [{ time: formatTime(), msg, type }, ...prev].slice(0, 40));
  }, []);

  const runScan = useCallback(() => {
    setScanning(true);
    setStatusColor("#f5a623");
    setEmptyMessage("Scanning...");
    appendLog(`Scan started — market: ${market.toUpperCase()}, threshold: ${thresh}x`, "info");

    let pool: Stock[] = [];
    if (market === "nse" || market === "both") pool = [...pool, ...NSE_STOCKS];
    if (market === "nasdaq" || market === "both") pool = [...pool, ...NASDAQ_STOCKS];

    window.setTimeout(() => {
      const all = pool.map(generateStockData);
      const filtered = all.filter((s) => s.volRatio >= thresh && s.pcr >= pcrMin);
      filtered.sort((a, b) => b.volRatio - a.volRatio);

      const bull = filtered.filter((s) => s.signal === "bullish").length;
      const bear = filtered.filter((s) => s.signal === "bearish").length;
      const tStr = formatTime().slice(0, 5);

      setMetrics({
        scanned: String(all.length),
        alerts: String(filtered.length),
        bull: String(bull),
        bear: String(bear),
        time: tStr,
      });
      setAlerts(filtered);
      setStatusColor("#00c896");
      setScanning(false);
      setEmptyMessage(
        filtered.length === 0 ? `No stocks exceed ${thresh}x volume threshold right now` : "",
      );

      appendLog(`Scan complete — ${all.length} scanned, ${filtered.length} alerts fired`, "alert");
      filtered.forEach((s) =>
        appendLog(`ALERT: ${s.sym} — Vol ${s.volRatio}x avg | PCR ${s.pcr} | ${s.signal.toUpperCase()}`, "warn"),
      );
    }, 900);
  }, [appendLog, market, pcrMin, thresh]);

  useEffect(() => {
    runScan();
  }, []); // eslint-disable-line react-hooks/exhaustive-deps -- initial scan on mount

  const logColor = (type: LogEntry["type"]) =>
    type === "alert" ? "#00c896" : type === "warn" ? "#f5a623" : "#94a3b8";

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100">
      <DashboardTopBar />
      <div className="mx-auto max-w-6xl px-4 py-10 pb-16">
        <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
          <Link to="/" className="text-xs text-slate-400 hover:text-slate-200">
            ← Back to dashboard
          </Link>
        </div>

        <div className="volume-scanner">
          <div className="mb-6 flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-2.5">
              <div
                className="h-2.5 w-2.5 rounded-full"
                style={{ background: statusColor, boxShadow: `0 0 0 0 ${statusColor}80`, animation: "pulse 1.6s ease-in-out infinite" }}
              />
              <h1 className="text-lg font-medium tracking-tight text-white">Volume Surge Scanner</h1>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <select
                value={market}
                onChange={(e) => setMarket(e.target.value as MarketFilter)}
                className="rounded-md border border-slate-600 bg-slate-900 px-2.5 py-1.5 text-sm text-slate-100"
              >
                <option value="nse">NSE (Nifty 50)</option>
                <option value="nasdaq">NASDAQ 100</option>
                <option value="both">Both Markets</option>
              </select>
              <button
                type="button"
                onClick={runScan}
                disabled={scanning}
                className="rounded-md border border-emerald-500/30 bg-emerald-500/10 px-4 py-1.5 text-sm font-medium text-emerald-400 hover:bg-emerald-500/20 disabled:opacity-60"
              >
                Scan Now
              </button>
            </div>
          </div>

          <div className="mb-6 flex flex-wrap items-center gap-3 text-sm text-slate-400">
            <label>Volume threshold:</label>
            <input
              type="range"
              min={1}
              max={5}
              step={0.1}
              value={thresh}
              onChange={(e) => setThresh(parseFloat(e.target.value))}
              className="w-36"
            />
            <span className="font-mono text-sm font-medium text-emerald-400">{thresh.toFixed(1)}x</span>
            <label className="ml-3">Min PCR filter:</label>
            <input
              type="range"
              min={0.5}
              max={2}
              step={0.1}
              value={pcrMin}
              onChange={(e) => setPcrMin(parseFloat(e.target.value))}
              className="w-36"
            />
            <span className="font-mono text-sm font-medium text-emerald-400">{pcrMin.toFixed(1)}</span>
          </div>

          <div className="mb-6 grid grid-cols-[repeat(auto-fit,minmax(140px,1fr))] gap-2.5">
            {[
              ["Stocks Scanned", metrics.scanned, ""],
              ["Alerts Fired", metrics.alerts, "text-emerald-400"],
              ["Bullish Signals", metrics.bull, "text-emerald-400"],
              ["Bearish Signals", metrics.bear, "text-red-400"],
              ["Last Scan", metrics.time, "text-sm"],
            ].map(([label, val, cls]) => (
              <div key={String(label)} className="rounded-lg border border-slate-800 bg-slate-900/40 p-3">
                <p className="text-xs text-slate-500">{label}</p>
                <p className={`mt-1 font-mono text-xl font-medium text-white ${cls}`}>{val}</p>
              </div>
            ))}
          </div>

          <p className="mb-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Alert Results</p>
          <div className="mb-1 grid grid-cols-[70px_1fr_90px_90px_90px_90px] gap-2.5 px-3.5 text-xs font-medium text-slate-500">
            <span>SYMBOL</span>
            <span>VOLUME vs 30D AVG</span>
            <span>PCR</span>
            <span>VOL RATIO</span>
            <span>OI TREND</span>
            <span>SIGNAL</span>
          </div>

          {alerts.length === 0 ? (
            <div className="rounded-lg border border-dashed border-slate-700 py-8 text-center text-sm text-slate-400">
              {emptyMessage}
            </div>
          ) : (
            <div className="mb-6 flex flex-col gap-2">
              {alerts.map((s, i) => {
                const pct = Math.min(Math.round((s.curVol / s.avg30) * 100), 400);
                const barColor =
                  s.signal === "bullish" ? "#00c896" : s.signal === "bearish" ? "#ff4f4f" : "#f5a623";
                const pcrClass = s.pcr < 0.8 ? "bull" : s.pcr > 1.3 ? "bear" : "neut";
                const pcrLabel = s.pcr < 0.8 ? "Bullish" : s.pcr > 1.3 ? "Bearish" : "Neutral";
                const oiColor =
                  s.oiTrend === "Rising" ? "#00c896" : s.oiTrend === "Falling" ? "#ff4f4f" : "#94a3b8";
                return (
                  <div
                    key={`${s.sym}-${i}`}
                    className={`grid grid-cols-[70px_1fr_90px_90px_90px_90px] items-center gap-2.5 rounded-lg border border-slate-800 bg-slate-950/40 px-3.5 py-2.5 border-l-[3px] ${
                      s.signal === "bullish"
                        ? "border-l-emerald-500"
                        : s.signal === "bearish"
                          ? "border-l-red-500"
                          : "border-l-amber-500"
                    }`}
                  >
                    <span className="font-mono text-sm font-semibold">{s.sym}</span>
                    <div className="flex flex-col gap-0.5">
                      <div className="h-1.5 overflow-hidden rounded bg-slate-800">
                        <div
                          className="h-full rounded transition-all duration-500"
                          style={{ width: `${Math.min(pct / 4, 100)}%`, background: barColor }}
                        />
                      </div>
                      <span className="font-mono text-[11px] text-slate-500">
                        {fmt(s.curVol)} / avg {fmt(s.avg30)}
                      </span>
                    </div>
                    <span
                      className={`rounded px-2 py-1 text-center font-mono text-xs font-medium ${
                        pcrClass === "bull"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : pcrClass === "bear"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {s.pcr}
                      <br />
                      <span className="text-[10px] opacity-70">{pcrLabel}</span>
                    </span>
                    <span
                      className={`text-center font-mono text-sm font-semibold ${s.volRatio >= 2.5 ? "text-emerald-400" : "text-amber-400"}`}
                    >
                      {s.volRatio}x
                    </span>
                    <span className="text-center text-xs font-medium" style={{ color: oiColor }}>
                      {s.oiTrend}
                    </span>
                    <span
                      className={`rounded-full px-2 py-0.5 text-center text-[11px] font-medium ${
                        s.signal === "bullish"
                          ? "bg-emerald-500/10 text-emerald-400"
                          : s.signal === "bearish"
                            ? "bg-red-500/10 text-red-400"
                            : "bg-amber-500/10 text-amber-400"
                      }`}
                    >
                      {s.signal.charAt(0).toUpperCase() + s.signal.slice(1)}
                    </span>
                  </div>
                );
              })}
            </div>
          )}

          <p className="mb-2.5 text-xs font-medium uppercase tracking-wide text-slate-500">Activity Log</p>
          <div className="max-h-36 overflow-y-auto rounded-lg border border-slate-800 bg-slate-900/40 p-3">
            {logs.length === 0 ? (
              <p className="font-mono text-xs text-slate-500">Waiting for scan...</p>
            ) : (
              logs.map((entry, i) => (
                <div key={i} className="border-b border-slate-800 py-1 font-mono text-xs last:border-b-0">
                  <span className="mr-2 text-emerald-400">{entry.time}</span>
                  <span style={{ color: logColor(entry.type) }}>{entry.msg}</span>
                </div>
              ))
            )}
          </div>
        </div>
      </div>
      <style>{`
        @keyframes pulse {
          0%, 100% { box-shadow: 0 0 0 0 rgba(0, 200, 150, 0.5); }
          50% { box-shadow: 0 0 0 5px rgba(0, 200, 150, 0); }
        }
      `}</style>
    </div>
  );
}
