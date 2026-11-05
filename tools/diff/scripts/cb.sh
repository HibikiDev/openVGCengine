#!/bin/bash


source "$(dirname "$0")/common.sh"
cd "$ROOT"
d="$RUNS/cb_$1"
rm -rf "$d"
node tools/showdown-oracle/corpus-battles.js --count $2 --seed $1 --out-dir "$d" ${@:3} 2>&1 | tail -3
find "$d" -name "scenario-*.json" -print0 | xargs -0 -P "${JOBS:-8}" -n 15 bash "$(dirname "$0")/run_many.sh" > "$RUNS/cb_$1.txt" 2>&1
echo "seed $1: PASS $(grep -c '^PASS' "$RUNS/cb_$1.txt") FAIL $(grep -c '^FAIL' "$RUNS/cb_$1.txt")"
for f in "$d"/*.fail.log; do
  [ -f "$f" ] || continue
  m=$(grep -m1 -E "^MISMATCH|doesn't support|not in the legal|forced switch expected|expected exactly" "$f" | sed 's/MISMATCH turn [0-9]* FAIL //' | cut -c1-110)
  [ -z "$m" ] && m=$(grep -m1 -E "RNG replay desync|panicked at" "$f" | sed "s/.*desync/desync/" | cut -c1-140)
  echo "$(basename "$f" .json.fail.log): $m"
done | sort -t: -k2 | head -60
