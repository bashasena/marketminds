import type { Snapshot } from "../../types";

/** Overlay live index, options, breadth & VIX (+ header date) onto a saved snapshot for the live strip only. */
export function mergeIndexOptionsFromLive(base: Snapshot, live: Snapshot): Snapshot {
  return {
    ...base,
    header: live.header,
    index: live.index,
    options: live.options,
    breadth: live.breadth,
    vix: live.vix,
    meta: {
      ...base.meta,
      ...live.meta,
      ui: base.meta?.ui ?? live.meta?.ui,
      data_warnings: live.meta?.data_warnings ?? base.meta?.data_warnings,
      market_id: live.meta?.market_id ?? base.meta?.market_id,
    },
  };
}
