---
name: local-stack-orchestrator
description: Operational runbook for managing the containerized Docker Compose stack (PostgreSQL 16, Mosquitto MQTT, Ntfy, FastAPI Gateway, and MBTiles Tile Server).
---

# Local Stack Orchestration

This skill covers managing, verifying, and troubleshooting the containerized station backend.

---

## 1. Container Stack Management

Start the local stack in background daemon mode:
```powershell
docker compose up -d
```

Inspect running container health:
```powershell
docker compose ps
```

Tail logs from a specific container:
```powershell
# API Gateway logs
docker compose logs -f api

# Mosquitto MQTT broker logs
docker compose logs -f mosquitto

# PostgreSQL logs
docker compose logs -f postgres

# MBTiles Offline Tile Server logs
docker compose logs -f cfr_tiles
```

---

## 2. Port & Endpoint Checklist

Verify that all local ports are bound and responding:
* **`5432`**: PostgreSQL 16 DB (`POSTGRES_DB=cfr_dispatch`)
* **`8000`**: FastAPI REST API Gateway (`http://localhost:8000/api/dispatches`)
* **`1883`**: Mosquitto Native MQTT TCP Port
* **`9001`**: Mosquitto MQTT over WebSockets Port (for React Kiosks)
* **`8080`**: Ntfy Push Notification Server (`http://localhost:8080`)
* **`8081`**: MBTiles Tile Server (`http://localhost:8081/services`) — serves `satellite`, `street`, `street_nolabels`, `cadastral`

---

## 3. Database Schema Initialization

Verify that `backend/api/init_db.sql` executed correctly:
```powershell
docker compose exec postgres psql -U cfr_user -d cfr_dispatch -c "\dt"
```
Ensure table `dispatches` and `evaluation_history` exist and index `idx_dispatches_target_gin` is active.

---

## 4. Tile Server (cfr_tiles) Management

For in-depth tile generation, SQLite WAL mode read-only permissions, and curl testing rules, consult [`.claude/skills/mbtiles-tile-server/SKILL.md`](file:///c:/Users/Curtis/Nextcloud/Documents/Projects/Coding/CFR-EVO-APP/.claude/skills/mbtiles-tile-server/SKILL.md).

Quick service list check:
```powershell
curl -s http://localhost:8081/services
```
Restart tile container after adding or modifying archives in `backend/data/tiles/`:
```powershell
docker restart cfr_tiles
```

