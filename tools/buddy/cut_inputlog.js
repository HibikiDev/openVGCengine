












'use strict';
const fs = require('fs');
const path = require('path');

const argv = process.argv.slice(2);
const keepArg = argv.find(a => a.startsWith('--keep='));
const keep = keepArg ? keepArg.slice(7) : null;
if (keep && keep !== 'p1' && keep !== 'p2') {
	console.error('cut_inputlog: --keep must be p1 or p2');
	process.exit(2);
}
const [src, turnArg, serverDir] = argv.filter(a => !a.startsWith('--'));
if (!src || !turnArg) {
	console.error('usage: node cut_inputlog.js <battle.log.json | inputlog.txt> <turn> [<buddy server dir>]');
	process.exit(2);
}
const turn = parseInt(turnArg, 10);
const dir = path.resolve(serverDir || path.join(__dirname, '../../trainer/runs/buddy_server'));
const {BattleStream} = require(path.join(dir, 'dist/sim/battle-stream'));

const raw = fs.readFileSync(src, 'utf8');
let lines, winner = null, sheets = [];
if (src.endsWith('.json')) {
	const d = JSON.parse(raw);
	lines = d.inputLog.slice();
	winner = d.winner || null;
	sheets = (d.log || []).filter(l => l.startsWith('|showteam|'));



	if (sheets.length) {
		const last = lines.map(l => l.startsWith('>player ')).lastIndexOf(true);
		if (last >= 0) lines.splice(last + 1, 0, '>show-openteamsheets');
	}
} else {
	lines = raw.replace(/\r/g, '').split('\n').filter(Boolean);
}
if (!lines || !lines.length || !lines[0].startsWith('>')) {
	console.error('cut_inputlog: no input log in ' + src);
	process.exit(1);
}

function run(upTo) {

	const s = new BattleStream({noCatch: true});
	let used = 0;
	for (const line of lines) {
		const m = /^>(p\d) /.exec(line);
		if (m && upTo !== null && s.battle && s.battle.turn >= upTo) break;
		s._writeLines(line);
		used++;
	}
	return {used, battle: s.battle};
}

const full = run(null);
const fb = full.battle;
const fullWinner = fb && fb.winner;
const cut = run(turn);
const b = cut.battle;
if (!b || b.turn < turn) {
	console.error(`cut_inputlog: the battle never reached turn ${turn} (it ended at turn ${fb ? fb.turn : '?'})`);
	process.exit(1);
}
if (sheets.length) {

	const shown = b.log.filter(l => l.startsWith('|showteam|'));
	const same = shown.length === sheets.length && shown.every((l, i) => l === sheets[i]);
	console.error(`open team sheets: ${shown.length} revealed, ${same ? 'identical to the original game' : 'DIFFERENT from the original game'}`);
	if (!same) process.exit(4);
}
const state = b.sides.map(side => `${side.id}: ` + side.active.map(p => p ? `${p.name} ${p.hp}/${p.maxhp}` : '-').join(', '));
let out = lines.slice(0, cut.used);
if (keep) {

	const j = lines.findIndex((l, i) => i >= cut.used && l.startsWith(`>${keep} `));
	const kept = j >= 0 ? lines[j] : null;
	const s = new BattleStream({noCatch: true});
	for (const l of out) s._writeLines(l);
	if (kept) s._writeLines(kept);
	const side = kept && s.battle.sides.find(x => x.id === keep);
	if (!kept || s.battle.turn !== b.turn || !side.isChoiceDone()) {
		console.error(`cut_inputlog: no usable turn-${turn} choice for ${keep} (${kept || 'none in the log'})`);
		process.exit(5);
	}
	out = out.concat([kept]);
	console.error(`kept ${keep}'s original turn-${b.turn} choice: ${kept.slice(4)}`);
}
process.stdout.write(out.join('\n') + '\n');
console.error(`cut at turn ${b.turn}: ${cut.used} of ${lines.length} lines | ${state.join(' | ')}`);
console.error(`full replay: ended turn ${fb.turn}, winner ${JSON.stringify(fullWinner)}` +
	(winner !== null ? ` (saved: ${JSON.stringify(winner)} - ${fullWinner === winner ? 'match' : 'MISMATCH'})` : ''));
if (winner !== null && fullWinner !== winner) process.exit(3);
