// Builds the web app page into remotion/web-dist (served by: python -m visuals web).
// Run: npm run build:web     (after editing anything in web/ or src/)
import { build } from "esbuild";
import { copyFileSync, mkdirSync, rmSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const out = join(here, "..", "web-dist");
rmSync(out, { recursive: true, force: true });
mkdirSync(join(out, "assets"), { recursive: true });

await build({
  entryPoints: { app: join(here, "main.tsx") },
  outdir: join(out, "assets"),
  bundle: true,
  minify: true,
  sourcemap: false,
  format: "esm",
  target: "es2022",
  jsx: "automatic",
  loader: { ".css": "css" },
  define: { "process.env.NODE_ENV": '"production"' },
  logLevel: "warning",
});
copyFileSync(join(here, "index.html"), join(out, "index.html"));
console.log("Built web-dist/ (restart python -m visuals web if it is running)");
