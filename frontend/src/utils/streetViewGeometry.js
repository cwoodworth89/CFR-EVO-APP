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
  // The camera's own position. It used to be read from `front_lat` -- the computed frontage,
  // which the save also overwrote, so reframing a view moved the routing destination (punch
  // list #78). Operator ruling 2026-09-11: the computed point, the arrival point and the
  // Street View point are separate and do not change each other. There is deliberately no
  // fallback to `front_lat`: after a frontage repair that fallback would aim the camera at
  // the repaired point instead of where the operator left it.
  const lat = parcel.streetview_lat;
  const lng = parcel.streetview_lng;
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

/** Whether two points are the same coordinate, where a bearing has no direction. */
const samePoint = (aLat, aLng, bLat, bLng) => Number(aLat) === Number(bLat) && Number(aLng) === Number(bLng);

/**
 * The centre of a lot, from the parcel polygon the dispatch record carries (`target.rings`,
 * GeoJSON order: [[lng, lat], ...], outer ring first). The area-weighted centroid of the outer
 * ring, planar in degrees -- at lot scale the curvature error is far below a metre. Falls back
 * to the vertex mean for a degenerate ring. Null when there is no usable ring.
 */
export const lotCentre = (rings) => {
  const ring = Array.isArray(rings) ? rings[0] : null;
  if (!Array.isArray(ring)) return null;
  const pts = ring
    .filter((p) => Array.isArray(p) && p.length >= 2 && Number.isFinite(Number(p[0])) && Number.isFinite(Number(p[1])))
    .map((p) => [Number(p[0]), Number(p[1])]);
  if (pts.length >= 2 && samePoint(pts[0][1], pts[0][0], pts.at(-1)[1], pts.at(-1)[0])) pts.pop();
  if (pts.length < 3) return null;
  // Relative to the first vertex: the cross products of raw coordinates (about -122.8 x 49.3)
  // cancel catastrophically at lot scale, where vertices differ in the 5th decimal place.
  const [ox, oy] = pts[0];
  let a2 = 0, cx = 0, cy = 0;
  for (let i = 0; i < pts.length; i++) {
    const x0 = pts[i][0] - ox, y0 = pts[i][1] - oy;
    const x1 = pts[(i + 1) % pts.length][0] - ox, y1 = pts[(i + 1) % pts.length][1] - oy;
    const cross = x0 * y1 - x1 * y0;
    a2 += cross;
    cx += (x0 + x1) * cross;
    cy += (y0 + y1) * cross;
  }
  if (Math.abs(a2) < 1e-18) {
    const n = pts.length;
    return { lat: pts.reduce((t, p) => t + p[1], 0) / n, lng: pts.reduce((t, p) => t + p[0], 0) / n };
  }
  return { lat: oy + cy / (3 * a2), lng: ox + cx / (3 * a2) };
};

/**
 * What the camera should face. The lot centre when the call carries a parcel polygon, else
 * the call's own point (a junction, a block, a street section). Null without either.
 * Punch list #93, operator 2026-09-16: build the proposal as made -- lot centre, else the
 * target point.
 */
export const aimPointForCall = (call) => {
  if (!call) return null;
  const centre = lotCentre(call.target?.rings ?? call.rings);
  if (centre && isCoord(centre.lat, centre.lng)) return { ...centre, kind: 'lot' };
  const lat = call.target?.lat ?? call.lat;
  const lng = call.target?.lng ?? call.lng;
  return isCoord(lat, lng) ? { lat: Number(lat), lng: Number(lng), kind: 'point' } : null;
};

/** Heading from a camera position to an aim point, or null when there is no direction:
 *  no aim point, or the two are the same coordinate. Never 0 by default (CLAUDE.md 6.1). */
export const headingToAim = (camLat, camLng, aim) => {
  if (!aim || !isCoord(camLat, camLng) || samePoint(camLat, camLng, aim.lat, aim.lng)) return null;
  return bearingDegrees(Number(camLat), Number(camLng), aim.lat, aim.lng);
};

/**
 * The view to show when nothing is saved, before Google has said where the nearest panorama
 * stands: the camera at the call's point, facing the aim point. Null when the call carries no
 * usable coordinates (Tier 1, CLAUDE.md 5).
 *
 * `heading` is null when there is no direction to face -- a call with no parcel polygon,
 * whose aim point IS its camera point. It used to fall to 0 here, and it always did:
 * toActiveCall sets `lat` to `target.lat`, so the camera and the aim were one point and every
 * unsaved tile faced due north (punch list #93, measured 2026-09-16: 46% of 41 parcel calls
 * faced more than 90 degrees away from the lot). A null heading is shown as "not aimed",
 * never as north.
 *
 * `aim` rides along so the panorama position from Google can be turned into the heading
 * (viewFromMetadata, and the interactive view's own search in useStreetViewPanorama).
 */
