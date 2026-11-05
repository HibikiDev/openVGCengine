#!/bin/bash

source "$(dirname "$0")/common.sh"
f="$1"
out=$("$DIFFRUN" replay "$f" 2>&1)
if echo "$out" | grep -q "=== PASS"; then echo "PASS $f"; rm -f "$f.fail.log"; else echo "FAIL $f"; echo "$out" > "$f.fail.log"; fi
