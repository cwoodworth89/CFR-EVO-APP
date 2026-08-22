-- Street suffix vocabulary -> public.vocabulary (category 'street_suffix')
--
-- WHY THIS EXISTS
-- The variant -> canonical street suffix mapping was hardcoded in TWO places that
-- disagreed with each other:
--   * services/gis/src/gis_service/normalization.py  SUFFIX_MAPPINGS (14 canonical)
--   * backend/scripts/extract_all_intersections_from_gis.py SUFFIX_MAPPINGS (larger)
-- The extractor wrote 'SUNSET SQ' into public.intersections while the geocoder
-- normalized an incoming dispatch to 'SUNSET SQUARE'. Those never match, so an
-- intersection on any such street was silently unresolvable.
--
-- normalization.py was also missing 10 suffix types that actually occur in
-- public.roads.roadtype, covering 26 real streets: SQUARE(8), GATE(5), TERRACE(4),
-- CLOSE(2), CIRCLE(2), WALK(1), SLIP LANE(1), GREEN(1), WOOD(1), TRAIL(1).
--
-- PROVENANCE OF THE CANONICAL FORMS
--  * The 14 pre-existing canonical abbreviations (AVE, ST, RD, ...) are kept exactly
--    as they were. They are already written into public.road_names and every stored
--    address, so changing them would invalidate existing data. They also match the
--    suffix list in CLAUDE.md section 5.
--  * The 10 additions take their canonical form from public.roads.roadtype -- the City
--    of Coquitlam Transportation centreline layer -- rather than an abbreviation
--    invented here. Where an abbreviation is in common use it is added as an ALIAS
--    row pointing at the same canonical value, so spoken or abbreviated input still
--    resolves.
--
-- NOTE: public.vocabulary.source is varchar(20), so the values below are short tags.
-- 'normalization.py' = the canonical form already in use before this migration.
-- 'public.roads'     = canonical form taken from the municipal centreline layer.
-- 'alias'            = a convenience variant pointing at one of the above.
--
-- term            = the variant as it may be spoken, transcribed or written
-- term_normalized = the canonical form stored in the database
-- Rows are editable by hand: this is vocabulary, and operators correct vocabulary.

INSERT INTO public.vocabulary (category, term, term_normalized, source, is_active, sort_order)
VALUES
  -- Pre-existing canonical set (unchanged)
  ('street_suffix','AVENUE','AVE','normalization.py',TRUE,10),
  ('street_suffix','AVE','AVE','normalization.py',TRUE,10),
  ('street_suffix','STREET','ST','normalization.py',TRUE,20),
  ('street_suffix','ST','ST','normalization.py',TRUE,20),
  ('street_suffix','ROAD','RD','normalization.py',TRUE,30),
  ('street_suffix','RD','RD','normalization.py',TRUE,30),
  ('street_suffix','DRIVE','DR','normalization.py',TRUE,40),
  ('street_suffix','DR','DR','normalization.py',TRUE,40),
  ('street_suffix','BOULEVARD','BLVD','normalization.py',TRUE,50),
  ('street_suffix','BLVD','BLVD','normalization.py',TRUE,50),
  ('street_suffix','HIGHWAY','HWY','normalization.py',TRUE,60),
  ('street_suffix','HWY','HWY','normalization.py',TRUE,60),
  ('street_suffix','WAY','WAY','normalization.py',TRUE,70),
  ('street_suffix','CRESCENT','CRES','normalization.py',TRUE,80),
  ('street_suffix','CRES','CRES','normalization.py',TRUE,80),
  ('street_suffix','COURT','CRT','normalization.py',TRUE,90),
  ('street_suffix','CRT','CRT','normalization.py',TRUE,90),
  ('street_suffix','PLACE','PL','normalization.py',TRUE,100),
  ('street_suffix','PL','PL','normalization.py',TRUE,100),
  ('street_suffix','LANE','LN','normalization.py',TRUE,110),
  ('street_suffix','LN','LN','normalization.py',TRUE,110),
  ('street_suffix','PROMENADE','PROM','normalization.py',TRUE,120),
  ('street_suffix','PROM','PROM','normalization.py',TRUE,120),
  ('street_suffix','RAMP','RAMP','normalization.py',TRUE,130),
  ('street_suffix','ALLEY','ALLEY','normalization.py',TRUE,140),

  -- Added 2026-08-22, canonical form taken from public.roads.roadtype
  ('street_suffix','SQUARE','SQUARE','public.roads',TRUE,200),
  ('street_suffix','SQ','SQUARE','alias',TRUE,200),
  ('street_suffix','GATE','GATE','public.roads',TRUE,210),
  ('street_suffix','TERRACE','TERRACE','public.roads',TRUE,220),
  ('street_suffix','TERR','TERRACE','alias',TRUE,220),
  ('street_suffix','CLOSE','CLOSE','public.roads',TRUE,230),
  ('street_suffix','CIRCLE','CIRCLE','public.roads',TRUE,240),
  ('street_suffix','CIR','CIRCLE','alias',TRUE,240),
  ('street_suffix','WALK','WALK','public.roads',TRUE,250),
  ('street_suffix','SLIP LANE','SLIP LANE','public.roads',TRUE,260),
  ('street_suffix','GREEN','GREEN','public.roads',TRUE,270),
  ('street_suffix','WOOD','WOOD','public.roads',TRUE,280),
  ('street_suffix','TRAIL','TRAIL','public.roads',TRUE,290)
ON CONFLICT DO NOTHING;

-- Guard: every roadtype present in the centreline layer must be resolvable. If the
-- municipal data gains a new suffix, this fails loudly at migration time rather than
-- silently making those streets unmatchable (which is exactly the defect above).
DO $$
DECLARE missing text;
BEGIN
  SELECT string_agg(DISTINCT upper(btrim(r.roadtype)), ', ')
    INTO missing
  FROM public.roads r
  WHERE r.roadtype IS NOT NULL AND btrim(r.roadtype) <> ''
    AND NOT EXISTS (
      SELECT 1 FROM public.vocabulary v
      WHERE v.category = 'street_suffix' AND v.is_active
        AND v.term = upper(btrim(r.roadtype)));
  IF missing IS NOT NULL THEN
    RAISE EXCEPTION 'public.roads.roadtype values with no street_suffix vocabulary entry: %', missing;
  END IF;
END $$;
