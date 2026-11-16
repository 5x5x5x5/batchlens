#!/usr/bin/env bash
# The whole demo on this computer, in one command: PlantCraft's local demo, the suite's modules
# that are installed, BatchLens, the synthetic batches, and the synthetic bioreactor
# imported into PlantCraft. Everything is reached at one address, through tools/gateway.py.
#
#   tools/run_demo.sh            start everything, then keep running until Ctrl+C
#   tools/run_demo.sh --reset    the same, with a fresh PlantCraft workspace
#
# Needs: this repository set up (make ci has run), a PlantCraft checkout beside it
# (../PlantCraft, or PLANTCRAFT_DIR) installed into the same Python environment
# (docs/demo.md), and curl. The suite's modules are optional: each one found in
# PLANTCRAFT_SUITE_BIN (default ~/.venvs/plantcraft-suite/bin) is started (docs/demo.md).
# Everything is local and synthetic; nothing leaves this computer.
#
# To put the demo where others can reach it, turn PlantCraft's sign-in on first (without it
# every visitor is an administrator): PLANTCRAFT_BASIC_AUTH_ENABLED=true,
# PLANTCRAFT_BASIC_AUTH_USERNAME and PLANTCRAFT_BASIC_AUTH_PASSWORD_FILE name the administrator.
# BATCHLENS_DEMO_GUEST and BATCHLENS_DEMO_GUEST_PASSWORD_FILE then add a read-only guest.
#
# The plant map is imported through PlantCraft's own interface routes (/api/session,
# /api/map/apply), as its pages do. They are not part of API v1 and were tried on PlantCraft
# 0.6.0 only. The app itself never calls them.
set -euo pipefail

cd "$(dirname "$0")/.."
REPO=$PWD
PLANTCRAFT_DIR=$(cd "${PLANTCRAFT_DIR:-../PlantCraft}" 2>/dev/null && pwd) || { echo "No PlantCraft checkout (set PLANTCRAFT_DIR)."; exit 1; }
SUITE_BIN=${PLANTCRAFT_SUITE_BIN:-$HOME/.venvs/plantcraft-suite/bin}
GATEWAY_PORT=${BATCHLENS_DEMO_PORT:-8088}
PLANTCRAFT_URL=http://127.0.0.1:8060          # PlantCraft itself, as the apps and this script reach it
DEMO_URL=http://127.0.0.1:$GATEWAY_PORT       # the one address for the browser
DATA_DIR="$PLANTCRAFT_DIR/var/batchlens"          # the app's database
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

# PlantCraft's own demo scenario is a simulated refinery with 50 control loops. The demo runs
# a copy of it under the mAb plant's name with one of those loops, shown as a utility, so the
# plant PlantCraft shows is the one BatchLens is about. The Simulator still runs: it is the
# scenario's source, and PlantCraft needs one tag from it.
SCENARIO="$PLANTCRAFT_DIR/var/batchlens-scenario.json"
mkdir -p "$PLANTCRAFT_DIR/var"
python - "$PLANTCRAFT_DIR/scenarios/opcua_demo.json" "$SCENARIO" <<'PY'
import json, sys
scenario = json.load(open(sys.argv[1]))
scenario["display_name"] = "mAb drug substance plant"
scenario["description"] = "A synthetic mAb drug substance plant: one bioreactor and its purification train."
# PlantCraft needs one tag from its source: one of the Simulator's loops stays, as a utility.
keep = scenario["loops"][0]
keep.update(name="Purified water flow", area="Utilities", unit="U-UTIL", service="A utility loop from PlantCraft's Simulator")
keep["metadata"] = {"loop_type": keep["metadata"]["loop_type"]}
scenario["loops"] = [keep]
json.dump(scenario, open(sys.argv[2], "w"), indent=2)
PY
LAUNCH='import pathlib, sys, run_opcua_demo as demo; demo.SCENARIO = pathlib.Path(sys.argv[1])'

