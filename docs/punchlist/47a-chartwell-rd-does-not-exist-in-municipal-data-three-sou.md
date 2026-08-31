# Punch list #47a — `Chartwell Rd` does not exist in municipal data — three sources give three street names

| | |
|:--|:--|
| **Status** | EXTERNAL |
| **Severity** | crew-visible |
| **Area** | 🧾 Import Completeness Audit, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3075 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 47. `Chartwell Rd` does not exist in municipal data — three sources give three street names
> **Status**: 📋 **Open — for the City GIS team, not a code defect.** Raised by the operator
> from HITL review of `DISP-2026-EC4501` (2026-08-19, rated OPERATIONAL): *"Flag this call.
> The dispatch announces 3305 Chartwell Rd, but that's not on the cadastral data. The map only
> shows it as 3305 Chartwell Green. Strange?"* All figures below **confirmed** by query.

**One address, three different street names, depending on who you ask:**

| Source | Street name |
|:--|:--|
| STT (`raw_transcript`) | `Chartwell **Grove**` |
| Operator, from the audio (`verified_address`) | `Chartwell **Rd**` |
| City of Coquitlam cadastre (`public.parcels`, `public.road_names`) | `Chartwell **Green**` |

#### What the municipal data actually holds

`public.road_names` contains exactly two Chartwell streets, and neither is a road:

```
Chartwell Green
Chartwell Lane (PRIV)
```

`public.parcels` agrees:

| Street | Parcels | House range |
|:--|--:|:--|
| Chartwell **Green** | 57 | 3255–3325 |
| Chartwell **Lane** (private) | 11 | 3221–3239 |

**There is no `Chartwell Rd`, `Chartwell Road`, or `Chartwell Grove` anywhere** in
`road_names` or `parcels`. House number **3305 is valid and unique** on Chartwell Green:

```
3305 Chartwell Green   49.317005655150034, -122.78752037030098
```

#### The system resolved it correctly

The pipeline produced `3305 Chartwell Green` at the parcel coordinates above — the right
place, per the only authoritative source available. Crews would have been routed correctly.

**So this call is scored `address WRONG` by the parser harness only because
`verified_address` disagrees with the cadastre, not because the system erred.** Worth knowing
when reading the address column: a small number of "failures" are ground-truth-versus-cadastre
conflicts of this kind.

#### The question for the City GIS team

Not answerable from anything this project holds:

1. Is **`Chartwell Rd` a legacy or alias name** for what the cadastre now calls Chartwell
   Green — a renamed street where the old name is still in circulation?
2. Does **E-Comm's CAD carry a different street name** for this block than the City's
   cadastral extract? If dispatch reads addresses from a CAD table that disagrees with the
   Open Data cadastre, that is a systematic divergence, not a one-off.
3. Is there any **`Grove`** designation in the area that would explain the STT reading, or is
   `Chartwell Grove` purely a mis-hearing of one of the other two?

Question 2 is the one that matters operationally. A single alias is a curiosity; a CAD/cadastre
divergence would mean an unknown number of announced addresses cannot be matched against
`public.parcels` at all — the same failure shape as #41 (`629 Cottonwood Ave` absent from
parcels).

#### Do not "fix" this in code

No string-match special case, and no alias row, until the source of the discrepancy is known
(CLAUDE.md §6.2 — a geocoding miss belongs in the data as a data fix, never as a special case
in application code). If GIS confirms `Chartwell Rd` is a legitimate legacy name, it belongs in
the street vocabulary as a recognition alias, the same mechanism as the call-type aliases
in #43.

---
