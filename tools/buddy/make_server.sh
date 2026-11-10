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




sed -i.bak -E "s/^exports\.logchallenges = .*/exports.logchallenges = true;/" "$C"
rm -f "$C.bak"
grep -qE "^exports\.logchallenges = true;" "$C" || echo "exports.logchallenges = true;" >> "$C"
if ! grep -q "importinputlog for every local user" "$C"; then
  echo "// importinputlog for every local user (tools/buddy/make_server.sh, user 11-08)" >> "$C"
  echo "for (const g of exports.grouplist) if (g.symbol === ' ') g.importinputlog = true;" >> "$C"
fi


cp "$HERE/position-plugin.js" "$DEST/dist/server/chat-plugins/openvgc-position.js"
cp "$HERE/position-plugin.js" "$DEST/dist/sim/openvgc-position.js"
mkdir -p "$DEST/logs/positions"

cp "$HERE/coach-plugin.js" "$DEST/dist/server/chat-plugins/openvgc-coach.js"


cp "$HERE/openvgc-i18n.js" "$DEST/dist/server/openvgc-i18n.js"
cp "$HERE/lang-plugin.js" "$DEST/dist/server/chat-plugins/openvgc-lang.js"

node -e "const c = require(process.argv[1]); if (!c.logchallenges || !c.grouplist.find(g => g.symbol === ' ').importinputlog) process.exit(3)" "$C" \
  || { echo "make_server.sh: $C doesn't load, or lacks logchallenges / importinputlog"; exit 1; }
node -e "const {Dex} = require(require('path').resolve(process.argv[1], 'dist/sim')); const f = Dex.formats.all(); console.log(f.length + ' formats, all buddy: ' + f.every(x => x.id.endsWith('buddy')) + ' - ' + f.map(x => x.id).join(' '))" "$DEST"
echo "make_server.sh: $DEST ready (127.0.0.1 only, buddy formats only)"
