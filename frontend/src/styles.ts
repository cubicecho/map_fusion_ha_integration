export const STYLES = `
:host {
  display: flex;
  flex-direction: column;
  height: 100%;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  font-family: var(--ha-font-family-body, var(--paper-font-body1_-_font-family, sans-serif));
}
.toolbar {
  display: flex;
  align-items: center;
  gap: 12px;
  height: var(--header-height, 56px);
  padding: 0 12px;
  background: var(--app-header-background-color, var(--primary-color));
  color: var(--app-header-text-color, var(--text-primary-color, #fff));
  border-bottom: var(--app-header-border-bottom, none);
  box-sizing: border-box;
  flex: none;
}
.title { flex: 1; font-size: 20px; min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.toolbar select {
  font: inherit;
  font-size: 14px;
  padding: 4px 8px;
  border-radius: 6px;
  border: 1px solid rgba(255,255,255,0.5);
  background: rgba(255,255,255,0.15);
  color: inherit;
}
.toolbar option { color: var(--primary-text-color); background: var(--card-background-color); }
.body { display: flex; flex: 1; min-height: 0; }
:host([narrow]) .body { flex-direction: column; overflow: auto; }
.map-wrap { flex: 1; min-width: 0; min-height: 300px; padding: 12px; box-sizing: border-box; display: flex; }
.map {
  flex: 1;
  width: 100%;
  height: 100%;
  background: var(--card-background-color, #fff);
  border-radius: 12px;
  touch-action: none;
  user-select: none;
  outline: none;
}
.map:focus-visible { box-shadow: 0 0 0 2px var(--primary-color); }
.grid line { stroke: var(--divider-color, #e0e0e0); stroke-width: 1; vector-effect: non-scaling-stroke; }
.grid line.axis { stroke: var(--secondary-text-color, #9e9e9e); }
.tick { fill: var(--secondary-text-color, #757575); font-family: sans-serif; }
.room {
  fill: var(--secondary-background-color, #eceff1);
  stroke: var(--secondary-text-color, #9e9e9e);
  stroke-width: 1;
  vector-effect: non-scaling-stroke;
  cursor: pointer;
}
.room.manual { stroke-dasharray: 5 3; }
.room:hover { fill: color-mix(in srgb, var(--primary-color) 15%, var(--secondary-background-color, #eceff1)); }
.room.selected { stroke: var(--primary-color); stroke-width: 2; }
.room.ghost { fill-opacity: 0.35; stroke-dasharray: 5 3; }
.unlinked { fill: none; stroke: var(--disabled-text-color, #bdbdbd); stroke-dasharray: 4 3; vector-effect: non-scaling-stroke; }
.label {
  fill: var(--primary-text-color);
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
  font-family: sans-serif;
  paint-order: stroke;
  stroke: var(--card-background-color, #fff);
  stroke-linejoin: round;
}
.draft {
  fill: #ff9800;
  fill-opacity: 0.4;
  stroke: #e65100;
  stroke-width: 2;
  vector-effect: non-scaling-stroke;
  cursor: move;
}
path.draft { stroke-linejoin: round; }
.draft.invalid { fill: #f44336; stroke: #b71c1c; }
.vertex { fill: #fff; stroke: #e65100; stroke-width: 2; vector-effect: non-scaling-stroke; cursor: grab; }
.vertex.selected { fill: #e65100; stroke: #fff; }
.midpoint { fill: #e65100; fill-opacity: 0.55; stroke: #fff; stroke-width: 1; vector-effect: non-scaling-stroke; cursor: copy; }
.midpoint:hover { fill-opacity: 1; }
.handle { fill: #fff; stroke: #e65100; stroke-width: 2; vector-effect: non-scaling-stroke; }
.handle-n, .handle-s { cursor: ns-resize; }
.handle-e, .handle-w { cursor: ew-resize; }
.handle-ne, .handle-sw { cursor: nesw-resize; }
.handle-nw, .handle-se { cursor: nwse-resize; }
.draft-label {
  fill: #bf360c;
  font-weight: bold;
  text-anchor: middle;
  dominant-baseline: middle;
  pointer-events: none;
  font-family: sans-serif;
  paint-order: stroke;
  stroke: #fff;
  stroke-linejoin: round;
}
.side {
  width: 320px;
  flex: none;
  overflow-y: auto;
  padding: 12px 16px 24px 4px;
  box-sizing: border-box;
}
:host([narrow]) .side { width: auto; padding: 0 12px 24px; }
.editor {
  background: var(--card-background-color, #fff);
  border-radius: 12px;
  padding: 16px;
  margin-bottom: 8px;
}
h2 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
h3 { margin: 16px 0 6px; font-size: 13px; font-weight: 500; color: var(--secondary-text-color); text-transform: uppercase; letter-spacing: 0.04em; }
.hint { color: var(--secondary-text-color); font-size: 14px; line-height: 1.4; }
.hint.small { font-size: 12px; margin-top: 8px; }
.warning { color: var(--warning-color, #e65100); font-size: 13px; margin-top: 8px; }
.warning[hidden] { display: none; }
.error { color: var(--error-color, #db4437); padding: 16px 0; }
.status { margin-top: 8px; font-size: 13px; color: var(--secondary-text-color); }
.fields { display: grid; grid-template-columns: 1fr 1fr; gap: 10px 12px; margin-top: 12px; }
.fields label { min-width: 0; display: flex; flex-direction: column; gap: 4px; font-size: 12px; color: var(--secondary-text-color); }
.fields input, .fields select {
  font: inherit;
  font-size: 15px;
  padding: 6px 8px;
  border: 1px solid var(--divider-color, #ccc);
  border-radius: 6px;
  background: var(--primary-background-color);
  color: var(--primary-text-color);
  min-width: 0;
  width: 100%;
  box-sizing: border-box;
}
.segmented { display: inline-flex; margin-top: 12px; border: 1px solid var(--primary-color); border-radius: 16px; overflow: hidden; }
.seg {
  font: inherit;
  font-size: 13px;
  padding: 5px 14px;
  border: none;
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
}
.seg + .seg { border-left: 1px solid var(--primary-color); }
.seg.active { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.seg:disabled { opacity: 0.5; cursor: default; }
.vertices { grid-column: 1 / -1; display: flex; flex-direction: column; gap: 4px; max-height: 280px; overflow-y: auto; }
.vertex-row { display: grid; grid-template-columns: 22px 1fr 1fr 28px; gap: 6px; align-items: center; border-radius: 6px; }
.vertex-row.head { font-size: 12px; color: var(--secondary-text-color); }
.vertex-row.selected { background: color-mix(in srgb, #ff9800 18%, transparent); }
.vertex-index { font-size: 12px; color: var(--secondary-text-color); text-align: center; }
.fields .vertex-row input { font-size: 14px; padding: 4px 6px; }
.icon-btn {
  font: inherit;
  font-size: 16px;
  line-height: 1;
  width: 28px;
  height: 28px;
  padding: 0;
  border: none;
  border-radius: 14px;
  background: transparent;
  color: var(--secondary-text-color);
  cursor: pointer;
}
.icon-btn:hover:not(:disabled) { background: var(--secondary-background-color, #eee); color: var(--error-color, #db4437); }
.icon-btn:disabled { opacity: 0.3; cursor: default; }
.readout { font-size: 13px; color: var(--secondary-text-color); margin-top: 4px; }
.actions { display: flex; flex-wrap: wrap; gap: 8px; margin-top: 12px; }
.btn {
  font: inherit;
  font-size: 14px;
  padding: 7px 14px;
  border-radius: 18px;
  border: 1px solid var(--primary-color);
  background: transparent;
  color: var(--primary-color);
  cursor: pointer;
}
.btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); }
.btn.danger { border-color: var(--error-color, #db4437); color: var(--error-color, #db4437); }
.btn:disabled { opacity: 0.5; cursor: default; }
.list { display: flex; flex-wrap: wrap; gap: 6px; }
.item {
  font: inherit;
  font-size: 14px;
  padding: 5px 12px;
  border-radius: 16px;
  border: 1px solid var(--divider-color, #ccc);
  background: var(--card-background-color, #fff);
  color: var(--primary-text-color);
  cursor: pointer;
}
.item.active { border-color: var(--primary-color); color: var(--primary-color); font-weight: 500; }
`;
