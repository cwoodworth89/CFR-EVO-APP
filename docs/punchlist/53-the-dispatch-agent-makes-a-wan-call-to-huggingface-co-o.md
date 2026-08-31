# Punch list #53 — The dispatch agent makes a WAN call to huggingface.co on every start

| | |
|:--|:--|
| **Status** | OPEN |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L3938 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 53. The dispatch agent makes a WAN call to huggingface.co on every start
> **Status**: ⚠️ **Open — not reproduced under WAN failure.** Observed 2026-08-29 in
> `cfr-agent` startup logs while deploying.

```
Aug 29 20:26:12 cfr-mapping-tcfh cfr-agent[3321015]: INFO - Loading local faster-whisper
  model 'base' (device=cpu, compute_type=int8)...
Aug 29 20:26:12 cfr-mapping-tcfh cfr-agent[3321015]: INFO - HTTP Request: GET
  https://huggingface.co/api/models/Systran/faster-whisper-base/revision/main "HTTP/1.1 200 OK"
```

CLAUDE.md §1 requires the entire system — STT included — to function with no internet. The kiosk
currently has WAN, so this returns 200 and nothing is visibly wrong. The question is what happens
when it does not.

`faster-whisper` resolves the model through `huggingface_hub`, which checks the repo for a newer
revision before falling back to the local cache. Two things need establishing, in order:

1. **Does it fail fast or hang?** `huggingface_hub` normally catches connection errors and falls
   back to cache, but the timeout is not short. If it stalls, **agent startup stalls with it**,
   and the audio listener is down for that whole window — the same class of outage as a stalled
   worker (#28), reached a different way.
2. **Does it fall back at all** if the cache is present but the revision check fails in some
   other way (DNS resolving to a captive portal, TLS interception, an HTTP 5xx rather than a
   connection refusal)?

**Do not "fix" this before measuring it.** The obvious change is `local_files_only=True`, or the
`HF_HUB_OFFLINE=1` environment variable, and it is probably right — but it also pins the kiosk to
whatever is in the cache, so the model can never be updated without a deliberate step. That is
arguably the correct trade for this system; it should still be a decision rather than a
side effect.

**How to test it honestly:** block egress to `huggingface.co` on the kiosk (a null route or an
`/etc/hosts` entry), restart `cfr-agent`, and time how long it takes to reach *"Background
Dispatch Worker process initialized and ready."* Compare against the ~2 s it takes today. That
is a real measurement of the offline guarantee rather than an assumption about it, and it is the
only way to know whether this is a latent outage or a harmless log line.


---
