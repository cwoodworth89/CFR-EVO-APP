import * as turf from '@turf/turf';
import polylabel from '@mapbox/polylabel';
import { KNOWN_BUILDINGS } from '../MapConstants';

/**
 * Pure geometry and address helpers shared by the map surfaces.
 *
 * Extracted from MapBoard.jsx. None of these touch React state, and exporting non-component
 * values from a component file is what `react-refresh/only-export-components` flags.
 */

/**
 * Where a zone's map-grid number is drawn: the polygon's pole of inaccessibility, as
 * [lat, lng]. Null when the geometry is unusable.
 *
 * This was a bounding-box centre until 2026-09-08, named `getZoneCentroid` but computing
 * neither a centroid nor anything that stays inside the shape. Measured over all 134 zones
 * in public/data/zones.json: two labels (126, 134) landed outside their own polygon, 126 by
 * 2.0 km, and the median label sat 139 m from the shape's visual centre. The zones are
 * long and bent along the valley, which is exactly the case a bbox centre gets wrong.
 *
 * The pole of inaccessibility is the interior point furthest from any edge -- the
 * cartographic convention for polygon labels, and the only one of the candidates that is
 * guaranteed inside a concave shape.
 *
 * Longitude is scaled by cos(latitude) before the search and unscaled after, because
 * polylabel measures distance in whatever units it is handed: at 49.3 degrees N a degree of
 * longitude is 0.65 of a degree of latitude on the ground, so running it on raw degrees
 * finds the pole of a shape stretched 1.5x east-west.
 */
const zoneLabelPointCache = new WeakMap(); // zones are fetched once and never mutated

export const getZoneLabelPoint = (zone) => {
  if (!zone || !zone.geometry || !zone.geometry.coordinates || !zone.geometry.coordinates[0]) return null;
  if (zoneLabelPointCache.has(zone)) return zoneLabelPointCache.get(zone);

  const ring = zone.geometry.coordinates[0];
  if (ring.length < 3) return null;

  const meanLat = ring.reduce((sum, pt) => sum + pt[1], 0) / ring.length;
  const k = Math.cos((meanLat * Math.PI) / 180);
  if (!Number.isFinite(k) || k <= 0) return null;

  // 1e-5 scaled degrees is ~1.1 m on the ground here; the labels are drawn at zoom 13-15,
  // where 1 m is well under a screen pixel, so tightening it further buys nothing visible.
  const [x, y] = polylabel([ring.map(pt => [pt[0] * k, pt[1]])], 1e-5);
  if (!Number.isFinite(x) || !Number.isFinite(y)) return null;

  const point = [y, x / k];
  zoneLabelPointCache.set(zone, point);
  return point;
};

/**
 * The Alpha side of a parcel boundary: the segment nearest the approach point.
 *
 * @param rings       one ring of the parcel polygon, as [lng, lat] pairs
 * @param referencePt [lng, lat], normally the route's end point
 */
export function getAlphaSegment(rings, referencePt) {
  if (!rings || rings.length < 2) return null;

  const refPt = turf.point(referencePt);
  let minDistance = Infinity;
  let alphaSeg = null;

  for (let i = 0; i < rings.length - 1; i++) {
    const p1 = rings[i];
    const p2 = rings[i + 1];
    const segment = turf.lineString([p1, p2]);
    const dist = turf.pointToLineDistance(refPt, segment, { units: 'meters' });
    if (dist < minDistance) {
      minDistance = dist;
      alphaSeg = segment;
    }
  }
  return alphaSeg;
}

/**
 * Attaches known-building detail to a dispatch target when the address matches one.
 *
 * Where a building records a `frontEntrance`, that coordinate replaces the parcel centroid
 * — apparatus needs the door, not the middle of the lot. Returns the target unchanged when
 * nothing matches; it never invents a building.
 */
export function enrichAddressWithBuilding(targetObj) {
  if (!targetObj) return null;
  const rawAddr = (targetObj.address || '').toUpperCase().trim();

  const matchedBuilding = KNOWN_BUILDINGS.find(b => {
    if (rawAddr.includes(b.name.toUpperCase())) return true;
    if (rawAddr.includes(b.address.toUpperCase())) return true;
    return b.aliases.some(alias => rawAddr.includes(alias));
  });

  if (matchedBuilding) {
    return {
      ...targetObj,
      address: matchedBuilding.address,
      buildingName: matchedBuilding.name,
      lat: matchedBuilding.frontEntrance ? matchedBuilding.frontEntrance[0] : matchedBuilding.lat,
      lng: matchedBuilding.frontEntrance ? matchedBuilding.frontEntrance[1] : matchedBuilding.lng,
      frontEntrance: matchedBuilding.frontEntrance,
      note: matchedBuilding.note
    };
  }

  return targetObj;
}
