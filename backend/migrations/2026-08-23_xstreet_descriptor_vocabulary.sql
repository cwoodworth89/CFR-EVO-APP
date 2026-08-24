-- XStreets descriptors: the things Locution announces that are not streets.
--
-- TERMINOLOGY. The printed run sheet labels this field "XStreets:", so that is the
-- name used throughout. Locution speaks them as "near <x> and <y>". Despite "cross",
-- they are proximity references: they often parallel the incident street rather than
-- crossing it, and they are not always streets at all.
--
-- WHY THIS EXISTS. Measured across the 283 dispatches carrying XStreets (2026-08-23):
--
--     both names match a real road   129   46%
--     only one name matches           44   16%
--     neither matches                 23    8%
--     only one road announced         87   31%
--
-- The unmatched names are two different things that currently look identical to the
-- system -- both are simply "did not match public.roads":
--
--   * a descriptor, where dispatch correctly named a feature that is not a street
--     ("Turning Lane", "Mall Access", "Walton Elementary School Access"), and
--   * a mis-transcription of a real street ("Tanger Crt" for Tanager Court,
--     "Crab Avenue" for Craigen Avenue, "Salal Cresson" for Salal Crescent).
--
-- Telling them apart matters most to the parser audit, which would otherwise count
-- ~91 descriptor occurrences as speech-to-text errors when the system was working
-- correctly. It also lets the geocoder say "dispatch named a turning lane, not a
-- street" instead of "one name did not match".
--
-- SHAPE. One row per spoken variant, term_normalized carrying the canonical form --
-- the same convention public.vocabulary already uses for street_suffix
-- ("AVENUE" and "AVE" both normalize to "AVE").
--
-- metadata.kind records whether the descriptor can ever have a location:
--
--   generic   -- no single location exists. There are hundreds of turning lanes.
--                A coordinate for these could only ever be invented (CLAUDE.md §6.1).
--   prefixed  -- names a specific facility, announced with the facility in front
--                ("Walton Elementary School Access"). Locatable in principle. When
--                that is built, coordinates must come from the Coquitlam Open Data
--                schools/parks/civic-facilities layers, NOT hand entry -- this is the
--                mistake custom_places made, where script-generated coordinates sat up
--                to 1.8 km from the parcel and the table was removed for it.
--   ambiguous -- names a real place but not which one ("Mall Access"). Needs the
--                incident's own context; not locatable from the term alone.
--
-- metadata.observed is the count in the dispatch corpus as of 2026-08-23, kept so a
-- later reader can tell a common term from a one-off without re-deriving it.
--
-- NOT INCLUDED, deliberately:
--   "School Clean" (1) -- a mis-transcription of "School Access". Encoding a typo as
--                        vocabulary would make the system treat a known STT error as
--                        correct dispatch language.
--   "Coquitlam" (5)    -- the city name leaking into the XStreets field, a parser bug.
--   "Pacific Coquitlam Engine 1 Engine 2 ..." -- the unit list leaking in, likewise.
--
-- source is varchar(20), hence the abbreviated 'corpus_2026-08-23' tag rather than a
-- fuller description; the derivation is documented here instead.
--
-- Idempotent: re-running inserts nothing new.

BEGIN;

INSERT INTO public.vocabulary (category, term, term_normalized, source, is_active, metadata)
VALUES
    -- Generic: a road feature type, never a specific place.
    ('xstreet_descriptor', 'Turning Lane',     'TURNING LANE',     'corpus_2026-08-23', true, '{"kind":"generic","observed":62}'),
    ('xstreet_descriptor', 'Turning Ln',       'TURNING LANE',     'corpus_2026-08-23', true, '{"kind":"generic","observed":42}'),
    ('xstreet_descriptor', 'Turn Ln',          'TURNING LANE',     'corpus_2026-08-23', true, '{"kind":"generic","observed":1}'),
    ('xstreet_descriptor', 'Access Road',      'ACCESS ROAD',      'corpus_2026-08-23', true, '{"kind":"generic","observed":6}'),
    ('xstreet_descriptor', 'Access Rd',        'ACCESS ROAD',      'corpus_2026-08-23', true, '{"kind":"generic","observed":5}'),
    ('xstreet_descriptor', 'Private Driveway', 'PRIVATE DRIVEWAY', 'corpus_2026-08-23', true, '{"kind":"generic","observed":3}'),

    -- Prefixed: announced as "<facility name> School Access". Matching is on the
    -- trailing phrase, so one row covers every school rather than needing a row per
    -- school forever.
    ('xstreet_descriptor', 'School Access',    'SCHOOL ACCESS',    'corpus_2026-08-23', true, '{"kind":"prefixed","observed":8,"examples":["Walton Elementary School Access","Glenn Eagle Secondary School Access","Scot Creek Middle School Access","Summit Middle School Access","Glen Elementary School Access"]}'),
    ('xstreet_descriptor', 'Park Access',      'PARK ACCESS',      'corpus_2026-08-23', true, '{"kind":"prefixed","observed":2,"examples":["Park Access","Town Center Park Access Rd"]}'),

    -- Ambiguous: a real place, but the term does not say which.
    ('xstreet_descriptor', 'Mall Access',      'MALL ACCESS',      'corpus_2026-08-23', true, '{"kind":"ambiguous","observed":10}')
ON CONFLICT DO NOTHING;

COMMIT;
