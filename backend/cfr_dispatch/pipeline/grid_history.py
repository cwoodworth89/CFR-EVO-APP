"""Map-grid retention: the grid E-Comm dispatched an address as, from calls the operator verified.

Operator ruling 2026-09-13: "We should build out the map grid retention so the system gets better over
time." The rules, 2026-09-14 (docs/standards/operator_data.md, ruling 21):

  * The evidence is `dispatches.verified_map_grid` only: a grid a person checked against the audio.
    Never the parsed grid, which is where the missing-digit grids came from.
  * One verified call is enough.
  * The call's own unit first, then the whole address. When the calls consulted disagree there is no
    answer, and phase 1 keeps the lot's zone.
  * No label on screen: the announced grid will match it.

Why phase 1 needs it. Phase 1 cannot use the grid it hears (the model completes it, punch-list #72), so
it shows the placed lot's zone. On 465 verified calls matched to a lot, the zone was E-Comm's grid on
447. The rest repeat per address: 1300 Pinetree Way was dispatched 86 on six of six calls while the lot
lies wholly in 87, and 2601 Lougheed Hwy differs by unit (Number 24 is 53, Number 29 is 55). Replayed in
time order with each call allowed only the calls verified before it, retention was right on 454 and made
none wrong that the lot's zone had right (measured 2026-09-13).

Read from public.dispatches at call time, never copied into a table: a grid verified in review applies
to the very next call, and nothing can go stale (CLAUDE.md 6.6).
"""
import logging
import re

from sqlalchemy import text

from gis_service.address_resolver import query_street
from gis_service.normalization import parse_house_and_street

# Words a dispatch or an operator puts in front of a unit: "Number 24", "Unit 1202", "Suite 2112", "#24".
_UNIT_WORDS = re.compile(r"\b(?:NUMBER|NUM|NO|UNIT|SUITE|STE|APT|APARTMENT)\b\.?|#", re.IGNORECASE)

_HISTORY_SQL = text("""
    SELECT btrim(verified_map_grid) AS grid, verified_address, target->>'subaddress' AS subaddress
    FROM public.dispatches
    WHERE btrim(coalesce(verified_map_grid, '')) ~ '^[0-9]+$'
      AND verified_address ILIKE :house_prefix
      AND (CAST(:dispatch_id AS text) IS NULL OR dispatch_id <> CAST(:dispatch_id AS text))
      AND (CAST(:before AS timestamptz) IS NULL OR timestamp < CAST(:before AS timestamptz))
""")


def unit_key(subaddress):
    """The unit a call names, comparable across wordings: 'Number 24', 'Unit 24' and '#24' are all '24'."""
    if not subaddress:
        return None
    s = _UNIT_WORDS.sub(" ", str(subaddress)).upper()
    s = " ".join(re.sub(r"[^A-Z0-9 ]", " ", s).split())
    return s or None


def address_key(address):
    """(house, street) as the geocoder matches them, so a verified address and a resolved one compare.

    The street goes through the resolver's own query_street, which applies the suffix vocabulary and
    drops a trailing unit number, so 'Pinetree Way' and 'PINETREE WAY 205' are the same street.
    """
    parsed = parse_house_and_street(address or "")
    if not parsed or not parsed.house:
        return None
    street = query_street(parsed.raw, parsed.street_type)
    return (parsed.house, street) if street else None


def choose_grid(history, unit):
    """Apply the operator's rules to (grid, unit_key) pairs from earlier verified calls.

    Returns (grid, scope, calls), scope 'unit' or 'address', or None when there is no history or it
    disagrees. None means phase 1 keeps the lot's zone.
    """
    if unit:
        same_unit = [g for g, u in history if u == unit]
        if same_unit:
            return (same_unit[0], "unit", len(same_unit)) if len(set(same_unit)) == 1 else None
    grids = [g for g, _ in history]
    if grids and len(set(grids)) == 1:
        return grids[0], "address", len(grids)
    return None


def verified_grid_for(engine, address, subaddress=None, *, dispatch_id=None, before=None):
    """The retained grid for a resolved address, or None.

    `dispatch_id` leaves the call itself out; `before` limits the history to calls before a time, for
    replays. A failed lookup returns None and logs, so phase 1 falls back to the lot's zone rather than
    losing its grid.
    """
    key = address_key(address)
    if key is None or engine is None:
        return None
    try:
        with engine.connect() as conn:
            rows = conn.execute(_HISTORY_SQL, {
                "house_prefix": f"{key[0]} %",
                "dispatch_id": dispatch_id,
                "before": before,
            }).fetchall()
    except Exception as e:
        logging.warning(f"Map-grid retention lookup failed for '{address}': {e}")
        return None
    history = [(str(int(r.grid)), unit_key(r.subaddress))
               for r in rows if address_key(r.verified_address) == key]
    return choose_grid(history, unit_key(subaddress))
