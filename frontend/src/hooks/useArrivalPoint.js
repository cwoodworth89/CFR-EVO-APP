import { useCallback, useEffect, useState } from 'react';
import { apiClient } from '../apiClient';

/**
 * The operator-set arrival point of one parcel (punch-list #49), as one piece of state that
 * both surfaces share.
 *
 * **The truck stops at the marker.** Where the computed frontage is wrong for a site -- a
 * gate off the lane, a trailer park, a highrise with the lobby round the back -- the operator
 * clicks where it should be and says why. The ruling is stored on the parcel, attributed, and
 * every later call to that address routes to it.
 *
 * Two callers since 2026-09-10:
 *
 *   * the console, where an address has been searched (`MapBoard`);
 *   * the dispatch display during a review replay, where the call is already on screen
 *     (operator: *"I can set the streetview but I can't easily set a new arrival point
 *     without backing out and typing in the address"*).
 *
 * It lived inline in `MapBoard` alone and was lifted here rather than copied, because a
 * second copy is how the one place without the fix ends up being the one that is wrong.
 *
 * **A save is a production change, not a scoped-to-this-replay one.** The parcel row is the
 * system of record for every future call to that address; replaying a call from August and
 * moving its arrival point moves where trucks stop tomorrow. The dispatch display says so
 * beside the controls.
 */
export function useArrivalPoint({ address, onSaved = null }) {
  const [parcel, setParcel] = useState(null);
  const [placing, setPlacing] = useState(false);
  const [draft, setDraft] = useState(null);

  const key = (address || '').trim().toUpperCase();

  // The parcel row behind the address: its entrance_* columns are the ruling, or their
  // absence is "nothing set, the computed frontage stands". A failed lookup leaves `parcel`
  // null and the card says the parcel is unknown -- it never reports "no arrival point set"
  // for an address it could not look up (CLAUDE.md s6.1).
  useEffect(() => {
    setParcel(null);
    setPlacing(false);
    setDraft(null);
    if (!key) return undefined;
    let cancelled = false;
    apiClient.parcels.lookup(key)
      .then((res) => { if (!cancelled && res?.found && res.parcel) setParcel(res.parcel); })
      .catch(() => { /* the card says the parcel is unknown */ });
    return () => { cancelled = true; };
  }, [key]);

  const start = useCallback(() => { setPlacing(true); setDraft(null); }, []);
  const cancel = useCallback(() => { setPlacing(false); setDraft(null); }, []);

  const onMapClick = useCallback((latlng) => {
    if (!placing || !latlng) return;
    setDraft({ lat: latlng.lat, lng: latlng.lng });
  }, [placing]);

  // lat/lng null clears the ruling and the computed frontage is used again. set_by is
  // required by the API: every override is attributable.
  //
  // `parcel_id` is the row's own key and is what decides where this lands. public.parcels is
  // one row per ADDRESS: 62 % of rows share a gis_id with a different address, and the one
  // Coquitlam Centre gis_id covers 235 of them. (An earlier version of this comment said
  // 1,671 -- that is the count of CFR's own base_site rows, which have no gis_id at all;
  // corrected 2026-09-11, punch-list #77.) Sending gis_id alone had the API answer
  // 200 OK and write the ruling to an arbitrary suite -- "2929 Barnet Hwy 1202" instead of
  // "2929 Barnet Hwy", so it was saved and never used (operator, 2026-09-10). The address
  // and gis_id still go along for an older API and for the log.
  const save = useCallback(async ({ lat, lng, note, setBy }) => {
    if (!parcel) throw new Error('No parcel behind this address');
    const res = await apiClient.parcels.saveEntrance({
      parcel_id: parcel.id, gis_id: parcel.gis_id, address: parcel.address, lat, lng, note, set_by: setBy,
    });
    const saved = res?.parcel || null;
    setParcel(saved);
    setPlacing(false);
    setDraft(null);
    if (onSaved) onSaved(saved);
    return saved;
  }, [parcel, onSaved]);

  return { parcel, placing, draft, start, cancel, save, onMapClick };
}
