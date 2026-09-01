# Punch list #44b — Kiosk crashed on a live dispatch — stale chunk after a frontend deploy

| | |
|:--|:--|
| **Status** | FIXED 2026-08-31 |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3979 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 44. Kiosk crashed on a live dispatch — stale chunk after a frontend deploy
> **Status**: ✅ **Fixed 2026-08-31, after it recurred on a second live call.**
> The deferred plan was implemented; operator discipline is no longer the mitigation.

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

## It recurred, on an overdose call — 2026-08-31

`DISP-2026-F7D588`, Medical Aid — Overdose, 1140 Pinetree Way, M1, **18:29:04**. The kiosk
showed the diagnostic card instead of the map:

```
TypeError: error loading dynamically imported module:
http://100.95.146.94/assets/KioskView-CZ0IDQ3H.js
```

Identical mechanism, second live call lost to it. Confirmed on the kiosk rather than
inferred:

| Checked | Result |
|:--|:--|
| The dispatch record | **Complete.** Address, units, coordinates and transcript all correct in `public.dispatches` |
| `KioskView-CZ0IDQ3H.js` on disk | **Absent.** Current chunk is `KioskView-Cn-2kwfP.js` |
| `dist/` mtime | 18:34:52 — a rebuild, but *five minutes after* the failure, so an earlier rebuild had already removed the chunk the tab held |
| nginx cache headers | **None set** (`/etc/nginx/sites-enabled`, `try_files` only), so a reload revalidates `index.html` and genuinely recovers |

**The interim mitigation was the defect.** "Remember to hard-reload after every deploy" is
not a mechanism, and it failed the same way twice. The operator's own reading afterwards:
*"maybe it wasn't flagged clear enough for me to reload."* The card said
`APPLICATION DIAGNOSTIC ERROR` over a `TypeError` — accurate, and useless to someone who
needs to know that one keypress fixes it.

## The fix — three layers

1. **`KioskView` is now imported eagerly** (`App.jsx`). This removes the failure class
   rather than recovering from it. The kiosk sits in STANDBY on `MapBoard`, so the
   `KioskView` chunk was fetched *for the first time when a call arrived* — a rebuild armed
   it silently and it fired only during an emergency. Measured cost of loading it up front:
   index 17 KB → 99 KB (it also pulls `EVORoutingEngine`, itself a deferred chunk), eager
   payload 1,304 KB → 1,386 KB, **+6.3%**, against 1.29 MB of vendor chunks already eager,
   over a LAN.
2. **`vite:preloadError` auto-recovery** (`main.jsx`), one shot, guarded by a
   `sessionStorage` marker that is handed back once a boot proves healthy. Covers the
   remaining lazy chunks and a stale `index.html`.
3. **The error card now names the fault and the remedy** — "Display Out Of Date — Reload
   Required", the Ctrl+Shift+R keys shown explicitly, an oversized reload button, and a line
   confirming dispatches are still being received and recorded. The raw stack is suppressed
   on this path. The reload button clears the marker, or the one-shot guard would refuse the
   operator's own retry.

## Verified by execution, not inspection

Run in a browser against the built bundle, 2026-08-31:

| Test | Result |
|:--|:--|
| First `vite:preloadError` | Event cancelled, marker set, `performance.navigation.type` → `reload`. Recovered |
| Second failure inside the window | Guard refused. **No reload loop** |
| Healthy boot, document **hidden** | Marker cleared, budget handed back |
| Detector vs both real incident strings | Matches; also Chrome/Safari wordings; rejects unrelated `TypeError`s |
| `KioskView-*.js` / `EVORoutingEngine-*.js` in `dist` | **Gone** — folded into `index` |

**Running it caught a defect in the fix itself.** The budget hand-back was first written
with `requestAnimationFrame`, which does not fire while the document is hidden — measured,
`document.hidden` true and no callback within 700 ms. On a kiosk with a blanked display the
marker would never clear and the failsafe would silently become single-use for the life of
the tab, dropping the *next* deploy's call onto the error card exactly as before. Replaced
with a timer and recorded in
[`dependency-behaviour.md`](../standards/dependency-behaviour.md).

---

## The reload was only half the fix — operator follow-up, 2026-08-31

> *"If a call comes in, the kiosk crashes, and we reload it, the dispatch doesn't
> appear. It's gone forever."*

Correct, and it applied to **every** reload during an incident, not just this one:
a browser restart, a power cycle, a crash. `activeCall` started `null` and was only
ever populated by an MQTT broadcast, and neither publisher sets the **retain** flag
(`api/mqtt.py` and `mqtt_broker.py` both publish `qos=1`, no retain). A freshly
loaded page therefore had no way to hear an announcement already made — it would
have sat on a working map with no call on it until the *next* dispatch.

**The dispatch was never lost.** `public.dispatches` is the system of record, so the
kiosk now asks the database what is still live on mount rather than waiting for a
broadcast that has already been and gone (CLAUDE.md §6.2).

| Decision | Why |
|:--|:--|
| Restore with the call's **real age** | A fresh 5:00 would silently extend the display window, and an elapsed clock restarted at 00:00 would misreport how long the crew has been on the call — a number that reads as real and is not (§6.1) |
| Bounded by the same 300 s window | A kiosk booted hours later shows nothing rather than resurrecting an old incident |
| Dismissals persisted to `localStorage` | Otherwise a call the operator had deliberately cleared comes straight back on the next reload |
| Storage unavailable → may re-show once | The safe direction to fail: a call shown twice beats a call lost |
| Live MQTT always wins over the restored copy | A broadcast is fresher than anything just read |
| Fetch five records, not one | Two calls inside one window is uncommon at ~11 dispatches a day but real; restoring only the newest would drop the one the crew is on |

### Verified against real records, by moving the clock

No dispatch was synthesised (§6.5) — the five real records from the running API were
selected against a varied observation time:

| Case | Result |
|:--|:--|
| Reload 20 s after the overdose | Restores, age 20 s, **280 s remaining** |
| Reload 4 m 59 s after | Restores, **1 s remaining** |
| Reload 5 m 01 s after | Nothing restored |
| Reload hours later | Nothing restored |
| Operator had dismissed it | Nothing restored |
| Two calls inside one window | Older one becomes active |
| Clock skew, record dated in the future | Rejected, no negative age |

Confirmed on the kiosk after deploy: `GET /api/dispatches?limit=5` fires on boot
(`http://100.95.146.94:8000/api/dispatches?limit=5` in the resource timing), and
correctly restores nothing while the newest dispatch is outside the window.
