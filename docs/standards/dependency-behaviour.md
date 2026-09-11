# Verified Dependency Behaviour

Companion to [`README.md`](README.md). That file covers **domain standards** — what the
fire service and the GIS world specify. This file covers **library semantics** — what the
code we depend on actually does, as opposed to what its API name suggests.

Both categories caused real defects in the 2026-08-21/22 review, but the library ones were
more dangerous, because a domain gap feels like a gap while a library assumption feels
like knowledge.

## `StreetViewPanorama` minimum zoom is viewport-dependent, and can be wider than the Static API allows

**Measured 2026-09-08**, from the operator's own browser console on the kiosk.

| | |
|:--|:--|
| Street View **Static API** `fov` | documented 10..120 degrees |
| Street View **JS SDK** minimum zoom | not documented as a number; **enforced**, and it varies with the container's size |

At the expanded panel's 971x622 container the SDK refused to go narrower than zoom
`0.4996017945373167` -- **127.31 degrees**, wider than the Static API's 120 degree maximum.
The two limits are therefore **not nested**, and any attempt to hold the panorama inside the
Static API's range fights the SDK and loses:

```
setZoom -> 0.5849625007211562   at _.Os.<anonymous>  (our zoom_changed listener, 120 deg)
setZoom -> 0.4996017945373167   at _.Vm.set          (the SDK, 127.31 deg)
setZoom -> 0.5849625007211562   at _.Os.<anonymous>
setZoom -> 0.4996017945373167   at _.Vm.set
...
```

The loop is unbounded: `setZoom` re-fires `zoom_changed`, and neither side yields.

The size dependency is what made it look intermittent. With devtools open the sidebar
narrows the container, which raises the SDK's minimum above our floor, so the clamp never
engages and the panel behaves perfectly. Closing devtools widens the container, lowers the
SDK's minimum below our floor, and the fight resumes. Any bug that "only happens with the
console closed" should be suspected of depending on the viewport.

**Consequence for CFR EVO**: the panorama is never clamped. It records whatever zoom the SDK
settles on, and only the tile's URL is bounded, so at the widest end the expanded panorama
shows about 127 degrees where the compact tile draws 120.

**The general shape**: two limits from the same vendor, for the same quantity, that do not
nest -- and only one of them is written down.


## The pattern: the API name is not the contract

Every library defect found so far had the same shape — **the name described the intent,
not the behaviour**, and the code was written against the name.

| Called | The name implies | It actually does |
|:--|:--|:--|
| `hotwords=` | these words are boosted | keeps the first 223 tokens, silently discards the rest |
| `token_set_ratio` | a similarity ratio | returns **100** when one token set is a subset of the other |
| `ST_Contains` | the point is in the polygon | excludes the boundary, so a point on a zone edge is *not* contained |
| `multiprocessing.Process` | the child continues where the parent left off | on Python 3.14 it does not inherit logging config -- the default start method became `forkserver` |
| MQTT `qos=1` | delivered once, reliably | delivered **at least** once -- duplicates are guaranteed possible and the receiver must be idempotent |
| `requestAnimationFrame` | runs after the next paint | runs before the next repaint **only while the document is visible**. On a hidden tab or a blanked kiosk display it never fires |
| Leaflet `map.fitBounds(bounds, { padding })` | fits the bounds inside the padded box | **with padding wider than the container, the box is negative and the map's zoom becomes `NaN`**, silently. A map at zoom `NaN` draws no tiles, which looks like a dead tile server |
| `feature_extractor(speech, sampling_rate=16000)` | encodes the clip you gave it | **keeps the first 30 seconds and silently drops the rest.** `__call__` defaults to `truncation=True`, `padding="max_length"`, `max_length=n_samples` (`chunk_length` 30 x 16 kHz = 480,000 samples) |
| OSM `restriction=no_right_turn` | the sign at the junction | **whatever the mapper typed.** At Pinetree Way and Guildford Way the sign is *no right on red* (operator, 2026-09-09); the relation says *no right turn*. OSRM v26.8.0 applies the value as written and ignores every value ending `_on_red` — punch-list **#1** |
| `WhisperModel(dir, local_files_only=True)` | nothing is fetched from the network | **still downloads `tokenizer.json`** from huggingface.co when the model directory lacks one -- the flag does not cover that fallback |

