import L from 'leaflet';
import markerShadow from 'leaflet/dist/images/marker-shadow.png';
import markerTargetGold from '../../assets/marker-target-gold.svg';
import markerCandidateBlue from '../../assets/marker-candidate-blue.svg';

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

// ---------------------------------------------------------------------------
// Pin markers for the dispatch target and its alternate candidates.
//
// These were three duplicated `new L.Icon({...})` literals in BlockParcelPanel,
// PropertySatellitePanel and RouteOverviewPanel, each loading its image from
// raw.githubusercontent.com and its shadow from cdnjs.cloudflare.com -- six
// external requests on the kiosk map. With the link down the fetches failed and
// the pin marking the incident simply did not render: the map drew, the route
// drew, and nothing reported the omission, because a failed <img> raises no
// JavaScript error. CLAUDE.md s1 (offline survival) and s6.1 (an unknown must be
// visible, never silently absent). Registered in docs/external_calls.md s3.1.
//
// Vendored as local SVG rather than copies of the upstream PNGs: no network at
// build or run time, no third-party asset licence to carry (s1's Carto caution
// is the same problem), and vector holds up on a 10-foot apparatus-bay display
// where a 25x41 raster does not.
//
// Imported rather than served from public/ so a missing file breaks `npm run
// build` instead of 404-ing silently on the kiosk -- the same failure mode this
// change exists to remove.
//
// Colour roles are CLAUDE.md s5: active target gold, alternate candidates sky
// blue. The exact hexes are a display choice, not a derived value.
//
// Geometry is unchanged from the icons these replace, so placement is identical:
// 25x41 with the anchor at the point (12, 41), not the centre.
// ---------------------------------------------------------------------------

const PIN_GEOMETRY = {
  shadowUrl: markerShadow,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
};

/** Gold pin: the active dispatch target. */
export const targetPinIcon = new L.Icon({ ...PIN_GEOMETRY, iconUrl: markerTargetGold });

/** Sky-blue pin: an alternate address candidate (CLAUDE.md s5 ambiguity handling). */
export const altCandidatePinIcon = new L.Icon({ ...PIN_GEOMETRY, iconUrl: markerCandidateBlue });
