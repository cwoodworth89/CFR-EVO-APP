# Punch list #80 — An unresolved talk group looks exactly like a dispatch with no talk group

| | |
|:--|:--|
| **Status** | OPEN. Measured, not built — the kiosk wording is the operator's to set. |
| **Severity** | 🔴 crew-visible |
| **Area** | 🎙️ Parser / talk group · 🖥️ Kiosk HUD · 🏷️ Review flags |
| **Ruling** | Operator, 2026-09-11: *"Well, not NO talk group. Unknown talk group. No talk group is a valid form of dispatch."* |
| **Origin** | Raised by the operator while reviewing #79, on the wording of the state the matcher returns. |

[← punch list index](../debug_and_qa_punchlist.md)

---

## The two facts the system collapses into one

| | What happened | Today |
|:--|:--|:--|
| **No talk group** | The dispatcher announced none. **A valid dispatch.** | `radio_channel = NULL` |
| **Unknown talk group** | One was announced and the pipeline could not read it. **A gap.** | `radio_channel = NULL` |

Both raise the same flag, `NO_TALK_GROUP` — whose label, *"No talk group announced or
transcribed"*, states the conflation outright — and
[`ActiveAlertBanner.jsx:283`](../../frontend/src/components/hud/ActiveAlertBanner.jsx:283)
renders the field as `{talkGroup && (…)}`, so **the kiosk hides it in both cases**.

## Why this is crew-visible

On a call where a channel *was* announced and the pipeline lost it, the crew sees a HUD with
no talk group on it — which is a normal, valid sight. Nothing tells them a channel exists and
they do not have it. They stay on their default net, and the call is on another.

This is §6.1 in its less obvious direction. The rule is usually read as *do not print a number
you do not have*; the same rule says **do not let a gap wear the appearance of a valid state.**
An unknown rendered as a legitimate "no channel" is a plausible wrong answer a crew cannot see
through, exactly like an invented one.

## Measured, 2026-09-11 (624 stored transcripts)

| | calls |
|:--|--:|
| Resolved to a channel | 576 |
| **No talk-group clause in the transcript at all** — none announced, or the whole clause lost | **39** |
| **Talk-group clause present, channel unresolved** | **12** |

The 12 will grow: #79's ruling sends a fragment degraded to bare `combined response` to
unresolved, which is 10 further calls in the corpus.

## The distinction is already available, unused

[`announcement.py:132`](../../backend/cfr_dispatch/parser/announcement.py:132) already knows
which case it is and throws the knowledge away:

* `talk_group_match` is `None` → the phrase was never spoken → **no talk group**
* `talk_group_match` is set but `match_radio_channel` returns `None` → **unknown talk group**

Both currently leave `radio_channel = None`. Nothing else needs to be inferred or measured;
the parser only has to carry the boolean it already computed.

## Shape of the fix

1. `DispatchData` carries whether a talk-group clause was announced.
2. `review_flags.py` splits `NO_TALK_GROUP` into two: one for "none announced" (arguably not a
   review flag at all, since it is a valid dispatch — **operator to rule**) and
   `UNKNOWN_TALK_GROUP` for announced-but-unread.
3. The kiosk renders the unknown case explicitly instead of hiding the field. **Wording is the
   operator's to set** — it is what a crew reads at 03:00 and §7.2 says a domain model is not
   improvised.

## Not to be done here

Do **not** close this by writing a sentinel string into `radio_channel` (`"UNKNOWN"`,
`"NONE"`). That is a placeholder that reads as real data — §6.1 names the pattern directly.
The state belongs beside the value, not inside it.
