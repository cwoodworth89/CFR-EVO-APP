/**
 * Street View camera arithmetic, pure, so it can be tested under `node --test` and so the
 * panel, the hook and the save path all speak one unit.
 *
 * THE VIEW is one object: { lat, lng, heading, pitch, fov, panoId }.
 *   * lat/lng   -- where the camera stands (the panorama's position, not the parcel)
 *   * heading   -- degrees clockwise from north, whole degrees when stored
 *   * pitch     -- degrees above the horizon, whole degrees when stored
 *   * fov       -- field of view in DEGREES at full precision; the SDK's zoom is derived
 *   * panoId    -- the panorama the operator was looking at; '' when unknown
 *
 * Google's relation between the panorama's zoom and its field of view is fov = 180 / 2^zoom
 * (Maps JavaScript API, StreetViewPanorama; zoom 1 is 90 degrees). The database stores
 * degrees (public.parcels.streetview_fov, double precision); zoom exists only on the way to
 * and from the SDK, so the two cannot disagree. Storing the zoom level in the degrees column
 * is what #35a found on 2026-09-06, and rounding the zoom is what lost framings on 09-08.
 *
 * Nothing here clamps a stored view. The Static API's 10..120 degree limit bounds the tile
 * URL and nothing else (docs/standards/dependency-behaviour.md records why the SDK's own
 * minimum zoom cannot be nested inside it).
 */

export const DEFAULT_PITCH = 5;   // degrees; the panel's long-standing default, a mild upward look
export const DEFAULT_FOV = 90;    // degrees; the SDK's zoom 1

// Street View Static API `fov` parameter, documented range.
export const STATIC_FOV_MIN = 10;
export const STATIC_FOV_MAX = 120;

const finite = (v, fallback) => {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
};

export const fovToZoom = (fov) => {
  const f = finite(fov, DEFAULT_FOV);
  return Math.log2(180 / (f > 0 ? f : DEFAULT_FOV));
};

export const zoomToFov = (zoom) => 180 / Math.pow(2, finite(zoom, 1));

/** Degrees for the Static API URL: integer, within the documented range. The stored angle
 *  keeps its precision; only the thumbnail request is bounded. */
export const clampStaticFov = (fov) =>
  Math.min(Math.max(Math.round(finite(fov, DEFAULT_FOV)), STATIC_FOV_MIN), STATIC_FOV_MAX);

/** Initial bearing from one point to another, whole degrees 0..359. Used for the default
 *  heading: from the arrival point on the street toward the parcel, so an unsaved view
 *  looks at the property rather than down the road. */
export const bearingDegrees = (fromLat, fromLng, toLat, toLng) => {
  const dLng = (toLng - fromLng) * (Math.PI / 180);
  const a = fromLat * (Math.PI / 180);
  const b = toLat * (Math.PI / 180);
  const y = Math.sin(dLng) * Math.cos(b);
  const x = Math.cos(a) * Math.sin(b) - Math.sin(a) * Math.cos(b) * Math.cos(dLng);
  return Math.round(((Math.atan2(y, x) * 180) / Math.PI + 360) % 360);
};

const isCoord = (lat, lng) => {
  const a = Number(lat);
  const b = Number(lng);
  return Number.isFinite(a) && Number.isFinite(b) && !(a === 0 && b === 0);
};

/**
 * The saved view on a parcel row from /api/parcels/lookup, or null when the operator has
 * never saved one. Since the 2026-09-06 migration an unsaved parcel holds NULL in
 * streetview_heading; before it every parcel read as a saved 0-degree view.
 */
export const savedViewFromParcel = (parcel) => {
  if (!parcel) return null;
  const heading = parcel.streetview_heading ?? parcel.heading;
  if (heading == null || !Number.isFinite(Number(heading))) return null;
  const lat = parcel.front_lat ?? parcel.lat;
  const lng = parcel.front_lng ?? parcel.lng;
  if (!isCoord(lat, lng)) return null;
  return {
    lat: Number(lat),
    lng: Number(lng),
    heading: Number(heading),
    pitch: finite(parcel.streetview_pitch ?? parcel.pitch, DEFAULT_PITCH),
    fov: finite(parcel.streetview_fov ?? parcel.fov, DEFAULT_FOV),
    panoId: parcel.streetview_pano_id ?? parcel.pano_id ?? '',
  };
};

