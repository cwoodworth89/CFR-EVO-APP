---
name: stt-mlops-backtest
description: Procedures for building the Whisper fine-tuning dataset from verified dispatches, training and scoring a model on held-out calls, backtesting it against the stored production transcripts, deploying it, and running the parser regression suites.
---

# STT MLOps: Training, Scoring, Backtesting, Deploying

Everything runs **on the kiosk** (`tcfire@100.95.146.94`), where the audio, the database and
the training dependencies are. Prefix every Python invocation with
`XDG_RUNTIME_DIR=/run/user/1000`: importing `cfr_dispatch` pulls in PortAudio, and without
it the import dies before your script runs. Design, measurements and rejected alternatives:
[`docs/briefings/whisper_training_round1_labelling.md`](../../../docs/briefings/whisper_training_round1_labelling.md).

## Read this first: the two traps that produced wrong numbers

**Round alignment.** Locution reads every dispatch twice. The operator's verified transcript
is usually *one* round; a full-recording transcription is *two*. Score one against the other
and every word of round 2 is an insertion — a 131% WER was reported this way on 2026-09-02
before being caught. Either score round-1 clips against round-1 labels
(`eval_round1_holdout.py`), or split the hypothesis with `split_rounds()` and score its
round 1 (`backtest_regression.py` does this). Never score a raw full-call transcript.

**Train-on-test.** The 2026-07-17 "22.6% → 3.5% WER" was measured on the 51 calls it was
trained on and under a labelling defect. `prepare_training_clips.py` writes a deterministic
10% holdout (every 10th call by `dispatch_id`) that training never sees; every number quoted
for a model comes from that holdout or from calls the model has not trained on.

## 0. Check the labels

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python tools/check_verified_transcripts.py --blocking-only"
```

A verified transcript is both the training label and the scoring reference, so a typo in it
is trained in and then scored as correct — two of six holdout address failures on
2026-09-02 were the label ("Norbur Pl" for Norbury). The check validates every flagged
transcript against `public.roads`, `public.vocabulary`, `public.parcels` and the corpus.

The operator's `include_in_training` flag is the exclusion mechanism — un-checked by hand for
PA pages and cut-off recordings. The check runs in that order:

* **UN-FLAG** (blocks) — a call whose note says `[PA]` or cut-off, still flagged. Un-check it
  in the review panel; nothing else about that call matters.
* **FIX** (blocks) — the main-address street is not a street the city has. Fix the transcript.
  The hint lists the nearest road name *and* every parcel carrying that house number, those in
  the call's map grid first — house + prefix + zone resolved "beaty" to Beedie Pl when
  spelling alone could not.
* **GRID** (advises) — the grid spoken in the verified text disagrees with `verified_map_grid`.
  Either side may be wrong; the backtest scores against the field.
* **ADVISE** — probable typos elsewhere, rare cross streets, missing parcels. Worth fixing;
  not worth stopping for.

`prepare_training_clips.py` runs this itself and refuses to build while anything blocks
(`--skip-label-check` overrides). Operator ruling 2026-09-02.

## 1. Build the dataset

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python tools/prepare_training_clips.py --force"
```

Selects calls with `feedback_submitted`, a verified transcript, and the operator's
`include_in_training` flag not false — **that flag is authoritative**; sampling the
recordings directory instead swept in PA pages the flag had already excluded. Each call
becomes one clip of round 1 paired with round 1 of the verified text:

```
onset    = timestamp of the first spoken word ("Coquitlam" -- always, operator 2026-08-31)
boundary = start of round 2, from split_rounds() run over the timestamped words
clip     = audio[onset : boundary]      label = split_rounds(verified)[0]
```

Both edges are measured per call. Dropped, never truncated: rounds over Whisper's 30 s
encoder window, calls with the post-round addendum, calls that do not open with "Coquitlam".
Always pass `--force` after a code change — existing clips are otherwise reused.

Outputs `data/training/round1_clips/`, `metadata_round1_train.csv`, `metadata_round1_holdout.csv`.
Read the summary: the `cut diagnostic` (heard/claimed words) should sit at 1.00; the
`measured boundary vs the retired midpoint formula` line shows how far a two-equal-rounds
assumption would have missed.

## 2. Train

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 OMP_NUM_THREADS=6 WHISPER_CT2_OUT=/home/tcfire/CFR-EVO-APP/backend/models/whisper-base-cfr-ct2-vN nice -n 15 .venv/bin/python tools/train_whisper_lora.py"
```

* **`WHISPER_CT2_OUT` to a fresh directory, always.** The default path is the one the live
  daemon has deployed; training over it fails silently at the next restart.
* `nice -n 15` and `OMP_NUM_THREADS=6` so a real dispatch preempts training. ~50 min for
  ~400 clips on the kiosk's 8 cores.
* The trainer refuses to start if any clip exceeds 30 s, and copies `tokenizer.json` into the
  output — without it faster-whisper fetches one from huggingface.co at load time despite
  `local_files_only=True`, and an offline kiosk cannot load the model at all.
* Hyperparameters (`r=32, alpha=64, lr=1e-3, 5 epochs`) are inherited from the original
  notebook and uncited — a §6.3 gap, open.

## 3. Score on the holdout

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python tools/eval_round1_holdout.py --models base /home/tcfire/CFR-EVO-APP/backend/models/whisper-base-cfr-ct2 /home/tcfire/CFR-EVO-APP/backend/models/whisper-base-cfr-ct2-vN"
```

