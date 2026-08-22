import * as turf from '@turf/turf';
import { KNOWN_BUILDINGS } from '../MapConstants';

/**
 * Pure geometry and address helpers shared by the map surfaces.
 *
 * Extracted from MapBoard.jsx. None of these touch React state, and exporting non-component
 * values from a component file is what `react-refresh/only-export-components` flags.
 */

/** Centre of a zone's bounding box, as [lat, lng]. Null when the geometry is unusable. */
export const getZoneCentroid = (zone) => {
  if (!zone || !zone.geometry || !zone.geometry.coordinates || !zone.geometry.coordinates[0]) return null;
  const coords = zone.geometry.coordinates[0];
  let minLat = 90, maxLat = -90, minLng = 180, maxLng = -180;
  coords.forEach(pt => {
    const lng = pt[0];
    const lat = pt[1];
    if (lat < minLat) minLat = lat;
    if (lat > maxLat) maxLat = lat;
    if (lng < minLng) minLng = lng;
    if (lng > maxLng) maxLng = lng;
  });
  return [(minLat + maxLat) / 2, (minLng + maxLng) / 2];
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