/**
 * The view to show when nothing is saved: the camera at the arrival point, looking at the
 * parcel. Null when the call carries no usable coordinates (Tier 1, CLAUDE.md 5).
 */
export const defaultViewForCall = (call) => {
  if (!call) return null;
  const lat = call.lat ?? call.front_lat ?? call.target?.lat;
  const lng = call.lng ?? call.front_lng ?? call.target?.lng;
  if (!isCoord(lat, lng)) return null;
  const camLat = Number(lat);
  const camLng = Number(lng);
  const tLat = Number(call.target?.lat ?? lat);
  const tLng = Number(call.target?.lng ?? lng);
  const heading = (isCoord(tLat, tLng) && (tLat !== camLat || tLng !== camLng))
    ? bearingDegrees(camLat, camLng, tLat, tLng)
    : 0;
  return { lat: camLat, lng: camLng, heading, pitch: DEFAULT_PITCH, fov: DEFAULT_FOV, panoId: '' };
};

/**
 * Whether a panorama is already showing a view, within the precision the view is stored
 * at: heading and pitch are whole degrees (0.5 tolerance), fov is full precision but the
 * SDK reports zoom in floating point (0.01 degrees is far below anything visible). Used so
 * a save, which turns into the saved view arriving back from the database, does not re-aim
 * a camera that is already exactly there (the "snap on save" of 2026-09-08).
 */
export const viewsMatch = (live, view) => {
  if (!live || !view) return false;
  if (view.panoId && live.panoId && live.panoId !== view.panoId) return false;
  return Math.abs(live.heading - view.heading) < 0.5
    && Math.abs(live.pitch - view.pitch) < 0.5
    && Math.abs(live.fov - view.fov) < 0.01;
};

/** The Static API request for a view: one JPEG at the saved framing.
 *  maps.googleapis.com/maps/api/streetview is registered in docs/external_calls.md 4.1;
 *  return_error_code turns a miss into an HTTP error the <img> reports rather than a grey
 *  placeholder that looks like imagery. */
// How far from the point the Static API may look for imagery when no panorama id is
// saved. Its default is 50 m; the interactive SDK searches 50 m then 100 m
// (hooks/useStreetViewPanorama.js), and on 2026-09-08 the tile 404'd on 2865 Glen Dr
// while the panorama found imagery -- the two searched different distances. Same reach,
// same answer. `source=outdoor` matches the SDK's search too.
export const STATIC_SEARCH_RADIUS_M = 100;

export const staticStreetViewUrl = (view, apiKey, size = '640x400') => {
  if (!view || !apiKey) return '';
  const where = view.panoId
    ? `pano=${encodeURIComponent(view.panoId)}`
    : `location=${view.lat},${view.lng}&radius=${STATIC_SEARCH_RADIUS_M}&source=outdoor`;
  return `https://maps.googleapis.com/maps/api/streetview?size=${size}&${where}`
    + `&heading=${Math.round(view.heading)}&pitch=${Math.round(view.pitch)}&fov=${clampStaticFov(view.fov)}`
    + `&return_error_code=true&key=${apiKey}`;
};

/** The Maps Embed API request for a view: the fallback when the JS SDK is rejected. */
export const embedStreetViewUrl = (view, apiKey) => {
  if (!view) return '';
  if (!apiKey) {
    return `https://www.google.com/maps/embed?pb=!1m14!1m12!1m3!1d1000!2d${view.lng}!3d${view.lat}!2m3!1f0!2f0!3f0!3m2!1i1024!2i768!4f13.1!5e1!3m2!1sen!2sca`;
  }
  return `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${view.lat},${view.lng}`
    + `&heading=${Math.round(view.heading)}&pitch=${Math.round(view.pitch)}`;
};
