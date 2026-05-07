import type { Snapshot } from "../../types";

/** US markets only — avoids saying "add API key" when key is set but data/cache is stale. */
export function usOptionsEmptyFollowUp(data: Snapshot) {
  const warnings = data.meta?.data_warnings ?? [];
  const noDatabentoKey = warnings.some((w) => w.includes("set DATABENTO_API_KEY"));
  const databentoErr = warnings.some((w) => w.startsWith("us_options_databento:"));
  const hasDetail = Boolean(data.databento_options);

  if (noDatabentoKey) {
    return (
      <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
        US ETF options use Databento OPRA (parent symbology). Add{" "}
        <span className="text-slate-300">DATABENTO_API_KEY</span> to the <span className="text-slate-300">project root</span> dotenv (next to{" "}
        <span className="text-slate-300">docker-compose.yml</span>), restart the <span className="text-slate-300">api</span> container, then use{" "}
        <span className="text-slate-300">Live</span> on the dashboard or Admin to refresh the snapshot.
      </p>
    );
  }
  if (databentoErr) {
    return (
      <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
        Databento could not return options for this build. Check <span className="text-slate-300">Admin → Data notes</span> on the saved snapshot for the error text (subscription,
        dataset, or date range).
      </p>
    );
  }
  if (hasDetail) {
    return (
      <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
        OI is still zero for this expiry/session. Check the <span className="text-slate-300">Databento OPRA</span> section below and Admin data notes; the venue may
        not have published joinable statistics for that day.
      </p>
    );
  }
  return (
    <p className="mt-2 text-xs leading-relaxed text-amber-200/85">
      This view is missing a <span className="text-slate-300">Databento</span> options block — usually a <span className="text-slate-300">saved</span> or{" "}
      <span className="text-slate-300">cached</span> snapshot from before the key was wired in. Turn on <span className="text-slate-300">Live</span> for the
      index/options strip, use Admin live refresh, run <span className="text-slate-300">docker compose up --build -d</span> so the API matches this repo, then
      hard-refresh the browser.
    </p>
  );
}
