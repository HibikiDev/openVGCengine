#!/bin/bash





set -eu
HERE="$(cd "$(dirname "$0")" && pwd)"
SRC="$(cd "${1:-$HERE/../../vendor/pokemon-showdown}" && pwd)"
DEST="${2:-$HERE/../../trainer/runs/buddy_server}"
mkdir -p "$DEST"
DEST="$(cd "$DEST" && pwd)"
[ -f "$SRC/dist/config/formats.js" ] || { echo "make_server.sh: $SRC is not a built Showdown (no dist/config/formats.js)"; exit 1; }

for d in dist node_modules config data lib server sim translations databases pokemon-showdown package.json LICENSE; do
  [ -e "$SRC/$d" ] && cp -r "$SRC/$d" "$DEST/"
done
mkdir -p "$DEST/logs/repl" "$DEST/logs/chat" "$DEST/logs/modlog"
rm -f "$DEST/dist/config/custom-formats.js"
cp "$SRC/dist/config/formats.js" "$DEST/dist/config/formats-showdown.js"
cp "$HERE/buddy-formats.js" "$DEST/dist/config/formats.js"
C="$DEST/config/config.js"
[ -f "$C" ] || cp "$DEST/config/config-example.js" "$C"
sed -i.bak -E "s/^exports\.bindaddress = .*/exports.bindaddress = '127.0.0.1';/; s/^exports\.backdoor = .*/exports.backdoor = false;/; s/^exports\.noguestsecurity = .*/exports.noguestsecurity = true;/" "$C"
rm -f "$C.bak"
grep -qE "^exports\.noguestsecurity = true;" "$C" || echo "exports.noguestsecurity = true;" >> "$C"
grep -qE "^exports\.bindaddress = '127.0.0.1';" "$C" || echo "exports.bindaddress = '127.0.0.1';" >> "$C"
grep -qE "^exports\.backdoor = false;" "$C" || echo "exports.backdoor = false;" >> "$C"
node -e "const {Dex} = require(require('path').resolve(process.argv[1], 'dist/sim')); const f = Dex.formats.all(); console.log(f.length + ' formats, all buddy: ' + f.every(x => x.id.endsWith('buddy')) + ' - ' + f.map(x => x.id).join(' '))" "$DEST"
echo "make_server.sh: $DEST ready (127.0.0.1 only, buddy formats only)"
