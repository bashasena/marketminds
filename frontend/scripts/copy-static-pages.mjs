/**
 * Copy standalone HTML files from static-pages/ into the Vite output (or public/ for dev).
 * Usage: node scripts/copy-static-pages.mjs [destDir]
 * Default dest: dist/
 */
import { cpSync, existsSync, mkdirSync, readdirSync } from "fs";
import { dirname, join } from "path";
import { fileURLToPath } from "url";

const __dirname = dirname(fileURLToPath(import.meta.url));
const src = join(__dirname, "../static-pages");
const dest = join(__dirname, "..", process.argv[2] || "dist");

if (!existsSync(src)) {
  console.warn("static-pages/: directory not found, skipping copy");
  process.exit(0);
}

mkdirSync(dest, { recursive: true });
let count = 0;
for (const name of readdirSync(src)) {
  if (!name.endsWith(".html")) continue;
  cpSync(join(src, name), join(dest, name));
  console.log(`static-pages: ${name} -> ${dest}/`);
  count += 1;
}
if (count === 0) {
  console.log("static-pages/: no .html files to copy");
}
