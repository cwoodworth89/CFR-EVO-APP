# Punch list #56 — Bring XStreets onto the same resolution path as main addresses

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4188 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 56. Bring XStreets onto the same resolution path as main addresses
> **Status**: 🔵 **Improvement — specified, not built.** Operator direction 2026-08-30:
> *"I think it'll be important ALL streets follow the same path."* Reframed from a defect
> report; the underlying measurement that motivated it is kept below.

**The principle.** Every street reference in a dispatch — the address, and each cross street —
should be resolved against municipal data by one path, and report rather than rewrite when it
cannot be resolved.

#### Today the two are handled oppositely

| | Main address | Cross streets |
|:--|:--|:--|
| Resolution | geocoder against `public.parcels` / `public.roads` / `public.intersections` | `fuzz.ratio` against a name list |
| No exact match | returns suggestions, `is_ambiguous`, `requested_address`, `resolution_note` | **silently rewritten** to the best match |
| Operator sees the substitution | yes | no |

The asymmetry looks like the address is missing a feature. It is the reverse: **the address is
already on the safe path.**

#### Why the fuzzy threshold cannot be the answer

`fuzzy_correct_street` (`backend/cfr_dispatch/parser/location.py`) accepts the best match at
`threshold = 90 if len(base) <= 4 else 75`. Measured across the 1,079 real street names, best
`fuzz.ratio` against a **different real Coquitlam street**:

| | |
|:--|--:|
| Streets whose nearest *other real street* scores ≥ 75 | **938 (86.9%)** |
| Streets whose nearest *other real street* scores ≥ 90 | 40 (3.7%) |

```
aberdeen avenue  -> eden avenue      85
adler avenue     -> palmer avenue    88
admiral court    -> cardinal court   81
agate place      -> sage place       86
```

Those are pairs of real, distinct streets. At 75 the threshold admits substituting one genuine
Coquitlam street for another across most of the city. This is the practice already removed from
`intersection_resolver` — *"THERE IS NO SAFE SCORE THRESHOLD for street names in this city"* —
and that removal was at **80**.

#### What the cross streets in the corpus actually are

56 distinct values across all dispatches; **33 match municipal data, 23 do not.** The 23 are
three different problems, and only one of them is a data gap:

**a. Our own suffix doubling — 10 of 23. Not a data gap; a normalisation defect.**
```
Burlington Drive Dr    Christmas Way Way    Guildford Way Way    Honeysuckle Lane Lane
King Edward Street St  Pinetree Way Way     Primrose Lane Lane   Turnberry Lane Ln
Burlington Drive Drive Inlet Street Way
```
All real streets with the suffix applied twice. These match after the suffix handling is fixed,
and they need no vocabulary and no fuzzy matching at all.

**b. STT errors — 6.** `Loheed Hwy`, `Gabriela Dr`, `Sandstown Court`, `Town Center Blvd`,
`Gislaison Avenue`, `Nunes Creek Dr`. These are exactly what should surface as *unresolved and
flagged*, not be silently rewritten — see the round-comparison evidence that when two rounds
disagree on a street name, the operator's answer often matches **neither**
([`briefings/round_disagreement_signal.md`](../briefings/round_disagreement_signal.md)).

**c. Genuine non-street references — 7.** `Turning Lane`, `Turning Ln`, `Mall Access Turning
Ln`, `Access Road`, `Unnamed Lane`, `Glen Elementary School Access`, `Gleneagle Secondary School
Access`.

#### The non-street vocabulary already exists — in `public.vocabulary`, not in `roads`

Operator expectation was that the new import would carry these. Checked: **`public.roads`
(3,451 rows) and `public.road_names` (1,079) contain zero** matches for `turning`, `access` or
`driveway` — they are road centrelines, and these are not roads.

They are already captured, from the arrival-point workstream, as
**`public.vocabulary` category `xstreet_descriptor`, 9 terms**:

```
Access Rd | Access Road | Mall Access | Park Access | Private Driveway
School Access | Turn Ln | Turning Lane | Turning Ln
```

So the data needed for a single unified path **already exists**; it simply lives in two tables,
which is correct — a turning lane is not a road centreline and should not be forced into one.

#### The unified path

For every street reference, address and cross street alike:

1. **Exact match against municipal data** (`public.roads` / `road_names`, and `public.parcels`
   for the address). Resolved.
2. **Else exact match against `xstreet_descriptor`.** Resolved as a *descriptor*, not a road —
   it has no geometry and must never be used to narrow a location, only displayed.
3. **Else unresolved.** Keep the announced text verbatim, mark it, and let it raise the flag.
   Never substitute.

Fix the suffix doubling first (class a): it removes 10 of the 23 without any resolution logic,
and it is a straightforward normalisation bug rather than a judgement call.

#### Constraints

* **`_verify_cross_streets` (`address_resolver.py`) is the existing precedent** and already does
  step 1 correctly before using cross streets to narrow. The unified path should extend that,
  not duplicate it.
* A descriptor resolved at step 2 **must not reach the narrowing logic** — `Mall Access` has no
  geometry and anchoring on it would silently answer a different question.
* Removing `fuzzy_correct_street` is the intended end state, but **measure before deleting**: how
  often it fires, and whether it corrects more than it breaks, is still unknown. Cross streets
  have no `verified_*` ground truth, so the honest test is a sample of substitutions read against
  the audio.
* Cross streets are **proximity references, not routing destinations** (`geocoder.py:139-152`) —
  a wrong one misleads a crew confirming their block rather than sending them somewhere. That
  bounds the severity; it does not make silent substitution acceptable.


---
