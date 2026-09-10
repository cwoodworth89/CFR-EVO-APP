/**
 * Padding for a route or parcel fit, measured from the container, never written down.
 *
 * The console used to pad its fit with the sidebar widths as literals,
 * `paddingTopLeft: [340, 80], paddingBottomRight: [400, 80]`, on a map the sidebars do
 * not overlay at all -- they are flex siblings, so the map was already narrowed by them
 * and the route was fitted into the middle half of what was left. On a phone the same
 * literals exceed the container. Measured 2026-09-09 against the installed Leaflet 1.9.4:
 * `fitBounds` with padding wider than the map gives a zoom of `NaN` and throws nothing,
 * and a map at zoom NaN draws no tiles (docs/standards/dependency-behaviour.md).
 *
 * This is the dispatch map's own formula (RouteOverviewPanel, in use on the kiosk since
 * 2026-09-06), made the one place both maps read, plus the clamp that makes the NaN
 * impossible: the two paddings on an axis never take more than MAX_PADDED_SHARE of it.
 *
 * Nothing here is an operational value: it decides how much margin a route gets, not
 * where anything is (CLAUDE.md s7.1).
 */

/** Proportions of the container, as the dispatch map has drawn them since 2026-09-06. */
export const FIT_FRACTIONS = Object.freeze({ top: 0.12, bottom: 0.08, side: 0.08 });
/** Floors in CSS px for small containers, likewise from the dispatch map. */
export const FIT_MINIMUMS = Object.freeze({ top: 45, bottom: 35, side: 35 });
/** The snap (parcel plus picked hydrants) pads every side equally. */
export const SNAP_FRACTION = 0.1;
export const SNAP_MINIMUM = 40;
/**
 * The largest share of an axis the two paddings may take between them. Above this the fit
 * area is too small to read; at 1.0 or more Leaflet returns NaN. 0.6 leaves 40 % of the
 * axis for the route on the narrowest phone.
 */
export const MAX_PADDED_SHARE = 0.6;

/** Leaflet reports a 0 x 0 container before layout; these are the fallbacks the old code used. */
const FALLBACK_WIDTH = 800;
const FALLBACK_HEIGHT = 600;

function clampAxis(a, b, size) {
  const budget = size * MAX_PADDED_SHARE;
  const sum = a + b;
  if (sum <= budget) return [a, b];
  const k = budget / sum;
  return [Math.floor(a * k), Math.floor(b * k)];
}

function dimensions(width, height) {
  const w = Number(width) > 0 ? Number(width) : FALLBACK_WIDTH;
  const h = Number(height) > 0 ? Number(height) : FALLBACK_HEIGHT;
  return [w, h];
}

/**
 * A floating panel over the map adds its extent to the side it sits on: its width (and
 * left offset) when it floats at the left, as on the kiosk; its height (and top offset)
 * when it spans the top, as on a phone.
 */
function panelExtent(panel, panelSide) {
  if (!panel) return { left: 0, top: 0 };
  if (panelSide === 'top') return { left: 0, top: (panel.height || 0) + (panel.offsetTop || 0) };
  return { left: (panel.width || 0) + (panel.offsetLeft || 0), top: 0 };
}

/**
 * @param {object} args
 * @param {number} args.width       container width in CSS px
 * @param {number} args.height      container height in CSS px
 * @param {object} [args.panel]     { width, height, offsetLeft, offsetTop } of a panel floating over the map
 * @param {'left'|'top'} [args.panelSide]  which edge the panel occupies
 * @param {object} [args.overlays]  extra px covered on each side by sheets or drawers: { top, right, bottom, left }
 * @returns {{ paddingTopLeft: [number, number], paddingBottomRight: [number, number] }}
 */
export function fitPadding({ width, height, panel = null, panelSide = 'left', overlays = null }) {
  const [w, h] = dimensions(width, height);
  const extent = panelExtent(panel, panelSide);
  const o = overlays || {};
  let top = Math.max(FIT_MINIMUMS.top, Math.round(h * FIT_FRACTIONS.top)) + extent.top + (o.top || 0);
  let bottom = Math.max(FIT_MINIMUMS.bottom, Math.round(h * FIT_FRACTIONS.bottom)) + (o.bottom || 0);
  let left = Math.max(FIT_MINIMUMS.side, Math.round(w * FIT_FRACTIONS.side)) + extent.left + (o.left || 0);
  let right = Math.max(FIT_MINIMUMS.side, Math.round(w * FIT_FRACTIONS.side)) + (o.right || 0);
  [left, right] = clampAxis(left, right, w);
  [top, bottom] = clampAxis(top, bottom, h);
  return { paddingTopLeft: [left, top], paddingBottomRight: [right, bottom] };
}

/** Equal padding on every side, for the close-in snap to the parcel and its hydrants. */
export function snapPadding({ width, height, panel = null, panelSide = 'left', overlays = null }) {
  const [w, h] = dimensions(width, height);
  const pad = Math.max(SNAP_MINIMUM, Math.round(Math.min(w, h) * SNAP_FRACTION));
  const extent = panelExtent(panel, panelSide);
  const o = overlays || {};
  let [left, right] = clampAxis(pad + extent.left + (o.left || 0), pad + (o.right || 0), w);
  let [top, bottom] = clampAxis(pad + extent.top + (o.top || 0), pad + (o.bottom || 0), h);
  return { paddingTopLeft: [left, top], paddingBottomRight: [right, bottom] };
}

function measure(map, panelEl) {
  const size = map && typeof map.getSize === 'function' ? map.getSize() : { x: 0, y: 0 };
  const panel = panelEl
    ? { width: panelEl.offsetWidth || 0, height: panelEl.offsetHeight || 0, offsetLeft: panelEl.offsetLeft || 0, offsetTop: panelEl.offsetTop || 0 }
    : null;
  return { width: size.x, height: size.y, panel };
}

/**
 * Options for `map.fitBounds` on a route: measured padding plus the caller's zoom cap and
 * animation choice. `panelEl` is the details box floating over the map, if any.
 */
export function routeFitOptions(map, { panelEl = null, panelSide = 'left', overlays = null, maxZoom, animate = true } = {}) {
  const { width, height, panel } = measure(map, panelEl);
  const options = { ...fitPadding({ width, height, panel, panelSide, overlays }), animate };
  if (maxZoom != null) options.maxZoom = maxZoom;
  return options;
}

/** Options for `map.fitBounds` on the snap: equal measured padding, the caller's zoom cap. */
export function snapFitOptions(map, { panelEl = null, panelSide = 'left', overlays = null, maxZoom, animate = false } = {}) {
  const { width, height, panel } = measure(map, panelEl);
  const options = { ...snapPadding({ width, height, panel, panelSide, overlays }), animate };
  if (maxZoom != null) options.maxZoom = maxZoom;
  return options;
}
