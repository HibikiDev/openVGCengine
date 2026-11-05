#!/bin/bash


source "$(dirname "$0")/common.sh"
cd "$ROOT"
cargo build -q -p diff 2>&1 | grep -E "^error" && exit 1
cp "target/debug/diff$EXE" "$DIFFRUN" || { echo "REG copy failed"; exit 1; }
bash "$(dirname "$0")/verify.sh" $1 > "$RUNS/verify_$1.txt" 2>&1
grep -E "test result|REPLAY PASS|CORPUS FIXTURES|corpus fixture FAIL|random-legal|FAILED|panicked" "$RUNS/verify_$1.txt" | sort | uniq -c | sed 's/^/REG /'
echo "REG fixtures passing: $(grep -c '=== PASS' "$RUNS/verify_$1.txt")"
for s in $(seq $2 $3); do bash "$(dirname "$0")/cb.sh" $s 100 2>&1 | grep -v "no legal choice\|^wrote"; done
echo "ALL DONE"
