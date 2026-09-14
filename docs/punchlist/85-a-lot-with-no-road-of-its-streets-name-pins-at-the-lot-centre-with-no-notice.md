# Punch list #85 — A lot with no road of its street's name pins at the lot's centre, with no notice

| | |
|:--|:--|
| **Status** | OPEN — found 2026-09-13; not built. No call has hit it yet. |
| **Severity** | 🔴 crew-visible — the pin looks like any frontage pin |
| **Area** | 🗺️ Geocoding · 🖥️ Kiosk |
| **Origin** | GIS data review, 2026-09-13, prompted by the UX agent's pushback on treating a lot's centre as a default pin |
| **Related** | #49 (arrival points) · #58 (lots with no named road) · #82 · [`../standards/operator_data.md`](../standards/operator_data.md) · [`../briefings/needs_attention_design.md`](../briefings/needs_attention_design.md) |

[← punch list index](../debug_and_qa_punchlist.md)

---

## What happens

1. **The geocoder falls back to the lot's centre.** Its exact-address step takes the arrival
   point, else the front point, else the lot's centre, and records `arrival_point = 'centroid'`
   for the last (`services/gis/src/gis_service/address_resolver.py`, the exact-parcel step). Its
   comment says the centre applies only "if a parcel somehow has no frontage point at all".
2. **Phase 1 shows it at once.** The phase 1 gate treats any lot with a zone as a solid place:
   `solid = bool(local_geocode_result.get("zone_id"))` in
   `backend/cfr_dispatch/pipeline/payload_builder.py`.
3. **The kiosk says nothing.** Its notices row appears only for `arrival_point === 'entrance'`
   (`frontend/src/components/kiosk/KioskView.jsx`). Its comment says `'front'` needs no notice;
   `'centroid'` is not mentioned.

## Measured, 2026-09-13

* **160 City lots have no front point.** Of those, **40 numbered addresses** are on streets no
  City road carries:
  * **Pinecone Burke Mtn, 28:** all on **one 24.0 ha lot**, sharing one centre, reached by Harper
    Rd, which becomes a forest service road behind locked gates (operator).
  * **Coronation Cres, 7.**
  * **Fremont St, 5.**
* **The centre is now inside the lot** (its pole of inaccessibility, applied the same day). Before,
  it could fall outside it.
* **No dispatch has resolved to `arrival_point = 'centroid'`**: 0 of 643, though the field is
  recent (611 records predate it).

## What a crew would see

For any of the 28 Pinecone Burke Mtn addresses: a pin in the middle of a 24 ha lot behind a locked
gate, with no notice, and the route drawn to it. It is the same pin for all 28 numbers.

## Not decided (operator)

* Whether the kiosk marks a centre pin as one, as it marks an operator's arrival point.
* Whether phase 1 withholds it as a fallback placement instead (the amber card until phase 2).
* Or both.

The needs-attention queue removes these 40 once arrival points are placed. It would not cover a
lot that loses its road in a later refresh.
