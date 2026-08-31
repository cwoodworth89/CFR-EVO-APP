# Punch list #44b — Kiosk crashed on a live dispatch — stale chunk after a frontend deploy

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3979 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 44. Kiosk crashed on a live dispatch — stale chunk after a frontend deploy
> **Status**: ⚠️ **Open — cause confirmed, fix deferred to
> [`PROJECT_IDEAS.md` #10](./PROJECT_IDEAS.md).** Interim mitigation is operator
> discipline: hard-reload the kiosk tab after every frontend deploy.

A real call (`DISP-2026-AAFDB8`, Alarm Activated - High Risk, 1123 Westwood St) arrived at
20:32 and the kiosk showed
`TypeError: error loading dynamically imported module: .../KioskView-B0Wnod_F.js`
instead of the map.

**Everything except the display worked.** Four things were suspected; three were exonerated
by measurement rather than assumption:

| Suspect | Verdict |
|:--|:--|
| The newly-enforced PA/hum filter | **Not at fault.** Zero `REJECTED` lines; the call matched Engine Tone at 100% |
| The dispatch pipeline | **Flawless.** Phase 1 TTA 5.14 s, address 100%, MQTT INSERT + UPDATE, Phase 2 verified |
| ntfy | **Published fine.** `messages_published` 410 → 411; message on the topic with correct address, units and grid |
| The frontend build | **This was it** |

**ntfy's apparent failure was delivery, not publication.** `subscribers=0` at the moment of
the call — the operator's phone had dropped off Tailscale. Reconnecting delivered it. No code
defect, and worth remembering as a diagnosis: a published-but-undelivered notification looks
identical to a broken notifier from the operator's side.

**The actual cause.** `npm run build` deletes the previous content-hashed chunks. The kiosk
tab still held the pre-rebuild `index.html`, so it requested `KioskView-B0Wnod_F.js`, which
the 20:07 rebuild had removed (`KioskView-Bu8ZsJK9.js` is current). `KioskView` is
**lazy-loaded**, so the stale reference sits invisible until a call needs it — a rebuild
silently arms this in every open tab and it detonates on the next real dispatch.

**This was my error.** I rebuilt the frontend, said a hard reload was needed, and did not
confirm it had happened before the kiosk sat through a live call in that state. A deploy is
not finished when the build succeeds; it is finished when the tab has been reloaded.


---