None of these are bugs in the libraries. All are documented or evident in source. The
defect was on our side: **we trusted the name.**

## The same failure outside libraries

**Libraries are where this was first noticed, not where it lives.** On 2026-08-31 the pattern
appeared five times in one session and only one instance was a dependency. The others were
municipal data, our own code, a comment, and a test — none of which this file originally
covered, which is why they had nowhere to be recorded.

| Named | The name implies | It actually is |
|:--|:--|:--|
| `public.roads.STATUS` | whether the road is in service | **who owns it.** The whole domain is `OPERATING` / `PRIVATE` / `MOT` / `METRO`; there is no `CLOSED` value. Filtering to `OPERATING` dropped 242 roads and left 1,918 homes with no street — punch-list **#42** |
| `parcels.legaldesc = 'MASTER'` | the main building or the whole property | **strata common property.** Measured across 517 properties: 10.3% of the summed unit area, spanning the site — driveways and walkways between units. Adopting it as "the property" would have outlined a driveway network — **#48** |
| `front_lat`, `access_far_corner_m` | current, because they are columns | **derived, and nothing recomputed them.** A stored value is only true until its source moves. 56 parcels held an arrival point on a street they were not on; the far-corner distance was then measured from a point already deleted — **#58** |
| *"deliberately left untouched … surfaces as an approximate location rather than a confident wrong one"* (code comment) | those rows have no stale value | **they keep whatever the previous algorithm wrote.** "Skip the row" only yields that outcome if the row was empty. The comment described the author's intent, not the code — **#58** |
| `test_import_parcels_production_script_unmodified` | asserts the script is unmodified | **asserts only that the file exists.** Its stated requirement had since been deliberately reversed, and it would have passed either way |
| `GONE = re.compile(r"\b(delet\|remov)\b")` | matches words starting with "delet" | **matches neither.** The trailing `\b` requires a boundary between `delet` and `ed`, so the alternation was unreachable for every word it was written for. Written for this repository's own docs check, in `audit_skill_references.py`, and caught only by testing it against real sentences |
| `ILIKE '% near %'` over `raw_transcript` | counts calls that said "near" | **undercounts badly.** Locution transcripts read `"…, Near, Pacific, Street…"` — the word is followed by a **comma**, so a pattern requiring a space after it misses most of them. Measured 2026-08-31: 5 matches where the true count was 9. It made a healthy 1:1 field look like a 9-vs-5 discrepancy and nearly had a working parser investigated as a fabrication bug. Use `~* '\ynear\y'` — Postgres word boundaries, punctuation-safe |
| `--workers 8` alongside `rate_limit_sec` in `compile_mbtiles.py` | eight requests in flight, so eight times the throughput | **one request at a time.** `RateLimiter.wait()` serialises every worker behind a single lock, so the ceiling is `1 / rate_limit_sec` no matter how many workers there are. That is correct and deliberate — it is what makes the limit a real courtesy to a municipal server — but the two settings read as independent and are not. Cost 8.5 hours of unexplained wall-clock on the 2026-08-27 cadastral crawl |

The last row is the cheapest lesson in the file: it was written **while documenting this very
pattern**, by someone who had just spent a day finding instances of it, and it was still wrong
until run against real input.

### Tile crawls: work out the hours before starting, not during

`compile_mbtiles.py` pairs a worker pool with an optional `RateLimiter`. Because the limiter
serialises, **worker count does not affect throughput at all** once a rate limit is set — the
only two numbers that decide the runtime are the tile count and `rate_limit_sec`.

Tiles quadruple per zoom level, so the top level is roughly three-quarters of any crawl.
Counting the City bounding box (§5) at each level:

