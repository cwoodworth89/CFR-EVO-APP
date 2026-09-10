#!/usr/bin/env bash
# Build an OSRM graph on the kiosk from the shared extract with a named profile, beside the
# graph being served, and record what built it.
#
#   backend/scripts/build_osrm_graph.sh backend/osrm/profiles/apparatus.lua apparatus
#
# Writes backend/data/osrm/<name>.osrm.* from backend/data/osrm/vancouver.osm.pbf, and
# backend/data/osrm/<name>.build.txt: image digest, profile md5, extract, command, time. The
# graph that was serving on 2026-09-08 had none of that recorded (docs/standards/osrm/README.md).
#
# Minutes of every core. Run tools/kiosk_capture_state.sh first, never during a tile
# generation, and say so (docs/briefs/osrm_routing_agent.md, "The kiosk, shared with another
# agent"). It does not touch the served graph or the osrm container. To try the result on
# port 5001 without touching port 5000:
#
#   docker run -d --name cfr_osrm_trial -p 5001:5000 -v "$PWD/backend/data/osrm:/data" \
#       <image> osrm-routed --algorithm mld /data/<name>.osrm
#
# CFR_ROOT overrides the repository root (for a copy of this script run from elsewhere);
# OSRM_IMAGE overrides the image.
set -euo pipefail
PROFILE=${1:?usage: build_osrm_graph.sh <profile.lua> <name>}
NAME=${2:?usage: build_osrm_graph.sh <profile.lua> <name>}
ROOT=${CFR_ROOT:-$(cd "$(dirname "$0")/../.." && pwd)}
DATA="$ROOT/backend/data/osrm"
# The image that built the graph served since 2026-08-14, by digest (docs/standards/osrm/README.md).
# :latest on the kiosk resolves to it today; the digest keeps the profile text and the binary
# that reads it in step.
IMAGE=${OSRM_IMAGE:-ghcr.io/project-osrm/osrm-backend@sha256:3ac496ff8fd7e1af53846179d73d06a97f719c8ad2217d008ed868942398665c}
PBF="$DATA/vancouver.osm.pbf"
[ -f "$PBF" ] || { echo "no extract at $PBF" >&2; exit 1; }
[ -f "$PROFILE" ] || { echo "no profile at $PROFILE" >&2; exit 1; }
PROFILE_ABS=$(cd "$(dirname "$PROFILE")" && pwd)/$(basename "$PROFILE")
PROFILE_NAME=$(basename "$PROFILE")

# osrm-extract names its output after its input, so the extract is hard-linked under the
# graph's name: same bytes, no copy, and vancouver.osrm.* is never written to.
ln -f "$PBF" "$DATA/$NAME.osm.pbf"

# The profile is mounted into /opt so that its require('lib/...') resolves to the image's own
# lib/, the text vendored at docs/standards/osrm/lib/.
run() { docker run --rm -v "$DATA:/data" -v "$PROFILE_ABS:/opt/$PROFILE_NAME:ro" "$IMAGE" "$@"; }

START=$(date -Is)
run osrm-extract -p "/opt/$PROFILE_NAME" "/data/$NAME.osm.pbf"
run osrm-partition "/data/$NAME.osrm"
run osrm-customize "/data/$NAME.osrm"
{
  echo "graph: $NAME.osrm"
  echo "built: $START .. $(date -Is) on $(hostname)"
  echo "image: $IMAGE"
  echo "profile: $PROFILE_ABS md5 $(md5sum "$PROFILE_ABS" | cut -d' ' -f1)"
  echo "extract: $PBF $(stat -c '%s bytes, modified %y' "$PBF")"
  echo "command: osrm-extract -p /opt/$PROFILE_NAME /data/$NAME.osm.pbf; osrm-partition /data/$NAME.osrm; osrm-customize /data/$NAME.osrm"
} > "$DATA/$NAME.build.txt"
cat "$DATA/$NAME.build.txt"
