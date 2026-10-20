/** Bundle entry: defines <map-fusion-panel> (registered as a sidebar panel by the integration). */
import { MapFusionPanel } from "./panel.js";

declare const __PANEL_VERSION__: string;

try {
  if (!customElements.get("map-fusion-panel")) customElements.define("map-fusion-panel", MapFusionPanel);
} catch (err) {
  // eslint-disable-next-line no-console
  console.error("map-fusion-panel: could not define the element", err);
}

// eslint-disable-next-line no-console
console.info(`%c MAP-FUSION-PANEL %c v${__PANEL_VERSION__} `, "color:#fff;background:#03a9f4;font-weight:700;", "color:#03a9f4;background:#fff;font-weight:700;");