| Zoom | Tiles |
|:--|--:|
| 12–17 | 11,686 |
| 18 | 34,293 |
| 19 | 137,172 |
| 20 | **545,700** |
| **Total** | **728,851** |

That is a bounding box; Coquitlam's actual polygon is smaller, so treat it as a ceiling. At
the `ortho` layer's configured `rate_limit_sec = 0.05` (20 req/s) that is **about 10 hours**.
At the 5 req/s used for the 2026-08-27 cadastral crawl it would be **40 hours**.

Neither number is wrong — the pacing is a deliberate courtesy to municipal infrastructure
(operator decision 2026-08-27), and the City's server is not a commercial CDN. The failure is
starting one of these expecting minutes. Run the arithmetic first: **tiles × `rate_limit_sec`
÷ 3600 = hours**, and raising `--workers` changes none of it.

### What generalises

* **A column name is not a contract either.** Municipal fields are named by the people who
  publish them, for their purposes. `STATUS` and `MASTER` are both accurate in the City's
  world and misleading in ours. Query the distinct values before filtering on a field
  (`SELECT status, count(*) ... GROUP BY status` costs seconds).
* **Every stored derived value needs a named recomputation.** If `X` is computed from `Y`,
  write down what recomputes `X` when `Y` moves — or do not store `X`. `access_far_corner_m`
  was dropped for exactly this reason: it was wanted occasionally, so it became a report.
* **A comment states intent; only the code states behaviour.** Where an invariant matters,
  assert it in a test — punch-list **#50** exists because an invariant was held by a comment
  attached to the wrong function.
* **Test names are claims and are not checked.** A test asserting less than its name says
  passes forever and protects nothing.
* **Substring matching on transcripts is not word matching.** Locution punctuates heavily —
  `"Coquitlam, Medic 1, Respond Emergency, …, Near, Pacific, Street, and The High St"`. Every
  field name and keyword can be followed by a comma, so `ILIKE '% word %'` silently misses
  them. Use `~* '\yword\y'`. A count that is quietly low reads as a defect in whatever
  produced the other number, which is the expensive way to find out.

## Rule

Before an operational decision rests on a library function's behaviour, verify it against
the **installed source of the pinned version** or that version's documentation — and
record it here. For a pinned dependency the installed source is authoritative and beats
recollection (CLAUDE.md §7.3).

Cheapest reliable check: write the two-line probe that demonstrates the behaviour, run it,
and paste the output here. `token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')`
→ `100` took ten seconds to run and would have prevented a 4.3 km routing error.

## Verified behaviours

### faster-whisper 1.2.1 — `hotwords` is truncated, head-first

`faster_whisper/transcribe.py`, `TranscriptionOptions.get_prompt`:

```python
if len(hotwords_tokens) >= self.max_length // 2:
    hotwords_tokens = hotwords_tokens[: self.max_length // 2 - 1]
```

* `max_length` is **448** for the loaded model, so the cap is **223 tokens**.
* The **head** is kept (`[:n]`), so ordering of the hotword list is the whole policy.
* Truncation is silent — no warning, no return value, no exception.
* `initial_prompt` is a separate budget (it becomes `previous_tokens`, capped the same
  way), so the two do not compete.

**Consequence when unverified**: 1,173 alphabetically-ordered entries were supplied; 61
survived; the list ended at "Archworth Avenue"; every arterial in Coquitlam received no
biasing at all. Punch-list #18.

### thefuzz 0.22.1 (rapidfuzz 3.14.5) — `token_set_ratio` and the subset trap

```
token_set_ratio('LOUGHEED HWY', 'ALDERSON AVE & LOUGHEED HWY')  -> 100
```

`token_set_ratio` compares the *set intersection* against the differences, so when one
string's tokens are a subset of the other's it scores a perfect match regardless of how
much extra the longer string contains.

* Use `fuzz.ratio` when the two strings are meant to be the *same* thing.
* Never use `token_set_ratio` where one operand may be a fragment of the other.