Prints WER and exact-match per model on the clips training never saw. **Caveat when
comparing generations:** the holdout membership shifts if the drop set changed, so a
*previous* model's score on the *new* holdout can include calls it trained on. Base and
the new model are clean; the old one is flattering.

Reference points: base 23.2%; v1 (midpoint cut, 2026-09-01) 2.76%→6.24% depending on
holdout; v2 (measured boundary, 2026-09-01) 5.28%, 20/44 exact.

## 4. Backtest against production transcripts (SMMR)

`backtest_regression.py` compares the **stored** `raw_transcript` (what production heard at
the time) with a fresh transcription from the active model, round-aligned, and reports
Structured Metadata Match Rate — address, units, incident, grid, channel — which is what
crews actually see. It writes a row to `public.evaluation_history` labelled with the model
that ran.

It reads `data/training/metadata.csv` (whole-call), so refresh that first and restrict it
to the holdout for an honest number:

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python tools/extract_training_data.py"
```

Then swap in a holdout-only `metadata.csv` (back the full one up, filter to the
`file_name`s in `metadata_round1_holdout.csv`, restore afterwards) and run:

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend && XDG_RUNTIME_DIR=/run/user/1000 .venv/bin/python tools/backtest_regression.py"
```

**To score a model other than the deployed one:** `backend/.env` overrides the shell
environment (`_load_env()` writes `os.environ` on import), so `WHISPER_MODEL=... python`
is silently ignored. Patch the module instead, in a wrapper:

```python
import cfr_dispatch, cfr_dispatch.stt.transcriber as T, runpy
T.WHISPER_MODEL = "/home/tcfire/CFR-EVO-APP/backend/models/whisper-base-cfr-ct2-vN"
runpy.run_path("tools/backtest_regression.py", run_name="__main__")
```

Reference: v1 on its holdout — WER 39.7%→4.9%, SMMR 93.5% (units 100, incident 97.8,
channel 93.5, grid 91.3, address 82.6). On the 2026-09-02 holdout every address failure was
an STT failure; the parser never missed an address when the transcript was exact.

## 5. Deploy

Ask first — the restart drops the audio listener for a few seconds.

```bash
ssh tcfire@100.95.146.94 "cp -p /home/tcfire/CFR-EVO-APP/backend/.env /home/tcfire/CFR-EVO-APP/backend/.env.pre-deploy-\$(date +%Y%m%d-%H%M%S) && sed -i 's|^WHISPER_MODEL=.*|WHISPER_MODEL=/home/tcfire/CFR-EVO-APP/backend/models/whisper-base-cfr-ct2-vN|' /home/tcfire/CFR-EVO-APP/backend/.env"
```

```bash
ssh tcfire@100.95.146.94 "sudo systemctl restart cfr-agent"
```

```bash
ssh tcfire@100.95.146.94 "journalctl -u cfr-agent --no-pager -n 50 | grep -iE 'faster-whisper model|error|opened audio stream'"
```

Confirm the load line names the new directory. Roll back by setting the value to `base` (or
the previous directory) and restarting.

## 6. Archive

`backend/models/` is git-ignored; the 2026-07-17 model was lost as a headless `model.bin`.
Archive **the whole directory** with the dumps, then pull it off the kiosk:

```bash
ssh tcfire@100.95.146.94 "cd /home/tcfire/CFR-EVO-APP/backend/models && tar czf /home/tcfire/cfr-backups/cfr-model-whisper-base-cfr-ct2-vN-\$(date +%Y%m%d-%H%M%S).tar.gz whisper-base-cfr-ct2-vN && cd /home/tcfire/cfr-backups && sha256sum cfr-model-*vN*.tar.gz > \$(ls -t cfr-model-*vN*.tar.gz | head -1).sha256"
```

```powershell
.\backend\scripts\pull_backups.ps1
```

## 7. Parser regression suites (stored transcripts — parser health, not the model)

These replay `raw_transcript` through the parser and never touch Whisper:

| Script | Measures | Read it as |
|:--|:--|:--|
| `backtest_parser_corpus.py` | per-field accuracy **by month** against `verified_*` | the honest parser number; pooled rates mix fixed and live defects |
| `backtest_parser.py` | production vs destructive parser | single denominator across fields — treat per-field rates as approximate |
| `backtest_round_comparison.py` | round-1 vs round-2 disagreement as a warning signal | where STT still splits on street names |

## What is still open

* **Address is the weakest field** (82.6% SMMR). Every remaining failure is STT, and two
  of six were house-number digits that `public.parcels` could correct ("999 Laval St" does
  not exist; 99 does). A parcel-validating resolver is the next gain — with any snapped
  address flagged as such, never presented as heard (§6.1).
* Hotword biasing is a wash on the fine-tuned model (5.28% → 5.12%, helped 8 calls, hurt 8).
* Retrain on a trigger, not a schedule: a new street or incident type, a template change by
  dispatch, or ~100 new verified calls.
