# Punch list #50 — The parcel import seeds `entrance_lat/lng` with the centroid on every INSERT

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3633 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 50. The parcel import seeds `entrance_lat/lng` with the centroid on every INSERT
> **Status**: ✅ **Fixed 2026-08-31.** `entrance_lat` / `entrance_lng` are gone from the
> INSERT column list, the bound values and the params dict in **both** `import_parcels.py`
> and `import_parcels_PROPOSED.py`, so a new row now gets SQL NULL and the resolver falls
> through to the computed `front_lat`.
>
> **Why it is written this way.** An unset entrance is a *correct* answer (§6.1). The
> centroid is not a safe stand-in for one: on **177 parcels it falls outside the parcel
> entirely**, and on `2865 Glen Dr` it sits 135.6 m from Glen Drive. Seeding it also made
> the row *look* operator-verified, because that is what the field means — with
> `entrance_set_by` / `_at` / `_note` all NULL and nothing checking them.
>
> **Guarded by a test, not a comment.** `backend/tests/test_parcel_import_entrance.py` —
> 6 tests over both scripts, asserting entrance is absent from the columns, the binds, the
> params and the `ON CONFLICT` list, while `front_lat` is still written and the column
> still exists in the schema. Verified to actually fail when the column is put back.
> This mattered: the invariant was previously held by a comment attached to the *wrong
> function* — it sat above `backfill_parcel_frontage`, which genuinely never writes
> entrance, while the INSERT 200 lines below did.
>
> **Trialled against the real table.** The exact INSERT the script now issues, run inside
> a transaction and rolled back on the kiosk:
>
> ```
> entrance_is_null | attribution_is_null | computed_front | centroid | resolver_would_use
>        t         |          t          |     49.281     |  49.28   |      49.281
> rows_left_behind: 0
> ```
>
> The resolver takes the **front point**, not the centroid. Before the fix that last
> column would have read 49.28.
>
> Original report follows. Latent, not live — confirmed by reading both import scripts and
> measured against the kiosk database 2026-08-29.** Found while verifying the claims in
> `docs/arrival_point_handoff.md`; not previously recorded.

**The constraint.** `docs/arrival_point_handoff.md` and punch-list #49 both state it plainly:
`entrance_lat`/`entrance_lng` are the **operator-verified** access point, they outrank the
computed front point, and *"an import must never overwrite `entrance_*`."*
`backend/scripts/import_parcels.py:262` carries the comment saying so.

**The comment guards the wrong line.** It sits inside `backfill_parcel_frontage`, which indeed
never writes those columns. The **upsert** does:

```python
# backend/scripts/import_parcels.py:458-459
"entrance_lat": lat,     # lat/lng here are the parcel CENTROID
"entrance_lng": lng,
```

The `ON CONFLICT (address) DO UPDATE SET` list correctly omits `entrance_lat`/`entrance_lng`, so
**existing** rows are safe. The `INSERT` half is not. Every newly inserted parcel is written with
`entrance_lat = centroid`.

**Why that is not cosmetic.** Resolution precedence in
`services/gis/src/gis_service/address_resolver.py:332` is:

```python
dest_lat = best_row['entrance_lat'] or best_row['front_lat'] or best_row['lat']
```

A seeded `entrance_lat` therefore **silently outranks the computed front point** and hands the
crew the centroid — the exact value the addressed-street work replaced. It also presents as a
recorded human override while `entrance_set_by`, `entrance_set_at` and `entrance_note` are all
NULL, i.e. an unattributed override (§6.3). On the 177 parcels whose centroid falls outside the
parcel entirely, the arrival point would sit off the property.

**Two triggers, both currently on the roadmap:**

1. **A re-import with new addresses.** Punch-list #41's remaining action is exactly this —
   *"`Addresses.shp` is dated 2025-06-22, over a year old. Re-pull and re-import."* Every address
   new to the file inserts rather than conflicts, and arrives with a seeded entrance point.
2. **`--force-drop`.** `create_parcels_table(drop_existing=True)` recreates the table, so all
   65,401 rows take the INSERT path. That reproduces the pre-correction state wholesale, and
   would additionally destroy any real operator overrides recorded by the time #49 ships.

**Measured state, kiosk database, 2026-08-29** — the defect has not fired yet:

| | |
|:--|--:|
| `public.parcels` | 65,401 |
| `entrance_lat` NOT NULL | **0** |
| `entrance_lat = lat` (centroid copy) | **0** |
| `entrance_set_by` NOT NULL | 0 |
| `front_lat` NOT NULL | 65,401 |

So this is a **trap laid for the next import**, not a live wrong answer. It is recorded now
because the next two actions queued in this workstream are the two that spring it.

**`import_parcels_PROPOSED.py` has the identical defect** (`:795`, with the same correct
`ON CONFLICT` omission). It is not a reason to prefer one script over the other, but whichever is
adopted needs the fix, and it should not be adopted while it carries this.

**Not fixed here** — read-only characterisation per the standing QA intake agreement. The likely
shape is to drop `entrance_lat`/`entrance_lng` from the INSERT column list entirely so new rows
get SQL NULL, matching what `front_lat` already relies on falling through to. That should be
paired with a test asserting an import leaves `entrance_*` untouched, since the existing comment
demonstrates that a comment alone does not hold this invariant.