**Also measured, and more fundamental**: for Coquitlam street names there is **no safe
similarity threshold at all**. Across all 1,079 road names, genuinely different streets
score `HAMBER CRT`/`AMBER CRT` **96**, `WESTWOOD ST`/`EASTWOOD ST` **93**,
`BURKE MOUNTAIN ST`/`BLUE MOUNTAIN ST` **93** — while corrections worth making score
`TASIS→TAHSIS` **95** and `JOHNSON→JOHNSTON` **98**. The populations overlap, so fuzzy
matching may **suggest** but must never **substitute**. Punch-list #15.

### PostGIS 3.4 — `ST_Contains` excludes the boundary

`ST_Contains(A, B)` is false when B lies on A's boundary; `ST_Intersects` is true.

Emergency response zone polygons are bounded **by the road network**, so every road
intersection sits exactly on a zone boundary. Using `ST_Contains` to find "which zone is
this junction in" returns NULL for them.

**Consequence when unverified**: 155 of 1,784 intersections had no map grid, and five
different containment queries across the codebase disagreed with each other. Now
consolidated into `public.zone_for_point()`. Punch-list #13.

### PostGIS 3.4 — `ST_ClusterDBSCAN` with `minpoints := 1` produces no noise

```
3 input points (2 close, 1 far), eps := 0.0002, minpoints := 1
-> 3 rows, 3 non-null cluster ids, 0 NULL, 2 distinct clusters
```

With `minpoints := 1` every point is its own core point, so nothing is classified as noise
and no row comes back with a NULL cluster id. `derive_intersections.py` relies on this: a
junction represented by a single centreline node must still become a cluster of one rather
than being dropped.

Verified 2026-08-22. Had it returned NULL for isolated points, single-node junctions would
have silently vanished from `public.intersections`.

### PostGIS 3.4 — `ST_LineMerge` signals failure through geometry type

```
disjoint parts  -> ST_MultiLineString (2 parts)
touching parts  -> ST_LineString      (1 part)
```

`ST_LineMerge` joins parts that share endpoints and leaves the rest alone, so a collection
that cannot be merged into a single line comes back as a `MultiLineString`. The geometry
type is therefore a reliable test for "did this merge".

`derive_intersections.py` uses `ST_LineInterpolatePoint` (which requires a `LineString`)
only when the merge yields `ST_LineString`, and falls back to `ST_PointOnSurface`
otherwise. Verified 2026-08-22 — the discrimination is correct.

This is also the shape of an earlier live defect: block interpolation had never worked
because `public.roads.geom` is `MULTILINESTRING` and `ST_LineInterpolatePoint` requires
`LINESTRING`, so step 3 of the geocoder cascade threw on every call and silently fell
through to coarser steps.

### Python 3.14 — `multiprocessing` defaults to `forkserver`, so children inherit nothing

```
python 3.14.4
multiprocessing.get_start_method() -> 'forkserver'
available: ['forkserver', 'fork', 'spawn']
```

Python 3.14 changed the default start method on Linux from `fork` to **`forkserver`**. A
forked child inherits the parent's memory, including any configured logging; a forkserver
child does not — it starts fresh with the root logger at **WARNING**, writing to stderr in
the default `WARNING:root:` format.

`orchestration.run_dispatch_system` called `setup_logging()` and *then* spawned the
pipeline worker, which was correct under `fork` and silently stopped working on 3.14.

**Consequence when unverified**: every `logging.info` in the two-phase dispatch pipeline was
discarded — no `Published … to Mosquitto` lines, no `[METRICS] Phase 1 TTA` timings, no
geocoder resolution notes. Only WARNING and above survived. The system was not diagnosable
from its logs for anything that did not raise a warning, which is what blocked the
investigation of punch-list #25. Punch-list #26.

**The tell was the log format**, not the missing lines: `WARNING:root:[DISP-…]` in the same
journal as `2026-08-22 14:34:04,724 - INFO - TONES CONFIRMED`. Two formats means two logging
configurations, and the default one means nobody configured it.

