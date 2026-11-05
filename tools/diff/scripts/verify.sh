#!/bin/bash


source "$(dirname "$0")/common.sh"
cd "$ROOT"

tests=$(cargo test --workspace 2>&1)
echo "$tests" | grep -E "test result: ok. [1-9]|FAILED|panicked"
echo "$tests" | grep -q "test result:" || { echo "CARGO TEST: no results - the test build failed:"; echo "$tests" | grep -E "^error" | head -5; }
cargo build --workspace >/dev/null 2>&1
for f in tools/diff/fixtures/scenario*.json; do echo -n "$(basename "$f" .json): "; ./target/debug/diff$EXE replay "$f" 2>&1 | tail -1; done


find tools/diff/fixtures/corpus -name "*.json" -print0 | DIFFRUN="$ROOT/target/debug/diff$EXE" \
  xargs -0 -P "${JOBS:-8}" -n 20 bash "$(dirname "$0")/run_many.sh" > "$RUNS/fixtures_$1.txt" 2>&1
grep "^FAIL" "$RUNS/fixtures_$1.txt" | sed 's/^FAIL /corpus fixture FAIL: /' | sort
echo "CORPUS FIXTURES PASS: $(grep -c '^PASS' "$RUNS/fixtures_$1.txt")  FAIL: $(grep -c '^FAIL' "$RUNS/fixtures_$1.txt")"
rm -rf "$RUNS/replay_$1" && node tools/showdown-oracle/random-legal.js --count 1000 --seed 1 --branching --out-dir "$RUNS/replay_$1" >/dev/null
find "$RUNS/replay_$1" -name "scenario-*.json" -print0 | xargs -0 -P "${JOBS:-8}" -n 25 bash "$(dirname "$0")/run_many.sh" > "$RUNS/batch_$1.txt" 2>&1
echo "REPLAY PASS: $(grep -c '^PASS' "$RUNS/batch_$1.txt")  FAIL: $(grep -c '^FAIL' "$RUNS/batch_$1.txt")"
grep '^FAIL' "$RUNS/batch_$1.txt" | sed 's/.*scenario/scenario/'
for s in 7 8 9 10 11 12; do ./target/debug/diff$EXE random-legal --count 50 --seed $s 2>&1 | grep -E "random-legal:|^--- scenario" | cut -c1-100; done
