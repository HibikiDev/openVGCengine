#!/bin/bash




source "$(dirname "$0")/common.sh"
results=$("$DIFFRUN" replay-many "$@" 2>/dev/null | sed -n 's/^RESULT //p')
for f in "$@"; do
  r=$(printf '%s\n' "$results" | grep -F -x -e "PASS $f" -e "FAIL $f" | head -1 | cut -c1-4)
  if [ "$r" = PASS ]; then
    echo "PASS $f"; rm -f "$f.fail.log"
  elif [ -z "$r" ]; then
    bash "$(dirname "$0")/run_one.sh" "$f"
  elif [ "$(bash "$(dirname "$0")/run_one.sh" "$f" | cut -c1-4)" = PASS ]; then
    echo "FAIL $f"; echo "replay-many FAIL, passes alone (shared-oracle state?)" > "$f.fail.log"
  else
    echo "FAIL $f"
  fi
done
