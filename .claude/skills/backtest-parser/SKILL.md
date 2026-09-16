---
name: backtest-parser
description: Run the parser regression over the stored transcripts and report the per-field numbers by month, before and after a change. Heavy and noisy, so it runs in its own sub-agent and the corpus output stays out of the calling chat.
when_to_use: A sanitize or parser change needs confirming, or someone asks what the parser's accuracy has been by month.
argument-hint: [the change to confirm, and the months to cover]
arguments: [scope]
context: fork
agent: stt-mlops-evaluator
background: true
---

Backtest the parser against the stored transcripts for: **$scope**

Follow the `stt-mlops-backtest` runbook, which is already loaded. It is the source for the
commands and their paths; do not reconstruct them from memory, and check a path before running it.

## What to run

* **§7, the parser regression suites** — `backtest_parser_corpus.py` for per-field accuracy **by
  month** against the `verified_*` columns. By month, never pooled: a pooled rate mixes calls
  whose data was fixed later with live ones and reads better than the parser is.
* **§4 only if the change could move the transcript itself**, not just the parser.

Everything runs on the kiosk over SSH, with the environment the runbook gives.

## The two traps the runbook opens with

Read that section before the first command and honour both. A number produced against a raw
full-call transcript, or against the wrong round, is not a parser number, and reporting it as one
is the failure this skill exists to avoid.

## Rules

* **Report what the run produced.** If a month is thin, say how thin; if a suite errors, report the
  error and stop rather than working around it (CLAUDE.md §7.7).
* **Before and after means the same months, the same suite, the same way.** A comparison against a
  differently-scoped run is not a comparison.
* Change nothing on the kiosk: no deploys, no model swaps, no restarts.

## Report

Return this and nothing else:

```
SCOPE:    <the change, the months, the suite that ran>
BEFORE:   <per-field numbers by month>
AFTER:    <per-field numbers by month, or "not run" and why>
MOVED:    <the fields that changed, with the size of the change>
DROPPED:  <drop counts by reason, if the suite reports them>
VERDICT:  <does the change hold up, and what would falsify this>
```
