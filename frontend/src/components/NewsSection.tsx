import { useEffect, useState } from "react";
import type { MarketId } from "../market/types";
import { Card } from "./ui/Card";

export type NewsItem = {
  title: string;
  url: string;
  published_at: string | null;
  source: string | null;
};

type NewsResponse = {
  market: string;
  items: NewsItem[];
  error: string | null;
};

export function NewsSection({ market }: { market: MarketId }) {
  const [items, setItems] = useState<NewsItem[]>([]);
  const [err, setErr] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setErr(null);
    (async () => {
      try {
        const r = await fetch(`/news?market=${encodeURIComponent(market)}&limit=12`);
        const j = (await r.json()) as NewsResponse;
        if (cancelled) return;
        if (!r.ok) {
          setErr(`${r.status} ${r.statusText}`);
          setItems([]);
          return;
        }
        setItems(j.items ?? []);
        setErr(j.error);
      } catch (e) {
        if (!cancelled) {
          setErr(e instanceof Error ? e.message : "Failed to load news");
          setItems([]);
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [market]);

  return (
    <Card title="Market news" subtitle="Headlines for the selected market (RSS)">
      {loading ? <p className="text-sm text-slate-500">Loading headlines…</p> : null}
      {!loading && err ? <p className="text-xs text-amber-200/80">{err}</p> : null}
      {!loading && !err && items.length === 0 ? (
        <p className="text-sm text-slate-500">No headlines returned. Try again later.</p>
      ) : null}
      <ul className="mt-2 divide-y divide-slate-800">
        {items.map((it) => (
          <li key={it.url} className="py-2.5 first:pt-0">
            <a
              href={it.url}
              target="_blank"
              rel="noopener noreferrer"
              className="text-sm font-medium text-sky-300/95 hover:text-sky-200"
            >
              {it.title}
            </a>
            <div className="mt-1 flex flex-wrap gap-x-2 text-[11px] text-slate-500">
              {it.source ? <span>{it.source}</span> : null}
              {it.published_at ? <span>{it.published_at}</span> : null}
            </div>
          </li>
        ))}
      </ul>
    </Card>
  );
}
