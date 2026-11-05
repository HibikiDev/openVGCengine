'use strict';













const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const SHOWDOWN = process.env.SHOWDOWN_PATH || path.join(ROOT, 'vendor', 'pokemon-showdown');
const { Dex } = require(path.join(SHOWDOWN, 'dist', 'sim'));
const raw = Dex.mod('champions').data.Moves;

const DECLARATIVE = new Set([
	'num', 'name', 'accuracy', 'basePower', 'category', 'pp', 'priority', 'flags', 'target', 'type', 'secondary', 'secondaries',
	'boosts', 'self', 'selfBoost', 'status', 'drain', 'recoil', 'heal', 'multihit', 'multiaccuracy', 'critRatio', 'willCrit',
	'selfSwitch', 'breaksProtect',

	'desc', 'shortDesc', 'contestType', 'isNonstandard', 'zMove', 'maxMove', 'gen', 'noSketch',
]);

function main() {
	const cov = require('./out/pool-coverage.json');
	const implemented = cov.moves.filter(m => m.status === 'implemented').map(m => m.id);
	const knownFlags = new Set(implemented.flatMap(id => Object.keys((raw[id] || {}).flags || {})));
	const dataOnly = [];
	const logic = [];


	let candidates = cov.moves.filter(m => m.status === 'missing').map(m => m.id);
	if (process.argv.includes('--catalog') || process.argv.includes('--vgc13')) {
		const ported = new Set(implemented);
		candidates = require('./ids/moves.json').filter(id => !ported.has(id) && id !== 'struggle');
		if (process.argv.includes('--vgc13')) {
			const vgc13 = new Set(require('./out/vgc13/moves.json').map(m => m.id));
			candidates = candidates.filter(id => vgc13.has(id));
		}

		candidates = candidates.filter(id => !raw[id].isZ && !raw[id].isMax);
	}
	for (const m of candidates.map(id => ({ id }))) {
		const def = raw[m.id];
		const extra = Object.keys(def).filter(k => !DECLARATIVE.has(k) || typeof def[k] === 'function');


		const selfExtra = def.self ? Object.keys(def.self).filter(k => k !== 'boosts' && !(k === 'volatileStatus' && def.self[k] === 'mustrecharge' && def.flags.recharge)) : [];
		if (selfExtra.length) extra.push('self.' + selfExtra.join('+'));

		if (def.secondaries && def.secondaries.length > 2) extra.push('secondaries>2');

		for (const sec of [def.secondary, ...(def.secondaries || [])].filter(Boolean)) {
			const fns = Object.keys(sec).filter(k => typeof sec[k] === 'function');
			const selfFns = sec.self ? Object.keys(sec.self).filter(k => typeof sec.self[k] === 'function') : [];
			if (fns.length || selfFns.length) extra.push('secondary.' + [...fns, ...selfFns.map(k => 'self.' + k)].join('+'));

			else if (!(sec.status || sec.boosts || (sec.self && sec.self.boosts) || sec.volatileStatus === 'flinch')) {
				extra.push('secondary.' + (sec.volatileStatus || Object.keys(sec).filter(k => k !== 'chance').join('+') || 'empty'));
			}
		}
		const newFlags = Object.keys(def.flags || {}).filter(f => !knownFlags.has(f));
		if (extra.length) logic.push({ id: m.id, extra });
		else dataOnly.push({ id: m.id, newFlags });
	}
	console.log(`data-only (${dataOnly.length}):`);
	console.log('  ' + dataOnly.map(m => m.newFlags.length ? `${m.id}[new flags: ${m.newFlags}]` : m.id).join(' '));
	const byKey = {};
	for (const m of logic) for (const k of m.extra) (byKey[k] = byKey[k] || []).push(m.id);
	console.log(`\nlogic (${logic.length}), by the field that needs engine work:`);
	for (const [k, ids] of Object.entries(byKey).sort((a, b) => b[1].length - a[1].length)) {
		console.log(`  ${k} (${ids.length}): ${ids.join(' ')}`);
	}
}

main();