Two further forkserver consequences worth knowing:

* The child re-imports the target module, so **module-level side effects run again** in the
  child.
* The target must be **picklable by qualified name** — a function defined in an inline
  `python -c` script fails with `AttributeError: module '__main__' has no attribute …`.

Configure logging *inside* each process rather than relying on inheritance; that is correct
under every start method.

### Browser — `requestAnimationFrame` does not fire while the document is hidden

```
document.hidden            -> true
requestAnimationFrame(cb)  -> cb NOT called within 700 ms
setTimeout(cb, n)          -> cb called
```

Measured in the browser 2026-08-31 against the kiosk bundle. `requestAnimationFrame` is
specified to run *before the next repaint*; a hidden document never repaints, so the
callback is not throttled but **indefinitely deferred**. Timers keep firing when hidden
(throttled, but they fire).

**Consequence when unverified**: the punch-list #44b failsafe hands its one-shot reload
budget back by clearing a `sessionStorage` marker once a boot has proved healthy. Written
first as `requestAnimationFrame(() => requestAnimationFrame(clearReloadMarker))`, the
cleanup would never run on a kiosk whose display had blanked or whose tab was backgrounded.
The marker would stay set and the failsafe would silently degrade to **single-use for the
life of the tab** — so the *second* deploy would drop a live call onto the error card
exactly as before the fix.

The failure is invisible: the failsafe still works the first time, and nothing reports that
it has stopped working. Caught only by running the recovery twice with the pane hidden.

Use a timer for anything that must run regardless of visibility. Reserve
`requestAnimationFrame` for work that is genuinely about painting.

### MQTT QoS 1 — "at least once" means duplicates are part of the contract

```
publish:   client.publish(MQTT_TOPIC, msg, qos=1)      mqtt_broker.py
subscribe: client.subscribe(topic, { qos: 1 }, ...)    useMqttListener.js
```

QoS 1 reads as a reliability *upgrade* from QoS 0, and it is — but the guarantee is
**at-least-once**, not exactly-once. Redelivery is expected behaviour: if the broker does
not receive a PUBACK it sends the message again, which is why the protocol carries a DUP
flag. **The receiver is required to be idempotent.** Exactly-once is QoS 2, which costs a
four-part handshake.

**Consequence when unverified**: the kiosk queued a duplicate delivery as a second
incident. Verified from the journal for `DISP-2026-F33FA3` — the backend published exactly
one INSERT and one UPDATE:

```
15:12:00  Published INSERT event to Mosquitto MQTT   (phase 1)
15:12:20  Published UPDATE event to Mosquitto MQTT   (phase 2, Match=True, Corrected=False)
```

The backend was correct. The duplicate was a redelivery of the INSERT, and
`useKioskQueue.handleInsert` had no de-duplication, so it appended the same dispatch to the
queue and raised the amber "1 New Call Queued" banner for the call already on screen.
Punch-list #25.

The fix — keying on `dispatch_id` and merging rather than queueing — is not a workaround.
It is the idempotency QoS 1 requires of every subscriber.

**Note the ordering trap this creates for diagnosis.** A duplicate INSERT and a phase 2
correction produce the *same visible symptom*. Only the broadcast log distinguishes them,
which is why punch-list #26 (the pipeline's discarded logging) had to be fixed first —
the first attempt at this investigation concluded "phase 2 re-broadcast" from the symptom
alone, and the logs later showed phase 2 published UPDATE exactly as designed.

### transformers 5.14.1 — `WhisperFeatureExtractor` truncates to 30 seconds, silently

Verified against the installed source on the kiosk,
`.venv/lib/python3.14/site-packages/transformers/models/whisper/feature_extraction_whisper.py`,
2026-08-31:

```
chunk_length = 30                      # __init__ default
n_samples    = chunk_length * sampling_rate      # 480,000 = 30.0 s
truncation   = True                    # __call__ default
padding      = "max_length"            # __call__ default
max_length   = max_length if max_length else self.n_samples
```

