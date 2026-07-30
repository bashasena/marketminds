/**
 * Copy standalone HTML from static-pages/ into the Vite output and generate pages.html catalog.
 * Usage: node scripts/copy-static-pages.mjs [destDir]
 */
import { cpSync, existsSync, mkdirSync, readdirSync, readFileSync, writeFileSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname, "../static-pages");
const dest = join(__dirname, "..", process.argv[2] || "dist");
const CATALOG_NAME = "pages.html";

if (!existsSync(src)) {
  console.warn("static-pages/: directory not found, skipping copy");
  process.exit(0);
}

mkdirSync(dest, { recursive: true });

function readTitle(filePath) {
  try {
    const html = readFileSync(filePath, "utf8");
    const m = html.match(/<title[^>]*>([^<]+)<\/title>/i);
    return m ? m[1].trim() : null;
  } catch {
    return null;
  }
}

function labelFromFilename(name) {
  return name
    .replace(/\.html$/i, "")
    .replace(/[-_]+/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

const entries = readdirSync(src)
  .filter((name) => name.endsWith(".html") && name !== CATALOG_NAME)
  .sort((a, b) => a.localeCompare(b))
  .map((name) => {
    const title = readTitle(join(src, name)) || labelFromFilename(name);
    return { name, title, href: `/${name}` };
  });

for (const { name } of entries) {
  cpSync(join(src, name), join(dest, name));
  console.log(`static-pages: ${name} -> ${dest}/`);
}

const listItems =
  entries.length === 0
    ? `<p class="empty">No pages in <code>frontend/static-pages/</code> yet.</p>`
    : `<ul class="page-list">${entries
        .map(
          ({ name, title, href }) => `
      <li>
        <a href="${href}">
          <span class="page-title">${escapeHtml(title)}</span>
          <span class="page-file">${escapeHtml(name)}</span>
        </a>
      </li>`,
        )
        .join("")}</ul>`;

const catalogHtml = `<!doctype html>
<html lang="en">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <title>Static pages</title>
    <style>
      * { box-sizing: border-box; margin: 0; padding: 0; }
      body {
        font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
        background: #0f172a;
        color: #e2e8f0;
        min-height: 100vh;
        padding: 2rem 1rem 3rem;
      }
      .wrap { max-width: 40rem; margin: 0 auto; }
      h1 { font-size: 1.75rem; font-weight: 600; margin-bottom: 0.5rem; }
      .sub { color: #94a3b8; font-size: 0.95rem; margin-bottom: 1.75rem; line-height: 1.5; }
      code {
        font-family: ui-monospace, monospace;
        font-size: 0.85em;
        background: #1e293b;
        padding: 0.12rem 0.35rem;
        border-radius: 0.25rem;
        color: #7dd3fc;
      }
      .page-list { list-style: none; display: flex; flex-direction: column; gap: 0.65rem; }
      .page-list a {
        display: flex;
        flex-wrap: wrap;
        align-items: baseline;
        justify-content: space-between;
        gap: 0.5rem 1rem;
        padding: 1rem 1.15rem;
        border: 1px solid #334155;
        border-radius: 0.75rem;
        background: #1e293b;
        color: inherit;
        text-decoration: none;
        transition: border-color 0.15s, background 0.15s;
      }
      .page-list a:hover {
        border-color: #34d399;
        background: #172033;
      }
      .page-title { font-weight: 600; color: #f8fafc; }
      .page-file { font-family: ui-monospace, monospace; font-size: 0.8rem; color: #64748b; }
      .empty { color: #94a3b8; padding: 1.5rem; border: 1px dashed #334155; border-radius: 0.75rem; }
      .meta {
        margin-top: 2rem;
        font-size: 0.85rem;
        color: #64748b;
      }
      .meta a { color: #34d399; text-decoration: none; }
      .meta a:hover { text-decoration: underline; }
      .count {
        display: inline-block;
        margin-bottom: 1rem;
        padding: 0.25rem 0.65rem;
        border-radius: 999px;
        background: #064e3b;
        color: #6ee7b7;
        font-size: 0.75rem;
        font-weight: 600;
      }
    </style>
  </head>
  <body>
    <div class="wrap">
      <h1>Static pages</h1>
      <p class="sub">
        Auto-generated from <code>frontend/static-pages/</code>.
        Add a <code>.html</code> file there and rebuild to see it here.
      </p>
      <span class="count">${entries.length} page${entries.length === 1 ? "" : "s"}</span>
      ${listItems}
      <p class="meta">
        <a href="/">← Back to dashboard</a>
        · Updated at build time
      </p>
    </div>
  </body>
</html>
`;

writeFileSync(join(dest, CATALOG_NAME), catalogHtml, "utf8");
console.log(`static-pages: ${CATALOG_NAME} (catalog, ${entries.length} entries) -> ${dest}/`);

function escapeHtml(s) {
  return s
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;");
}
