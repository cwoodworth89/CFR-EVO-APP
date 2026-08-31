# Punch list #34b — Live overdose call still showed the green ROUTINE (Code 1) badge

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | crew-visible |
| **Area** | 🖥️ Live Operation Batch, 2026-08-23 |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L2068 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 34. Live overdose call still showed the green ROUTINE (Code 1) badge
> **Status**: ⚠️ **Open — duplicate symptom of #31, now confirmed in live operation.**

An overdose dispatch (an *emergency* response) rendered with the green border and the
`ROUTINE (CODE 1)` badge. This is exactly the failure #31 predicts: `response_type` never
reaches the kiosk, `isEmergency` is always false, so every call renders routine. **No separate
fix — #31 and #30 cover it.** Logged because it is the first live confirmation rather than a
database inference.

**Second, separate defect in the same sighting**: the kiosk announced an update that did not
exist. `triggerUpdateFlash` (`frontend/src/hooks/useKioskQueue.js:41-48`) sets
`isRecentlyUpdated` for 4 s, which renders the `⚡ UPDATED` badge
(`ActiveAlertBanner.jsx:46`). Nothing in that path compares the new payload to the old one, so
the badge fires on **any** re-delivery — and MQTT QoS 1 is at-least-once, so duplicate
delivery of an unchanged call is the contract, not an anomaly (see the kiosk idempotency note
in the handoff). The operator is told data changed when it did not.

**Fix direction**: fire the flash only when a field the operator can see actually differs —
address, incident, units, grid, talkgroup, coordinates — rather than on receipt. Worth
deciding *what counts as a change* before implementing, since "updated" is an operational
claim (§6.1: a badge asserting something that did not happen is fabricated state).

---

---

## 34b (update). Data side resolved; needs one operator look

> **Status**: ⚠️ **Open — narrowed 2026-08-30. Backend confirmed fixed; the render is not.**

This was recorded as a duplicate symptom of **#31**, and #31 is now closed: `response_type`
persists and reaches the payload, verified in the database with a clean dated cutover.

**What is not verified is the badge itself.** Whether a live emergency call now renders as
something other than green ROUTINE needs one look at the kiosk during a real emergency
dispatch — that cannot be established from here, and inferring it from the data would be
exactly the reported-vs-confirmed conflation §6.6 warns about.

**Closes on**: one operator screenshot of a live `emergency` call showing the badge.