# Every app as id:prefix:port:command. View's own port, 8080, is left alone: other things on
# a workstation use it.
APPS="batchlens:batchlens:9100:$(command -v batchlens)"
for entry in histcraft:hist:8100 linkcraft:link:8140 dashcraft:dash:8085 alarmcraft:alarm:8110 modelcraft:model:8130 doccraft:doc:8150; do
  [ -x "$SUITE_BIN/${entry%%:*}" ] && APPS="$APPS $entry:$SUITE_BIN/${entry%%:*}"
done
LIST=""; OPS=""; ROUTES=""
for app in $APPS; do
  IFS=: read -r id prefix port _ <<<"$app"
  # PlantCraft lists an app at its prefix, and forwards an assistant tool call to the address
  # it has for it inside the suite's network. In a packaged stack both are known.
  LIST="$LIST,$id=/$prefix/"; OPS="$OPS,$id=http://127.0.0.1:$port/$prefix"; ROUTES="$ROUTES /$prefix/=$port"
done

# PlantCraft's --reset clears its own workspace; what the suite's modules stored is cleared here.
if [ -n "$FLAGS" ]; then
  for id in histcraft linkcraft dashcraft alarmcraft modelcraft doccraft; do rm -rf "$PLANTCRAFT_DIR/var/$id"; done
fi

if curl -fs -o /dev/null "$PLANTCRAFT_URL/"; then
  echo "Something already answers at $PLANTCRAFT_URL: stop the demo that is running first."; exit 1
fi
echo "Starting PlantCraft, BatchLens and $(( $(wc -w <<<"$APPS") - 1 )) of the suite's modules..."
: > /tmp/batchlens-demo.log
PIDS=""
# PlantCraft's launcher starts the Simulator and PlantCraft as children: they are stopped first.
# (Each command ends in "|| true": under "set -e" a pid without children would end the trap early.)
trap 'for pid in $PIDS; do pkill -P "$pid" 2>/dev/null || true; done; kill $PIDS 2>/dev/null || true; wait 2>/dev/null || true; echo; echo "Stopped."' EXIT
# A signal ends the script through the line above (bash alone would leave the servers running).
trap 'exit 143' TERM INT HUP
(cd "$PLANTCRAFT_DIR" && PLANTCRAFT_APPS="${LIST#,}" PLANTCRAFT_OPS_URLS="${OPS#,}" \
  exec python -c "$LAUNCH; sys.exit(demo.main(sys.argv[2:]))" "$SCENARIO" --no-linkcraft $FLAGS) >> /tmp/batchlens-demo.log 2>&1 &
PIDS="$PIDS $!"
for _ in $(seq 1 180); do
  curl -fs -o /dev/null "$PLANTCRAFT_URL/" && break
  kill -0 $PIDS 2>/dev/null || { echo "PlantCraft stopped; see /tmp/batchlens-demo.log"; exit 1; }
  sleep 2
done
curl -fs -o /dev/null "$PLANTCRAFT_URL/" || { echo "PlantCraft did not answer; see /tmp/batchlens-demo.log"; exit 1; }

# Each app gets an app key from PlantCraft's workspace (made once, kept beside its data), as
# PlantCraft's own launcher gives one to an app it starts. After PlantCraft is up: --reset
# clears the workspace first.
# Historian may read CSV files only in the folders named here: the plant's folder.
export HISTCRAFT_CSV_DIRS="$PLANT_DIR"
# Models' built-in examples are about the refinery (a furnace): not in this plant.
export MODELCRAFT_EXAMPLES=false
for app in $APPS; do
  IFS=: read -r id prefix port command <<<"$app"
  key=$(cd "$PLANTCRAFT_DIR" && python -c "$LAUNCH; print(demo._app_key(sys.argv[2], demo.PROJECT_ROOT / 'var' / sys.argv[2]))" "$SCENARIO" "$id")
  env PLANTCRAFT_URL="$PLANTCRAFT_URL" PLANTCRAFT_APP_KEY_FILE="$key" "$(tr a-z A-Z <<<"$id")_DATA_DIR=$PLANTCRAFT_DIR/var/$id" \
    "$command" serve --port "$port" >> /tmp/batchlens-demo.log 2>&1 &
  PIDS="$PIDS $!"
