-- "Unnamed Lane" joins the XStreets descriptor vocabulary
--
-- Operator ruling, 2026-09-12: "Add Unnamed Lane btw".
--
-- Evidence, not inference. DISP-2026-0093AD, 1260 Pinetree Way (Pinetree Community Centre):
--
--     "...near pinewood avenue and unnamed lane, use talk group 10..."
--
-- "Pinewood Avenue" matched a real road exactly; "Unnamed Ln" matched nothing and raised
-- XSTREET_UNRESOLVED, because the 2026-08-23 seeding encoded only the terms verified at the
-- time and this was not among them. Dispatch is stating that the adjacent feature has no
-- name -- which is a description of a road feature, exactly what `generic` means in that
-- migration: no single location exists, so a coordinate for it could only be invented
-- (CLAUDE.md 6.1).
--
-- Two spellings, matching the convention the other terms use: the spoken form and the form
-- street-suffix normalisation produces ("Lane" -> "Ln"). Both carry the same term_normalized.
--
-- observed = 1: one occurrence in the corpus as of 2026-09-12. Kept honest rather than
-- rounded up -- the field exists so a later reader can tell a common term from a one-off.
--
-- Idempotent: re-running inserts nothing new.

BEGIN;

INSERT INTO public.vocabulary (category, term, term_normalized, source, is_active, metadata)
VALUES
    ('xstreet_descriptor', 'Unnamed Lane', 'UNNAMED LANE', 'operator_2026-09-12', true,
     '{"kind":"generic","observed":1,"examples":["DISP-2026-0093AD"]}'),
    ('xstreet_descriptor', 'Unnamed Ln',   'UNNAMED LANE', 'operator_2026-09-12', true,
     '{"kind":"generic","observed":1,"examples":["DISP-2026-0093AD"]}')
ON CONFLICT DO NOTHING;

COMMIT;
