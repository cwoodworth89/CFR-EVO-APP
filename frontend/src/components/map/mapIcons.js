import L from 'leaflet';

/**
 * Leaflet div icons shared by the map surfaces.
 *
 * Extracted from MapBoard.jsx: these are module-level constants, not components, and
 * exporting them from a component file is what the `react-refresh/only-export-components`
 * lint rule flags. They are also pure — no state, no props — so they belong outside the
 * 1,100-line component rather than inside it.
 */

/** 🚧 Barricade marker for road closures. */
export const closureIcon = L.divIcon({
  className: 'custom-closure-icon',
  html: `<div style="
    background-color: #f59e0b;
    border: 2px solid #000000;
    border-radius: 6px;
    width: 28px;
    height: 28px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 5px rgba(0,0,0,0.4);
    font-size: 15px;
    box-sizing: border-box;
  ">🚧</div>`,
  iconSize: [28, 28],
  iconAnchor: [14, 14],
  popupAnchor: [0, -14]
});

/** 🎯 Marker for the active dispatch target. */
export const targetIcon = L.divIcon({
  className: 'custom-target-icon',
  html: `<div style="
    background-color: #4f46e5;
    border: 2px solid #ffffff;
    border-radius: 50%;
    width: 24px;
    height: 24px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    font-size: 13px;
    box-sizing: border-box;
    color: white;
  ">🎯</div>`,
  iconSize: [24, 24],
  iconAnchor: [12, 12],
  popupAnchor: [0, -12]
});

/** Unobtrusive numeric label for an emergency response zone. */
export const createSoftZoneNumberIcon = (zoneId) => L.divIcon({
  className: 'soft-zone-number-marker',
  html: `<div style="display:flex;align-items:center;justify-content:center;color:#0f172a;font-weight:800;font-size:12px;font-family:ui-monospace, SFMono-Regular, monospace;pointer-events:none;user-select:none;opacity:0.85;white-space:nowrap;line-height:1;">${zoneId}</div>`,
  iconSize: [32, 16],
  iconAnchor: [16, 8]
});