done
# shellcheck disable=SC2086
python "$REPO/tools/gateway.py" "$GATEWAY_PORT" 8060 $ROUTES >> /tmp/batchlens-demo.log 2>&1 &
PIDS="$PIDS $!"
for _ in $(seq 1 60); do
  curl -fs -o /dev/null "$DEMO_URL/batchlens/healthz" && break
  sleep 1
done
curl -fs -o /dev/null "$DEMO_URL/batchlens/healthz" || { echo "BatchLens did not answer; see /tmp/batchlens-demo.log"; exit 1; }

echo "Loading the synthetic batches: six finished, one running now..."
# With --reset the batches are loaded again as generated, undoing corrections made in the app,
# and the campaign's dates are set again from today.
LIVE_FROM=$(BATCHLENS_DATA_DIR="$DATA_DIR" batchlens seed-demo --live $FLAGS 2>/dev/null \
  | python -c 'import json,sys; print(json.load(sys.stdin)["live_from"])')

echo "Writing the synthetic plant for time zone $ZONE and importing it into PlantCraft..."
plant_files() { batchlens demo-plant --out "$PLANT_DIR" --time-zone "$ZONE" --live-from "$LIVE_FROM" 2>/dev/null; }
plant_files | tail -1
# The bioreactor is live: its file is written again every minute, up to now.
(while sleep 60; do plant_files > /dev/null; done) &
PIDS="$PIDS $!"
COOKIES=$(mktemp)
curl -fs -c "$COOKIES" -o /dev/null "$PLANTCRAFT_URL/api/session"
if [ "${PLANTCRAFT_BASIC_AUTH_ENABLED:-}" = "true" ]; then
  # With sign-in on, the import is the administrator's.
  python - "$PLANTCRAFT_BASIC_AUTH_USERNAME" "$PLANTCRAFT_BASIC_AUTH_PASSWORD_FILE" <<'PY' \
    | curl -fs -b "$COOKIES" -c "$COOKIES" -o /dev/null -H 'Content-Type: application/json' --data-binary @- "$PLANTCRAFT_URL/api/login"
import json, sys
print(json.dumps({"username": sys.argv[1], "password": open(sys.argv[2]).read().rstrip("\r\n")}))
PY
  if [ -n "${BATCHLENS_DEMO_GUEST:-}" ]; then
    echo "Adding the read-only guest..."
    users() { (cd "$PLANTCRAFT_DIR" && plantcraft users --scenario "$SCENARIO" "$@"); }
    users add "$BATCHLENS_DEMO_GUEST" --name "Guest" --access viewer > /dev/null 2>&1 || true  # there already
    PLANTCRAFT_PASSWORD=$(cat "$BATCHLENS_DEMO_GUEST_PASSWORD_FILE") users password "$BATCHLENS_DEMO_GUEST" > /dev/null
  fi
fi
curl -fs -b "$COOKIES" -X POST --data-binary "@$PLANT_DIR/plant-map.json" \
  "$PLANTCRAFT_URL/api/map/apply?filename=plant-map.json" \
  | python -c 'import json,sys; r=json.load(sys.stdin); print("imported:", r["applied"], {s["name"]: [s["create"], s["update"], s["unchanged"]] for s in r["sections"]}, "issues:", r["issues"])'
rm -f "$COOKIES"

echo "Giving the suite's modules the mAb plant (history, control loops, signal ranges, dashboards, a process display, alarm rules, documents)..."
python "$REPO/tools/seed_suite.py" "$DEMO_URL" "$PLANT_DIR/bioreactor.csv" "$ZONE" 2>&1 | tail -1

cat <<DONE

Ready. Everything shown is synthetic.
  Open:    $DEMO_URL   (no password; BatchLens and the suite's modules are in the app
                                switcher, top left)
  A tour:  docs/demo.md, "A five-minute tour"
Ctrl+C stops everything.
DONE
wait
