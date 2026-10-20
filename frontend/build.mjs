// Bundles the panel into custom_components/map_fusion/frontend/, which ships
// with the integration (HACS installs it as is, no Node toolchain needed).
import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import * as esbuild from "esbuild";

const here = dirname(fileURLToPath(import.meta.url));
const pkg = JSON.parse(readFileSync(resolve(here, "package.json"), "utf8"));

const options = {
  entryPoints: [resolve(here, "src/main.ts")],
  outfile: resolve(here, "../custom_components/map_fusion/frontend/map-fusion-panel.js"),
  bundle: true,
  format: "esm",
  // Old on purpose: wall tablets and embedded WebViews choke on newer syntax.
  target: "es2015",
  minify: true,
  legalComments: "none",
  banner: { js: `/*! map-fusion-panel v${pkg.version} built from frontend/src, do not edit */` },
  define: { __PANEL_VERSION__: JSON.stringify(pkg.version) },
};

if (process.argv.includes("--watch")) {
  const ctx = await esbuild.context(options);
  await ctx.watch();
  console.log(`watching… → ${options.outfile}`);
} else {
  await esbuild.build(options);
  console.log(`built v${pkg.version} → ${options.outfile}`);
}
