---
name: tile-health
description: Check the kiosk's tile server end to end — which services cfr_tiles publishes, whether each answers with a real tile rather than a blank, and whether an archive was left in WAL mode. Read-only, and it runs in the calling chat: three probes and a listing are not worth a sub-agent.
when_to_use: Someone asks whether the map tiles are healthy, or a tile archive was just rebuilt, swapped, deleted, or cfr_tiles was restarted.
disallowed-tools: Edit, Write, NotebookEdit
---

Check the kiosk's tile server and answer in the block at the end. **Read-only**: never restart,
rebuild or delete anything. A restart is the operator's, and `.claude/hooks/kiosk_restart_guard.py`
blocks it anyway. Background: the `mbtiles-tile-server` skill.

Everything below runs on the kiosk over `ssh -o BatchMode=yes tcfire@100.95.146.94`.

## 1. What is published

```bash
curl -s http://localhost:8081/services
```

Expect exactly `cadastral`, `ortho` and `street_vector`. A missing service means `cfr_tiles` could
not open that archive; an extra one means a retired archive is still in the directory.

## 2. Does each service answer with a real tile

**A `200` is not proof.** A raster tile the archive does not hold answers `200 image/png` with a
116-byte blank, even from `ortho`, which stores JPEG. Check the content type and the size. These
are the tiles under Hall 1:

```bash
for p in cadastral/tiles/16/10414/22425.png ortho/tiles/18/41658/89702.jpg street_vector/tiles/14/2603/5606.pbf; do
  curl -s -o /dev/null -w "%{http_code} %{content_type} %{size_download}  $p\n" "http://localhost:8081/services/$p"
done
```

| Probe | Healthy answer, measured 2026-09-15 |
|:--|:--|
| cadastral z16 | `200 image/png 21489` |
| ortho z18 | `200 image/jpeg 16983` |
| street_vector z14 | `200 application/x-protobuf 81889` |

A 116-byte `image/png` from any of them means that archive holds no tile there. A different size
with the right content type is normal after a rebuild: report the number, do not call it a fault.

## 3. The archives on disk

```bash
ls -la /home/tcfire/CFR-EVO-APP/backend/data/tiles/
```

Report each `.mbtiles` with its size and date. A `-wal` or `-shm` file beside an archive is a
finding on its own: the read-only volume cannot open a WAL-mode archive, and the fix is in the
`mbtiles-tile-server` skill, §2.

## Report

Return this block and nothing else:

```
SERVICES: <the three, or what differed>
PROBES:   cadastral <code type bytes> | ortho <code type bytes> | street_vector <code type bytes>
ARCHIVES: <name size date>, ...; WAL leftovers: none | <files>
VERDICT:  healthy | <what is wrong, and the exact command the operator should run>
```
