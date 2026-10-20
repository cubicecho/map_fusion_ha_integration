import { readFileSync } from "node:fs";
import { dirname, resolve } from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

// Old tablets and WebViews can't parse newer syntax, and one syntax error
// kills the whole panel. Check the committed bundle.
const BUNDLE = readFileSync(
  resolve(dirname(fileURLToPath(import.meta.url)), "../../custom_components/map_fusion/frontend/map-fusion-panel.js"),
  "utf8",
);

const FORBIDDEN: Array<[string, string]> = [
  ["??=", "logical assignment (ES2021)"],
  ["||=", "logical assignment (ES2021)"],
  ["&&=", "logical assignment (ES2021)"],
  ["?.", "optional chaining (ES2020)"],
  ["??", "nullish coalescing (ES2020)"],
  [".flat(", "Array.prototype.flat (ES2019)"],
  [".replaceAll(", "String.prototype.replaceAll (ES2021)"],
  ["Object.hasOwn(", "Object.hasOwn (ES2022)"],
];

describe("the committed bundle", () => {
  it.each(FORBIDDEN)("does not use %s (%s)", (token) => {
    expect(BUNDLE).not.toContain(token);
  });

  it("carries the build banner", () => {
    expect(BUNDLE.startsWith("/*! map-fusion-panel v")).toBe(true);
  });
});
