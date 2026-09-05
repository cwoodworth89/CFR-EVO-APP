# Punch list — closed items

[← punch list index](../debug_and_qa_punchlist.md)

55 items closed. Retained for provenance; each file holds the full record of what was verified and how (CLAUDE.md §6.6).

| ID | Severity | Status | Item |
|:--|:--|:--|:--|
| **44a** | 🔴 crew-visible | CLOSED | [Round 1 wins the address unconditionally — Phase 2 never compares the two rounds](44a-round-1-wins-the-address-unconditionally-phase-2-never.md) |
| **62** | 🔴 crew-visible | CLOSED | [The geocoder's street-centroid step has raised on every call since the `parcels.lat` rename](62-the-geocoders-street-centroid-step-has-raised-on-every-call-si.md) |
| **66** | 🔴 crew-visible | CLOSED | [The kiosk address sanitizer removed 18 City street names that begin with a unit keyword](66-the-kiosk-address-sanitizer-removed-18-city-street-names-tha.md) |
| **67** | 🔴 crew-visible | CLOSED | [Step 4b, the nearest civic address, has raised on every call since the parcel column rename](67-step-4b-the-nearest-civic-address-has-raised-on-every-call-s.md) |
| **68** | 🔴 crew-visible | CLOSED | [The digit join glued the next clause's number onto the map grid when the STT lost round 2's opening](68-the-digit-join-glued-the-next-clauses-number-onto-the-map-gr.md) |
| **45a** | ⚪ hygiene | CLOSED | [Geocoder harness needs a review pass before its numbers are trusted again](45a-geocoder-harness-needs-a-review-pass-before-its-numbers.md) |
| **46a** | ⚪ hygiene | CLOSED | [No STT harness exists — WER is computed for training, never for regression](46a-no-stt-harness-exists-wer-is-computed-for-training-neve.md) |
| **61** | 🔴 crew-visible | CLOSED | [The API silently falls back to an empty SQLite file when Postgres is unreachable](61-the-api-silently-falls-back-to-an-empty-sqlite-file-when-po.md) |
| **53** | 🟠 operational | CLOSED | [The dispatch agent makes a WAN call to huggingface.co on every start](53-the-dispatch-agent-makes-a-wan-call-to-huggingface-co-o.md) |
| **44b** | 🟠 operational | CLOSED | [Kiosk crashed on a live dispatch — stale chunk after a frontend deploy](44b-kiosk-crashed-on-a-live-dispatch-stale-chunk-after-a-fr.md) |
| **2** | 🔴 crew-visible | CLOSED | [Intersection Geocoding & Hardcoded Port Moody Fallback (`DISP-2026-F1F345`)](02-intersection-geocoding-hardcoded-port-moody-fallback-di.md) |
| **7** | 🔴 crew-visible | CLOSED | [`custom_places.json` coordinates are hand-entered and some are badly wrong](07-custom-places-json-coordinates-are-hand-entered-and-som.md) |
| **9** | 🔴 crew-visible | CLOSED | [False intersection: DAVID AVE & PANORAMA DR](09-false-intersection-david-ave-panorama-dr.md) |
| **11** | 🔴 crew-visible | CLOSED | [Private hydrants defaulted to NFPA 291 class AA — fabricated flow rating](11-private-hydrants-defaulted-to-nfpa-291-class-aa-fabrica.md) |
| **13** | 🔴 crew-visible | CLOSED | [`public.intersections` needs the same data-integrity pass](13-public-intersections-needs-the-same-data-integrity-pass.md) |
| **15** | 🔴 crew-visible | CLOSED | [Fuzzy matching silently substituted a different intersection](15-fuzzy-matching-silently-substituted-a-different-interse.md) |
| **16** | 🔴 crew-visible | CLOSED | [`<street> and <street>` is a CAD artifact, not a self-intersection](16-street-and-street-is-a-cad-artifact-not-a-self-intersec.md) |
| **18** | 🔴 crew-visible | CLOSED | [96% of the Whisper hotword list is silently discarded](18-96-of-the-whisper-hotword-list-is-silently-discarded.md) |
| **23** | 🔴 crew-visible | CLOSED | [Live dispatches lost their street-section fields on the way to the kiosk](23-live-dispatches-lost-their-street-section-fields-on-the.md) |
| **24** | 🔴 crew-visible | CLOSED | [The kiosk displayed an invented hydrant on every dispatch](24-the-kiosk-displayed-an-invented-hydrant-on-every-dispat.md) |
| **33** | 🔴 crew-visible | CLOSED | [Legacy worked-example placeholders in the review form — one reached the training set](33-legacy-worked-example-placeholders-in-the-review-form-o.md) |
| **41** | 🔴 crew-visible | CLOSED | [`629 Cottonwood Ave` is absent from `public.parcels`](41-629-cottonwood-ave-is-absent-from-public-parcels.md) |
| **45b** | 🔴 crew-visible | CLOSED | [Retire `confidence_score`, replace it with named review flags](45b-retire-confidence-score-replace-it-with-named-review-fl.md) |
| **50** | 🔴 crew-visible | CLOSED | [The parcel import seeds `entrance_lat/lng` with the centroid on every INSERT](50-the-parcel-import-seeds-entrance-lat-lng-with-the-centr.md) |
| **52b** | 🔴 crew-visible | CLOSED | [An ampersand in the "near" clause silently discarded the second cross street](52b-an-ampersand-in-the-near-clause-silently-discarded-the.md) |
| **3** | 🟠 operational | CLOSED | [Missing `responding_units` in Replayed Dispatches](03-missing-responding-units-in-replayed-dispatches.md) |
| **6** | 🟠 operational | CLOSED | [Verify first live ingest through the new PostGIS path](06-verify-first-live-ingest-through-the-new-postgis-path.md) |
| **22** | 🟠 operational | CLOSED | ["Next 24h" / "Next 7d" closure filters matched nothing](22-next-24h-next-7d-closure-filters-matched-nothing.md) |
| **25** | 🟠 operational | CLOSED | [A corrected re-broadcast queued itself as a second call](25-a-corrected-re-broadcast-queued-itself-as-a-second-call.md) |
| **27** | 🟠 operational | CLOSED | [The worker process is unsupervised](27-the-worker-process-is-unsupervised.md) |
| **28** | 🟠 operational | CLOSED | [A stalled worker could block the audio listener — fixed](28-a-stalled-worker-could-block-the-audio-listener-fixed.md) |
| **29** | 🟠 operational | CLOSED | [Phase 1 session state lives only in worker memory](29-phase-1-session-state-lives-only-in-worker-memory.md) |
| **34c** | 🟠 operational | CLOSED | [The phantom "UPDATED" badge](34c-the-phantom-updated-badge.md) |
| **39** | 🟠 operational | CLOSED | [Review table: restore the verified value in the row, drop the pencil-and-legend](39-review-table-restore-the-verified-value-in-the-row-drop.md) |
| **40** | 🟠 operational | CLOSED | [Street basemap has no tiles above zoom 18 — but the reported symptom did not reproduce](40-street-basemap-has-no-tiles-above-zoom-18-but-the-repor.md) |
| **43b** | 🟠 operational | CLOSED | [The 8 failed cadastral tiles, and what the "blank" tiles actually are](43b-the-8-failed-cadastral-tiles-and-what-the-blank-tiles-a.md) |
| **46b** | 🟠 operational | CLOSED | [The API image was 22 GB because it baked in 10.7 GB of bind-mounted data](46b-the-api-image-was-22-gb-because-it-baked-in-10-7-gb-of.md) |
| **4** | ⚪ hygiene | CLOSED | [Remove Satellite View from Call Review Panel](04-remove-satellite-view-from-call-review-panel.md) |
| **5** | ⚪ hygiene | CLOSED | [Audio Player Simplification in Call Review Panel](05-audio-player-simplification-in-call-review-panel.md) |
| **8** | ⚪ hygiene | CLOSED | [The 11 test failures are NOT environmental — correcting the record](08-the-11-test-failures-are-not-environmental-correcting-t.md) |
| **19b** | ⚪ hygiene | CLOSED | [Audio player loading inconsistency & Auto-play removal](19b-audio-player-loading-inconsistency-auto-play-removal.md) |
| **26** | ⚪ hygiene | CLOSED | [The dispatch pipeline's INFO logging is discarded](26-the-dispatch-pipelines-info-logging-is-discarded.md) |
| **36** | ⚪ hygiene | CLOSED | [Double-click-to-autofill removed from the review form](36-double-click-to-autofill-removed-from-the-review-form.md) |
| **42** | 🔴 crew-visible | CLOSED | [The roads import silently discards 242 road segments, including 45 streets that 1,918 parcels are addressed on](42-the-roads-import-silently-discards-242-road-segments-in.md) |
| **12** | 🔴 crew-visible | CLOSED | [Street centroid reports the requested address as though exact](12-street-centroid-reports-the-requested-address-as-though.md) |
| **31** | 🔴 crew-visible | CLOSED | [`response_type` never reaches the kiosk — every call renders as ROUTINE](31-response-type-never-reaches-the-kiosk-every-call-render.md) |
| **43a** | 🔴 crew-visible | CLOSED | [Call-type vocabulary carries locale variants as duplicate rows; HITL captures incident as free text](43a-call-type-vocabulary-carries-locale-variants-as-duplica.md) |
| **38** | 🔴 crew-visible | CLOSED | [`DISP-2026-ACCF6D` routed to the wrong street — the parcel front point is on Pinetree Way](38-disp-2026-accf6d-routed-to-the-wrong-street-the-parcel.md) |
| **58** | 🔴 crew-visible | CLOSED | [Parcels whose street has no road keep a stale front point on a different street](58-parcels-whose-street-has-no-road-keep-a-stale-front-po.md) |
| **48** | 🔴 crew-visible | CLOSED | [One civic address, many parcels — the import keeps whichever the shapefile lists first](48-one-civic-address-many-parcels-the-import-keeps-whichev.md) |
| **10** | ⚪ hygiene | CLOSED | [Three test modules have never run in review](10-three-test-modules-have-never-run-in-review.md) |
| **35b** | 🔴 crew-visible | CLOSED | ["Near roads" stopped being recorded on 2026-08-21 — Phase 2 rebuilds `target` and drops `cross_streets`](35b-near-roads-stopped-being-recorded-on-2026-08-21-phase-2.md) |
| **51a** | 🟠 operational | CLOSED | [Add cross_street_1 and cross_street_2 to the review panel for HITL verification](51a-add-cross-street-1-and-cross-street-2-to-the-review-pan.md) |
| **59** | 🟠 operational | CLOSED | [Phase 2 crashed after saving audio, before recording its URL](59-phase-2-crashed-after-saving-audio-before-recording-its.md) |
| **47b** | 🟠 operational | CLOSED (accepted risk) | [Basemap tile licensing has never been checked — Carto and Esri](47b-basemap-tile-licensing-has-never-been-checked-carto-and.md) |
