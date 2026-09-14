-- Remove the Lougheed Hwy & Mariner Way junction row labelled source = 'manual'
--
-- Operator ruling, 2026-09-13: remove it. Added by 2026-08-22_manual_lougheed_mariner_interchange.sql.
--
-- The label was wrong. No person placed it: its own note says the point is "the midpoint of the
-- shortest line between the two centrelines ... derived 2026-08-22 -- NOT operationally
-- confirmed". It is a script-generated coordinate presented as hand-entered, the kind #82 ruling 2
-- forbids for placed locations. Operator: "I hate that it's called manual as if I did it."
--
-- What it did, measured with the live resolver on the kiosk the same day: with the row, both word
-- orders resolved to that midpoint (grid 49, confidence 100); without it, both return unresolved,
-- so a call naming the interchange shows the amber location-unresolved card with the announced
-- grid. No dispatch in the 641-call corpus has named it; all 19 distinct junctions dispatched
-- resolve to derived rows.
--
-- A junction a person does pin belongs with the other hand-entered locations in the planned cfr
-- schema (docs/standards/operator_data.md), attributed to who placed it. public.intersections is
-- left holding derived rows only; derive_intersections.py's guard for manual rows is harmless with
-- none present.
--
-- The geocoder caches intersections when it starts (geocoder.py _load_intersection_keys), so a
-- running cfr-agent keeps the row until its next restart. Idempotent: safe to re-run.

DELETE FROM public.intersections
WHERE source = 'manual'
  AND street_a = 'LOUGHEED HWY'
  AND street_b = 'MARINER WAY';
