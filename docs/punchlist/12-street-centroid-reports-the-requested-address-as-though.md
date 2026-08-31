# Punch list #12 — Street centroid reports the requested address as though exact

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | crew-visible |
| **Area** | 🧭 Geocoder Honesty Gaps |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L572 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 12. Street centroid reports the requested address as though exact
> **Status**: ⚠️ **Open — re-confirmed in the working tree 2026-08-21.** Both overwrites are
> still present: `geocoder.py:170–174` (step 5, street centroid) and `:177–181` (step 6,
> road centroid). Unchanged since the item was written.

`geocoder.py` step 5 overwrites the result address with the address that was asked for:

```python
result = self.address.resolve_street_centroid(parsed.street, parsed.street_type)
if result:
    result['address'] = f"{parsed.house} {parsed.raw}".strip().title() if parsed.house else result['address']
```

So a whole-street average is displayed as "3080 Gordon Ave" — indistinguishable on
screen from an exact parcel match apart from the confidence score. Step 6 (road centroid)
does the same.

The step 4b nearest-civic resolver added 2026-08-21 deliberately does **not** do this: it
reports the parcel actually used, keeps the dispatched string in `requested_address`, and
explains the substitution in `resolution_note`. Steps 5 and 6 should follow that pattern.

---

## 12 (closed). The centroid now says it is a centroid

> **Status**: ✅ **Closed 2026-08-30.** Verified in the working tree.

The defect was a street-centreline midpoint being returned as though it were the requested
civic address. `services/gis/src/gis_service/geocoder.py` now sets an explicit
`resolution_note` on that path:

> *"<requested> could not be placed on this street. Showing the centreline midpoint of
> <street>, not a specific address. Verify on arrival."*

The field is carried through rather than dropped at the first boundary — it appears in
`geocoder.py` (8 sites), `pipeline/payload_builder.py`, `pipeline/phase2.py` and
`pipeline/review_flags.py`. That is §6.1 satisfied: the approximation is still returned,
because a street midpoint is better than nothing, but it is labelled and the operator can see it.
