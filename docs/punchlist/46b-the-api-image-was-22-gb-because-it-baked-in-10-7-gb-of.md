# Punch list #46b — The API image was 22 GB because it baked in 10.7 GB of bind-mounted data

| | |
|:--|:--|
| **Status** | CLOSED |
| **Severity** | operational |
| **Area** | 🧷 Parcel Import Integrity |
| **Blocks** | 1 |
| **Origin** | `debug_and_qa_punchlist.md` L4361 |

[← punch list index](../debug_and_qa_punchlist.md)

---

## 46. The API image was 22 GB because it baked in 10.7 GB of bind-mounted data
> **Status**: ✅ **Closed 2026-08-30.** Image 22.2 GB → **1.27 GB**; 223 GB of disk reclaimed.

Found because an API rebuild stalled for ~10 minutes on `exporting layers` during the #45
deploy, holding open the migration window above.

`backend/api/Dockerfile` does `COPY backend /app/backend`, and there was **no `.dockerignore`**:

| Path | Size | Needed in the image? |
|:--|--:|:--|
| `backend/data` | 9.9 GB | **No** — bind-mounted |
| `backend/audio_files` | 766 MB | **No** — bind-mounted |
| `backend/models` | 73 MB | No |
| API code (`cfr_dispatch` + `api` + `scripts`) | **~1.6 MB** | Yes |

`docker-compose.yml` already bind-mounts `./backend/data` and
`./backend/audio_files/recordings`, so **the baked-in copy was shadowed the instant the
container started and never read.** It also made the image quietly misleading: it held a frozen
snapshot of the tiles and recordings from build time, which would be served if a mount ever
went missing. Stale data served silently is worse than absent data failing loudly.

**The build cache was the larger hoard.** `docker image prune -af` reclaimed only 1.9 GB;
`docker system df -v` showed **221.9 GB of build cache** across 143 unused entries, each having
cached an 11 GB context copy. `image prune` does not touch it — that needs `docker builder
prune`.

| | Before | After |
|:--|--:|--:|
| API image | 22.2 GB | **1.27 GB** |
| Build cache | 221.9 GB | **0** |
| Disk free | 172 GB | **395 GB** |

Verified on the rebuilt image rather than assumed: API healthy at 513 dispatches, audio serving
1.78 MB **from the bind mount**, and `/app/backend/data` reporting 9.9 GB inside the container —
the mount, not the image.

`.dockerignore` also excludes tests, logs, docs, frontend sources and `.env` files. A secret
committed to an image layer survives deletion of the file.


---