Confirmed live: `WhisperFeatureExtractor().n_samples` returns `480000`.

Whisper's encoder takes a fixed 30-second window, so this is correct behaviour for the
model — but it is invisible at the call site. `feature_extractor(speech, sampling_rate=16000)`
with no `max_length` returns the same shaped tensor for a 12-second clip and a 75-second
one. Nothing warns, and the discarded audio does not appear in any log.

**Where this bites us**: [`train_whisper_lora.py`](../../tools/train_whisper_lora.py)
pairs that call with a label covering the **whole** recording. CFR dispatches are
double-round broadcasts averaging ~48 s — 486 of the 490 training-eligible calls run longer
than 30 s, the longest 74.9 s — and
[`extract_training_data.py`](../../tools/extract_training_data.py) deliberately
duplicates the transcript for calls over 25 s so the label spans both rounds. The input is
therefore the first 30 seconds and the target is roughly twice that much speech.

Note this is a **training-only** skew. Inference goes through faster-whisper, which does
long-form sequential decoding over successive 30-second windows and reads the whole file.

### faster-whisper 1.2.1 -- `local_files_only=True` does not cover the tokenizer

Observed on the kiosk 2026-09-01, loading a freshly converted fine-tuned model:

```
Loading .../whisper-base-cfr-ct2 ...
HTTP Request: HEAD https://huggingface.co/openai/whisper-tiny/resolve/main/tokenizer.json
```

`local_files_only=True` was passed. It governs the *model weights* lookup. When the model
directory has no `tokenizer.json`, faster-whisper separately fetches one from the Hub --
and hardcodes `openai/whisper-tiny` as the source regardless of the model's actual size.

Two things make this dangerous rather than merely untidy:

* It is a WAN call on the boot path of an offline dispatch system (CLAUDE.md s1). With no
  internet the model does not load at all -- it is not a degraded mode, it is a failure.
* It is silent on the happy path. The model loads, transcribes correctly, and scores
  normally, so nothing reveals the dependency until the network is gone.

`ctranslate2.converters.transformers` does not copy the file, even though the preceding
`processor.save_pretrained(merged_dir)` writes it. The converter takes `--copy_files`;
[`train_whisper_lora.py`](../../tools/train_whisper_lora.py) now passes
`--copy_files tokenizer.json`.

Verified after the fix: the model loads under `HF_HUB_OFFLINE=1` + `TRANSFORMERS_OFFLINE=1`
with `local_files_only=True`, and holdout WER is unchanged at 2.76% -- the downloaded
tiny tokenizer and the model's own were equivalent, so this was a live outage risk rather
than a correctness bug. It would not have stayed that way for a differently-sized model.

### faster-whisper 1.2.1 / CTranslate2 — word timestamps change with `OMP_NUM_THREADS`

**Measured 2026-09-05 on the kiosk**, same 61 recordings, same code
(`tools/prepare_round2_dataset.py --stop-after-cut`, the round-1 cut: speech onset and the
round boundary from `word_timestamps=True`, `beam_size=1`, int8 on CPU):

| Environment | New calls cut | Dropped as "rounds not separable" / "over 30 s" |
|:--|--:|--:|
| plain | 42 of 61 | 5 / 8 |
| `OMP_NUM_THREADS=6 nice -n 15` | 3 of 61 | 25 / 24 |

The mechanism is not known and is not guessed at here. The result is that the timestamped
words under six threads are different enough that the round boundary is found on 3 calls
instead of 42; the transcripts themselves were not compared. Consequence: build a dataset, or
measure anything that depends on word timestamps, in the plain environment. `OMP_NUM_THREADS=6`
stays for training only, where it exists to leave cores for a live dispatch and numeric
determinism does not matter. The round-2 job runs the build plain and the training under six
threads for exactly this reason.

### OSRM v26.8.0 — which `restriction` values the parser applies, and which it ignores

