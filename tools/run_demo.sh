#!/usr/bin/env bash
# The whole demo on this computer, in one command: PlantCraft's local demo, BatchLens inside
# it, the five synthetic batches, and the synthetic bioreactor imported into PlantCraft.
#
#   tools/run_demo.sh            start everything, then keep running until Ctrl+C
#   tools/run_demo.sh --reset    the same, with a fresh PlantCraft workspace
#
# Needs: this repository set up (make ci has run), a PlantCraft checkout beside it
# (../PlantCraft, or PLANTCRAFT_DIR) installed into the same Python environment
# (docs/demo.md), and curl. Everything is local and synthetic; nothing leaves this computer.
#
# The plant map is imported through PlantCraft's own interface routes (/api/session,
# /api/map/apply), as its pages do. They are not part of API v1 and were tried on PlantCraft
# 0.6.0 only. The app itself never calls them.
set -euo pipefail

cd "$(dirname "$0")/.."
PLANTCRAFT_DIR=${PLANTCRAFT_DIR:-../PlantCraft}
PLANTCRAFT_URL=http://127.0.0.1:8060
APP_URL=http://127.0.0.1:9100/batchlens/
DATA_DIR="$PLANTCRAFT_DIR/var/batchlens"          # where `make dev` puts the app's database
PLANT_DIR="$PLANTCRAFT_DIR/var/batchlens-plant"   # the files PlantCraft imports
FLAGS=""
[ "${1:-}" = "--reset" ] && FLAGS="--reset"

command -v batchlens >/dev/null || { echo "batchlens is not on PATH: activate the environment (docs/demo.md)."; exit 1; }
[ -f "$PLANTCRAFT_DIR/run_opcua_demo.py" ] || { echo "No PlantCraft checkout at $PLANTCRAFT_DIR (set PLANTCRAFT_DIR)."; exit 1; }

# PlantCraft reads CSV files on the wall clock of its scenario's source time zone.
ZONE=$(python - "$PLANTCRAFT_DIR/scenarios/opcua_demo.json" <<'PY'
import json, sys
print(json.load(open(sys.argv[1]))["source"].get("timezone", "America/Sao_Paulo"))
PY
)

# PlantCraft forwards an assistant tool call to the app at the address it has for it inside the
# suite's network. In a packaged stack that is known; here it has to be told.
export PLANTCRAFT_OPS_URLS="${PLANTCRAFT_OPS_URLS:+$PLANTCRAFT_OPS_URLS,}batchlens=${APP_URL%/}"

echo "Starting PlantCraft and BatchLens (the first start builds interfaces and can take minutes)..."
make dev DEV_FLAGS="$FLAGS" > /tmp/batchlens-demo.log 2>&1 &
SERVERS=$!
trap 'kill $SERVERS 2>/dev/null; wait $SERVERS 2>/dev/null; echo; echo "Stopped."' EXIT

for _ in $(seq 1 180); do
  if curl -fs -o /dev/null "$PLANTCRAFT_URL/" && curl -fs -o /dev/null "${APP_URL%batchlens/}healthz"; then break; fi
  kill -0 $SERVERS 2>/dev/null || { echo "The servers stopped; see /tmp/batchlens-demo.log"; exit 1; }
  sleep 2
done
curl -fs -o /dev/null "$PLANTCRAFT_URL/" || { echo "PlantCraft did not answer; see /tmp/batchlens-demo.log"; exit 1; }

echo "Loading the five synthetic batches..."
# With --reset the batches are loaded again as generated, undoing corrections made in the app.
BATCHLENS_DATA_DIR="$DATA_DIR" batchlens seed-demo $FLAGS 2>/dev/null | tail -1

echo "Writing the synthetic plant for time zone $ZONE and importing it into PlantCraft..."
batchlens demo-plant --out "$PLANT_DIR" --time-zone "$ZONE" 2>/dev/null | tail -1
COOKIES=$(mktemp)
curl -fs -c "$COOKIES" -o /dev/null "$PLANTCRAFT_URL/api/session"
curl -fs -b "$COOKIES" -X POST --data-binary "@$PLANT_DIR/plant-map.json" \
  "$PLANTCRAFT_URL/api/map/apply?filename=plant-map.json" \
  | python -c 'import json,sys; r=json.load(sys.stdin); print("imported:", r["applied"], {s["name"]: [s["create"], s["update"], s["unchanged"]] for s in r["sections"]}, "issues:", r["issues"])'
rm -f "$COOKIES"

cat <<DONE

Ready. Everything shown is synthetic.
  PlantCraft:  $PLANTCRAFT_URL          (open BatchLens from the app switcher, top left)
  BatchLens:   $APP_URL   (after opening PlantCraft once, which signs you in)
  A tour:      docs/demo.md, "A five-minute tour"
Ctrl+C stops everything.
DONE
wait $SERVERS
