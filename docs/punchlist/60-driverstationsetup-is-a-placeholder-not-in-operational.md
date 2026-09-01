# Punch list #60 — `DriverStationSetup` is a placeholder, not in operational use

| | |
|:--|:--|
| **Status** | DEFERRED |
| **Severity** | hygiene |
| **Area** | 🎨 Kiosk & Review Panel UI/UX |
| **Blocks** | 1 |
| **Origin** | Operator ruling 2026-08-31 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 60. Placeholder screen, deferred pending redesign

> **Status**: 🕓 **Deferred by the operator 2026-08-31.** Annotated in place, deliberately not
> fixed — the screen needs substantial work and any detail corrected now would be undone by
> the redesign.

**Nobody is onboarded through it.** No driver or officer uses this screen and nothing depends
on it. It is wired into `MapBoard` on `appMode === "DRIVER_SETUP"` and renders if opened, but
that is a code fact rather than a workflow. The defect below is therefore **latent, not live**.

#### The known defect, recorded so the redesign does not inherit it

`frontend/src/components/DriverStationSetup.jsx` hardcodes the ntfy topic as
`cfr-dispatches`. Nothing publishes there. Both the host agent (`backend/.env`) and the API
container (`docker-compose.yml`) publish to `chief-master` — confirmed by reading both on the
kiosk. The screen displays the wrong topic name three times and generates a QR code and a
deep link pointing at it.

#### How it drifted, which matters more than the value

| | | |
|:--|:--|:--|
| 2026-08-15 | `6d7866e` | Removed ntfy.sh and the salted monthly rotation; set the topic to `cfr-dispatches` across the backend, the config and this component. |
| 2026-08-21 | `e81964f` | *"align dispatch topic with the documented `chief-master` master topic"* — updated the backend and config, **and missed this file**. |

A rename applied to three places out of four, with nothing failing on the fourth. Ten days of
divergence that only surfaced because someone went looking at the ntfy topics for an unrelated
reason.

#### When it is rebuilt

**Do not fix by editing the literal.** The topic belongs in configuration, read once, so the
next rename cannot half-apply. Separate hardcoded copies are the condition that produced
this: `ntfy_broker.py`'s env default was corrected to `chief-master` on 2026-08-31, leaving
the literal in `DriverStationSetup.jsx` as the only stale one.

Related: the ntfy topic architecture is now recorded accurately in
[`ntfy_server_access_and_qr_spec.md`](../ntfy_server_access_and_qr_spec.md) §2, including the
removal of the salted scheme that never existed in code.
