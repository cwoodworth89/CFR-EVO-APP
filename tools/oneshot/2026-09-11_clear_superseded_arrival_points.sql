-- Clear four arrival points that are superseded copies — punch list #77
--
-- Operator, 2026-09-11. Each of these four rows carries a ruling the operator has since
-- re-set on the property's base_site row, which is the row the resolver reads (ec34d27).
-- Nothing reads these, so clearing them changes no routing; it removes the duplicates that
-- made the original defect so hard to see.
--
--   181939  2929 Barnet Hwy 2112   superseded by 201357  "Main fire panel entrance"
--   163422  3030 Lincoln Ave       superseded by 201436  "Main Entrance for Engine"
--   163590  2865 Glen Dr           superseded by 201337  "Gated Entrance"
--   198562  602 Como Lake Ave 2606 superseded by 201792  "Main lobby entrance on the corner"
--
-- `is_base_site IS NOT TRUE` is a guard: a mistyped id cannot strip the point off a row the
-- system actually reads. Idempotent — a second run clears nothing and reports zero rows.

UPDATE public.parcels
   SET entrance_lat = NULL,
       entrance_lng = NULL,
       entrance_note = NULL,
       entrance_set_by = NULL,
       entrance_set_at = NULL
 WHERE id IN (181939, 163422, 163590, 198562)
   AND is_base_site IS NOT TRUE
 RETURNING id, address;

-- What should remain: every arrival point on a base_site row, none anywhere else.
SELECT id, address, is_base_site, entrance_note
  FROM public.parcels
 WHERE entrance_lat IS NOT NULL
 ORDER BY is_base_site DESC, address;
