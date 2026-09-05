# What the first harness baselines pointed at: three lists, and what each turned out to be

**Date:** 2026-09-05 · **Corpus:** 529 verified dispatches, 2026-07-12 to 2026-09-01 · **Model in
service:** `whisper-base-cfr-ct2` · **Tools:** `tools/harness_chain.py`, `backtest_parser_corpus.py`,
`trace_geocode_corpus.py --probe`, the kiosk database, and the City's own `Addresses.shp`.

The operator asked, after the first full baseline, to read the tails: the verified addresses the
geocoder could not pin, the calls whose map grid came out wrong, and the worst transcriptions.
Every line below is one call or one class of call, what it turned out to be, and where it went.
Nothing here is a pooled rate; the pooled rates are in `evaluation_history`.

## The short version

| Tail | Looked like | Was | Went to |
|:--|:--|:--|:--|
| 22 verified addresses the geocoder cannot pin | a geocoder gap | 16 civic numbers the City's own address file does not contain; 4 named places or bare streets; 1 correct unknown; 1 possible typo | **#64**, City register §14, backlog (named places, bare streets) |
| 32 wrong map grids in the STT run | parser trouble | the STT prompt echoed into pauses as *"map grid N"*, and the parser believed the first one it saw; 19 of the 32 | **#63**: parser mitigation shipped, the prompt is the operator's call, measured |
| 15 worst transcriptions | model quality | 3 PA pages the operator had already tagged `[PA]`; the rest mostly the same prompt echo; a few real mis-hearings | harness excludes `[PA]`; **#63**; hotword coverage (#18) |
| 23 wrong streets on stored transcripts | geocoder | STT homophones, two *"Thor"* heard as *"four"* glued onto the house number, four cross-street sections where round 2 had the parcel | **#44a** fixed (2 of the 4), #18, backlog |

