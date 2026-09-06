-- 'CT' as an alias of the City's 'CRT' (category 'street_suffix').
--
-- The operator types "Sugarpine Ct" in the verified column; the City's parcel and road
-- layers spell the suffix "CRT" (public.parcels.streettype, public.roads.roadtype), and so
-- do the canonical forms already written into public.road_names and every stored address.
-- Without this row normalize_street_name('SUGARPINE CT') stayed 'SUGARPINE CT', so the
-- typed correction did not fold onto the City's street in the hotword ranking or the
-- misheard-street tally (punch-list #71, 2026-09-05). Operator ruling the same day: the
-- system accepts either spelling; the notes are not rewritten.
--
-- LANE is deliberately NOT touched: its canonical 'LN' is baked into road_names and
-- intersection keys (see 2026-08-22_street_suffix_vocabulary.sql, "SUNSET SQ").
INSERT INTO public.vocabulary (category, term, term_normalized, source, is_active, sort_order)
SELECT 'street_suffix', 'CT', 'CRT', 'alias', TRUE, 90
WHERE NOT EXISTS (
  SELECT 1 FROM public.vocabulary WHERE category = 'street_suffix' AND upper(term) = 'CT'
);