**Read 2026-09-09** in `src/extractor/restriction_parser.cpp` at tag `v26.8.0`, the version
running on the kiosk ([`osrm/README.md`](osrm/README.md)), after punch-list #1 came down to one
OSM relation.

`RestrictionParser::TryParse`:

* A value starting `only_` is an only-restriction. A value starting `no_` is a no-restriction
  **unless it ends `_on_red`**. Anything else yields nothing. So `no_right_turn_on_red`, the
  tag for the sign at Pinetree Way and Guildford Way, is not a restriction to OSRM at all —
  it has no signal state and leaves a right-on-red ban alone, which is right. The relation
  there (6812366) is tagged plain `no_right_turn`, a full ban, and that is the whole cause of
  the 50 m lap of the junction on every westbound Hall 1 route.
* The test is `starts_with`, not equality. Relation 17957326 has its time window written into
  the plain tag — `no_right_turn @ (Mo-Fr 07:00-09:00,16:00-18:00)`, via 49.25084, −122.86907 —
  and because that starts with `no_` it is applied **all day**. The window belongs in
  `restriction:conditional`, a different tag.
* `except=` is split on `;` and the restriction is dropped when any item is in the profile's
  `restrictions` list — for `car.lua` that is `motorcar`, `motor_vehicle`, `vehicle`. The
  City's 22 `except` values are psv, bicycle, bus, hgv, police, staff, "city vehicle": every
  one leaves the restriction in force for the car. `except=emergency` would too, unless a
  profile adds `emergency` to its list; no City restriction carries it today.
* Tags are read in the order `restriction`; then `restriction:conditional` and
  `restriction:<mode>:conditional`, **only when the extractor was told to parse conditionals**
  (`parse_conditionals`, which is `osrm-extract --parse-conditional-restrictions`, verified in
  the pinned image's `--help` 2026-09-09, applied at customize time by
  `osrm-customize --parse-conditionals-from-now` with `--time-zone-file`); then
  `restriction:<mode>` per mode in the list. Whether the kiosk graph's unrecorded build parsed conditionals is not known, so the
  City's 21 weekday-peak turn bans are either all applied or all absent. The check is a route
  through one of them (Clarke Rd → Chapman Ave, `no_right_turn @ (Mo-Fr 07:00-09:00)`, via
  49.26909, −122.88056) at the first rebuild, when the command is recorded.

### OSRM v26.8.0 — routes are chosen by weight and reported in duration, and the two diverge on penalised ways

**Measured 2026-09-09** on the kiosk, stock `car.lua` against `apparatus.lua`, 2,248 routes
each. A route response's `distance` and `duration` are the metres and seconds along the route
returned; they are not the quantity the router minimised. With `weight_name = 'routability'`
(car.lua line 21) the router minimises weight, and `WayHandlers.penalties`
([`osrm/lib/way_handlers.lua`](osrm/lib/way_handlers.lua) lines 466–474) sets a way's *rate* to
speed × the smallest of the service, width, alternating, side-road and priority penalties,
while its duration comes from the speed alone. A penalised way is therefore cheap in time and
dear in weight. Seen: once turn restrictions came off, six routes to 3007 Glen Dr left the slip
lane for the direct turn at Pinetree Way, 11 s *slower* by duration and lighter by weight.
Consequences: an ETA taken from `duration` is the true time along the route shown, so §6.2
holds; and a route that got slower after a profile change is not by itself a defect, it may be
the lighter route. The earlier unverified entry for this is closed.

### Leaflet 1.9.4 — `fitBounds` with padding wider than the container gives zoom `NaN`

```
container 1596 x 936, paddingTopLeft [340,80], paddingBottomRight [400,80]  -> getZoom() 14
container   73 x 788, same padding                                            -> getZoom() NaN, nothing thrown
```

Measured 2026-09-09 in headless Chromium against the installed `leaflet/dist/leaflet.js`
(1.9.4), with the two points the console fits, Hall 1 and a destination about 3 km away.
`getBoundsZoom` subtracts the padding from the container size and takes the log of the
ratio; a negative size gives `NaN`, and `setView` accepts it. The map is then a blank pane:
a tile layer at zoom `NaN` requests nothing, which is indistinguishable on sight from the
tile-server failure punch-list #40 painted the hatch to rule out.

