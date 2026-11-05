#!/usr/bin/env node












'use strict';
const fs = require('fs');
const path = require('path');
const { Dex } = require('./lib/showdown');

const arg = (name, dflt) => { const i = process.argv.indexOf(`--${name}`); return i >= 0 ? process.argv[i + 1] : dflt; };
const MOD = arg('mod', 'gen5'), VS = arg('vs', 'champions');
const POOLS = arg('pools', 'vgc13').split(',');
const g5 = Dex.mod(MOD);
const ch = Dex.mod(VS);

const pool = kind => [...new Set(POOLS.flatMap(p => require(path.join(__dirname, 'out', p, `${kind}.json`)).map(e => e.id)))];
const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);

function handlers(a, b) {
	const names = new Set([...Object.keys(a), ...Object.keys(b)].filter(k => typeof a[k] === 'function' || typeof b[k] === 'function'));
	return [...names].filter(k => String(a[k]) !== String(b[k])).sort();
}

function diffFields(a, b, fields) {
	const out = {};
	for (const f of fields) if (!same(a[f], b[f])) out[f] = { [MOD]: a[f] ?? null, [VS]: b[f] ?? null };
	return out;
}

const MOVE_FIELDS = ['basePower', 'accuracy', 'type', 'priority', 'category', 'pp', 'target', 'critRatio', 'secondary', 'flags',
	'drain', 'recoil', 'multihit', 'self', 'boosts', 'status', 'volatileStatus', 'ignoreAbility', 'willCrit'];
const SPECIES_FIELDS = ['baseStats', 'types', 'abilities', 'weightkg'];

const result = { generated: new Date().toISOString(), moves: {}, species: {}, abilities: {}, items: {}, conditions: {}, typechart: [] };
for (const id of pool('moves')) {
	const a = g5.moves.get(id), b = ch.moves.get(id);
	const fields = diffFields(a, b, MOVE_FIELDS);
	const h = handlers(a, b).concat(handlers(a.condition || {}, b.condition || {}).map(k => `condition.${k}`));
	if (Object.keys(fields).length || h.length) result.moves[id] = { ...fields, ...(h.length ? { handlers: h } : {}) };
}
for (const id of pool('species')) {
	const a = g5.species.get(id), b = ch.species.get(id);
	const fields = diffFields(a, b, SPECIES_FIELDS);
	if (Object.keys(fields).length) result.species[id] = fields;
}
for (const kind of ['abilities', 'items']) {
	for (const id of pool(kind)) {
		const a = g5[kind].get(id), b = ch[kind].get(id);
		const h = handlers(a, b).concat(handlers(a.condition || {}, b.condition || {}).map(k => `condition.${k}`));
		const fields = kind === 'items' ? diffFields(a, b, ['fling', 'naturalGift', 'onPlate', 'megaStone']) : {};
		if (h.length || Object.keys(fields).length) result[kind][id] = { ...fields, ...(h.length ? { handlers: h } : {}) };
	}
}

for (const id of [...new Set([...Object.keys(g5.data.Conditions), ...Object.keys(ch.data.Conditions)])].sort()) {
	const a = g5.conditions.get(id), b = ch.conditions.get(id);
	const h = handlers(a, b);
	const fields = diffFields(a, b, ['duration', 'counterMax']);
	if (h.length || Object.keys(fields).length) result.conditions[id] = { ...fields, ...(h.length ? { handlers: h } : {}) };
}
for (const atk of g5.types.names()) {
	for (const def of g5.types.names()) {
		const a = g5.getEffectiveness(atk, def) + (g5.getImmunity(atk, def) ? 0 : 100);
		const b = ch.getEffectiveness(atk, def) + (ch.getImmunity(atk, def) ? 0 : 100);
		if (a !== b) result.typechart.push({ attack: atk, defend: def, [MOD]: a, [VS]: b });
	}
}

const out = path.join(__dirname, 'out', VS === 'champions' ? `${MOD}-diff.json` : `${MOD}-vs-${VS}-diff.json`);
fs.writeFileSync(out, JSON.stringify(result, null, '\t') + '\n');
const count = o => Object.keys(o).length;
console.log(`wrote ${out}: moves ${count(result.moves)} / ${pool('moves').length}, species ${count(result.species)} / ${pool('species').length}, ` +
	`abilities ${count(result.abilities)} / ${pool('abilities').length}, items ${count(result.items)} / ${pool('items').length}, ` +
	`conditions ${count(result.conditions)}, type-chart cells ${result.typechart.length} (${MOD}'s ${g5.types.names().length} types)`);