export const defaultViewForCall = (call) => {
  if (!call) return null;
  const lat = call.lat ?? call.front_lat ?? call.target?.lat;
  const lng = call.lng ?? call.front_lng ?? call.target?.lng;
  if (!isCoord(lat, lng)) return null;
  const camLat = Number(lat);
  const camLng = Number(lng);
  const aim = aimPointForCall(call);
  return {
    lat: camLat,
    lng: camLng,
    heading: headingToAim(camLat, camLng, aim),
    pitch: DEFAULT_PITCH,
    fov: DEFAULT_FOV,
    panoId: '',
    aim,
  };
};

// ---------------------------------------------------------------------------------------
// Street View Static API metadata (punch list #93, operator's permission 2026-09-16).
//
// One request per unsaved call, to find where the nearest panorama actually stands so the
// heading can be computed from there. Google, "Street View Image Metadata" (read 2026-09-16):
// "Street View Static API metadata requests are available at no charge. No quota is consumed
// when you request metadata." Registered in docs/external_calls.md 4.1.

/** The metadata request for a view's point: the same search the image request makes. */
export const streetViewMetadataUrl = (view, apiKey) => {
  if (!view || !apiKey || !isCoord(view.lat, view.lng)) return '';
  return `https://maps.googleapis.com/maps/api/streetview/metadata?location=${view.lat},${view.lng}`
    + `&radius=${STATIC_SEARCH_RADIUS_M}&source=outdoor&key=${apiKey}`;
};

/**
 * The view from a metadata answer: the camera at the panorama Google found, pinned to it by
 * id so the image is from the panorama the heading was computed for, facing the aim point.
 * Null unless the answer is OK with a usable position and id.
 */
export const viewFromMetadata = (defaultView, meta) => {
  if (!defaultView || meta?.status !== 'OK') return null;
  const lat = meta.location?.lat;
  const lng = meta.location?.lng;
  if (!isCoord(lat, lng) || !meta.pano_id) return null;
  return {
    ...defaultView,
    lat: Number(lat),
    lng: Number(lng),
    panoId: String(meta.pano_id),
    heading: headingToAim(lat, lng, defaultView.aim),
  };
};

/**
 * Which picture the tile shows, as one decision (punch list #93, the fallback chain):
 *
 *   saved view                         -> 'saved'       the operator's view, untouched
 *   no usable coordinates              -> 'standby'     Tier 1
 *   metadata not answered yet          -> 'resolving'   no image requested yet
 *   metadata OK                        -> 'metadata'    pano pinned, heading from the pano
 *   metadata ZERO_RESULTS              -> 'no-imagery'  "No Street View available"
 *   any other answer, or no answer     -> 'fallback'    the location request, heading from
 *     (REQUEST_DENIED, OVER_QUERY_LIMIT,                 the call's point to the lot centre
 *      UNKNOWN_ERROR, a failed fetch, no key)
 *   a picture with no direction        -> 'no-heading'  the tile says it is not aimed
 *
 * `view` is the compact tile's picture (null when the tile shows a status instead).
 * `expandView` is what the interactive view opens on, and it is set whenever the call has
 * coordinates -- including resolving, no imagery and not aimed. Operator, 2026-09-16: "if no
 * heading comes back we still need to allow the user to expand the window into interactive
 * mode, at the nearest point to look and set a future point." The interactive view searches
 * for the nearest panorama itself (useStreetViewPanorama), and a save from there makes the
 * next call for the address take the 'saved' branch.
 *
 * Offline is decided before this: the panel shows "Street View needs the internet".
 */
export const resolveStreetView = ({ savedView, defaultView, meta }) => {
  if (savedView) return { kind: 'saved', view: savedView, expandView: savedView };
  if (!defaultView) return { kind: 'standby', view: null, expandView: null };
  if (!meta) return { kind: 'resolving', view: null, expandView: defaultView };
  if (meta.status === 'ZERO_RESULTS') return { kind: 'no-imagery', view: null, expandView: defaultView, reason: meta.status };
  const fromPano = viewFromMetadata(defaultView, meta);
  const view = fromPano || defaultView;
  const kind = fromPano ? 'metadata' : 'fallback';
  if (!Number.isFinite(view.heading)) {
    return { kind: 'no-heading', view: null, expandView: defaultView, reason: meta.status, from: kind };
  }
  return { kind, view, expandView: view, reason: meta.status };
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
  const headingMatches = !Number.isFinite(view.heading) || Math.abs(live.heading - view.heading) < 0.5;
  return headingMatches
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
  // No heading, no image: without one the API faces a direction of its own choosing, which
  // would read as an aimed picture. The panel says "not aimed" instead (#93).
  if (!view || !apiKey || !Number.isFinite(view.heading)) return '';
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
  // No heading, no heading parameter: Math.round(null) is 0, the silent north of #93.
  const heading = Number.isFinite(view.heading) ? `&heading=${Math.round(view.heading)}` : '';
  return `https://www.google.com/maps/embed/v1/streetview?key=${apiKey}&location=${view.lat},${view.lng}`
    + `${heading}&pitch=${Math.round(view.pitch)}`;
};