One number changed my reading of everything else: **22 of the 325 "verified" calls since
August 1 are PA pages** (#14), captured as dispatches and then, honestly, marked `[PA]` in the
review notes. They were scoring as calls with no address. Every harness now leaves them out.

## A. Verified addresses the geocoder cannot pin

Of 303 verified addresses since 2026-08-01: 254 placed exactly, 27 at an intersection the
operator verified as one, 11 by block, 5 by street centroid, 6 not at all.

**The 16 civic numbers** (11 block, 5 street centroid) were checked one by one against
`Addresses.shp`, 69,708 rows, the file `import_parcels.py` reads. None is in it. So the import
did not lose them; the City's layer does not carry them. `1414 Pinetree Way` sits between 1413
and 1415 in that file; `1734 Eagle Mountain Dr` beside 1735; `629 Cottonwood Ave` (#41)
between 628 and 633. The table is in **#64**; the question for the City is register §14. Until
the City answers, block placement is the best the data allows and the entrance queue (#49) is
where a person pins them. The harness's new *approximate* bucket counts them as what they are.

**The 6 the geocoder cannot place at all:** `4522 Port Mann Bridge`, `Eagle Mountain Park`, and
a Lougheed on-ramp are named places, not addresses; the operator's own note on the park call
says *"no real address but gives a park; we need to be able to send"*, which is a feature
(backlog: named places, a table fed from City open data, never hand-entered coordinates, #7).
`Pinetree Way` alone is a bare street: `get_coordinates` returns before the ladder starts, so
not even the street centroid is tried (backlog). `Unknown Location` is verified as unknown and
correct. `1883 Beaty Pl`: no such street in `roads` or `parcels`; outside Coquitlam or a typo in
the verified column, for the operator.

## B. Wrong map grids

**On the stored transcripts** (the base model, the parser harness): 62 misses, 54 of them in
July, 49 of those with no grid at all, the tail-truncation defect the operator fixed around
2026-07-29 (`qa_harnesses.md` §4). The 8 in August are the old model cutting the number at the
end of the audio: *"map grid 1,"* for 100, *"map grid 8."* for 81. Nothing to fix in code; the
model in service does not do it.

**In the STT run** (the model in service): 32 misses, 19 of them on calls the stored
transcript had right. The fresh transcripts show the mechanism, and it is not the model
mis-hearing a number. It inserts the phrase *"coquitlam map grid N"* into the pause mid-round,
with a wrong N, and `split_rounds` cuts the round there while the parser takes the first grid
it sees. The phrase is the tail of the STT initial prompt. Full account, measurement and the
switch to test it in **#63**. On the 42 hardest calls: parser fix 32 → 25 wrong grids; no
prompt 25 → 7.

## C. The worst transcriptions

| Class | Calls | What to do |
|:--|--:|:--|
| PA pages tagged `[PA]` (*"watch us up"*, *"launches up"*, *"ice coffee"*) | 3 | excluded from every harness now; the capture itself is #14 |
| Prompt echo damage (*"2739 bond emergency coquitlam map grid 69 39 barnet…"*) | 6 | #63 |
| Genuine mis-hearings: *Portman* / Port Mann, *Patulow* / Patullo, *ego mountain* / Eagle Mountain, *Burningions* | 4 | hotword coverage, #18: 96 % of the hotword list is discarded by the token budget |
| Correct calls the metric punished (*"1, 3, 7, 8, Oxford"* is 1378 after sanitising; the operator rated it PERFECT) | 2 | none; the WER is honest after the prompt echo is removed |

Without the prompt, the mean WER on these 42 calls fell from 16.6 % to 2.9 %. They are the
worst calls by construction; the fair number is the 44-clip holdout run without the prompt,
recorded in `evaluation_history`.

## D. Wrong streets on the stored transcripts (23)

| Class | Calls | Where |
|:--|--:|:--|
| STT homophones: *Cancel* / Kensal, *Erxene* / Erskine, *Ronald* / Runnel, *Gaintainstbury* / Gatensbury, *Pine Tree* / Pinetree, *Guildford Kway Rcmps* | 6 | #18 (hotwords); all six streets exist in `roads` |
| *"Thor"* heard as *"four"* and glued to the house number: `3356 Thor Crt` → `33564 Crt` | 2 | #18; a lead for a guard, since no civic number in `parcels` has more than 4 digits (max 6000) |
| Cross-street section where the other round had the parcel: `Gordon Ave (Between …)` for `3030 Gordon Ave` | 4 | **#44a** fixed 2; the other 2 have no resolvable number in either round |
| Verified-column typos: *Riverband* for Riverbend, *Pintree* for Pinetree | 2 | operator |
| `Chartwell Green` for `Chartwell Rd` | 1 | #47a, external |
| The incident word leaked into the address: *"Smoldering Pinetree Way"* | 2 | the parser's call-type vocabulary does not contain *smoldering*; lead for #43a |
| Fragments (*"St"*, *"Dr"*, *"Burningions"*) | 3 | STT; #63 territory |

## What changed in the measurement itself today

`[PA]`-tagged calls excluded; *approximate* split out of *cosmetic* (a street centroid or a
cross-street section is not the same place); the transcript and verified round 1 written into
the per-call CSV; which step placed the *verified* address recorded, because a 0 m distance
between two fallbacks proves nothing; the git hash taken when a run starts. Rows recorded
before 2026-09-05 fold *approximate* into *cosmetic* and include the PA pages.

## For the operator

1. **The prompt** (#63): `STT_INITIAL_PROMPT=` empty in `backend/.env`, then restart `cfr-agent`.
   The holdout number is in `evaluation_history`. The hotwords still list *map grid*; untested.
2. **Restart `cfr-agent`** to pick up the sanitiser and #44a; the listener drops for seconds.
3. **Two verified-column typos** (*Riverband*, *Pintree*) and one probable one (*Beaty Pl*).
4. **The City question** in register §14, sixteen numbers.