**Consequence when unverified**: the console's route fit writes the sidebar widths as
literals, `paddingTopLeft: [340, 80], paddingBottomRight: [400, 80]`, in `MapBoard.jsx` and
twice in `MapViewControls.jsx`. Any container narrower than 740 px crosses the line: a phone
in either orientation, and an iPad in portrait with the sidebar open (500 px of map). The
dispatch map measures its floating box (`panelRef.current.offsetWidth`) instead, and does
not have this. The fix is the same pattern in one place; found by the mobile accessibility
review ([`briefings/mobile_accessibility_review.md`](../briefings/mobile_accessibility_review.md))
and **built the same day** as `frontend/src/components/map/fitPadding.js`: one place both maps
read, measuring the container and whatever floats over it, with a clamp so the two paddings on
an axis never exceed 60 % of it and the `NaN` cannot occur.

Measure the padding from the elements that occupy the map, never write it down.
### OSRM v26.8.0 — `way:get_location_tag` decides by the way's last node, and the profile guide never mentions it

**Read 2026-09-09** in `src/extractor/scripting_environment_lua.cpp` at tag `v26.8.0` ("use a
single node (last) of the way to localize the way") and on the project wiki page *Using
location dependent data in profiles* ("it is always the last node of a way", and with
overlapping polygons "the first found tag value will be returned"). `docs/profiles.md` at the
same tag contains no mention of location-dependent data at all; `osrm-extract --help` on the
pinned image lists `--location-dependent-data`. Consequences: a road along a boundary is inside
or outside by where its way ends, which is why the City polygon is the boundary buffered 100 m;
and a way that crosses out of the polygon counts as outside for its whole length, seen as
2925 Barnet Hwy moving by 13 s at factor 0.1 for no gain. Without the flag every way reads as
outside, so the profile's factor must stay off when no polygon was given (`apparatus.lua`,
`city_limits_factor` is nil unless set at build time).

### JavaScript and Python disagree about an empty list, and the same fallback was written in both

**Measured 2026-09-11** on the running system, after the fix in `79a05f5` reached the database
and not the kiosk.

The dispatch record carries `routing_metrics` twice — the column, and inside `target` — and both
readers pick between them with what looks like the same expression:

| | | |
|:--|:--|:--|
| `api/routers/dispatches.py` | `if not metrics:` -> fall through to `target` | `[]` is **falsy** in Python |
| `kiosk/KioskView.jsx` | `a.routing_metrics \|\| a.target?.routing_metrics` | `[]` is **truthy** in JavaScript |

`||` selects the first **truthy** operand, and every array is truthy in JavaScript, `[]`
included. So the JavaScript reader can never fall through on an empty list: it returns the
empty one and stops. The Python reader, on identical data, returns the populated one.

**Consequence when unverified**: phase 1 writes `routing_metrics` at the top level and phase 2
wrote its recomputed answer only into `target`. On a page load the API resolved it correctly and
the ETAs appeared; on the live MQTT `UPDATE` the merge kept phase 1's top-level `[]`, `||` chose
it, and the units stayed at `--:--` on the one call it mattered for — the one being corrected
while the crew watched. The bug was invisible to every check that involved a reload, which is
every check a developer makes by habit. Fixed in `edad22d`: phase 2 sends both copies, and the
kiosk takes the first list with entries rather than the first truthy one.

Neither expression is wrong for its language. What was wrong was carrying one language's
reading of "empty means keep looking" across an API boundary into the other. A fallback that
spans the Python/JavaScript line has to be written twice and verified twice.


## Unverified — assumptions still resting on names

Recorded so they are visible (§7.5). None of these have been checked.

* **Silero VAD** (`vad_filter=True` in `transcriber.py`) — what it removes, and whether it
  can clip the leading tones or the first unit name of a dispatch.
