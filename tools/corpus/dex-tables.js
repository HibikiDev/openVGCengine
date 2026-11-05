'use strict';













const fs = require('fs');
const path = require('path');
const { Dex, toID } = require('../showdown-oracle/lib/showdown');

const MODS = ['champions', 'gen5', 'gen6', 'gen7', 'gen8', 'gen9'];
const OUT = path.join(__dirname, 'out', 'dex-tables.json');

function main() {
	const out = { abilities: {}, movepools: {}, species: {}, moves: {}, names: { moves: {}, items: {}, abilities: {}, species: {}, natures: {} } };
	for (const mod of MODS) {
		const dex = Dex.mod(mod);
		const table = {};
		for (const s of dex.species.all()) {
			if (!s.exists) continue;
			table[toID(s.name)] = [...new Set(Object.values(s.abilities))].filter(a => a && a !== 'No Ability').sort();
		}
		out.abilities[mod] = table;
		const pools = {}, species = {}, moves = {};
		for (const sp of dex.species.all()) {
			if (!sp.exists || sp.gen > dex.gen) continue;
			const pool = [...dex.species.getMovePool(sp.id)].sort();
			if (!pool.length) continue;
			pools[sp.id] = pool;
			species[sp.id] = { types: sp.types, bs: sp.baseStats };
		}
		for (const m of dex.moves.all()) {
			if (!m.exists || m.gen > dex.gen || m.isZ || m.isMax || m.isNonstandard) continue;
			moves[m.id] = { type: m.type, cat: m.category, bp: m.basePower, pri: m.priority, target: m.target,
				acc: m.accuracy === true ? 101 : m.accuracy, heal: m.flags.heal ? 1 : 0 };
		}
		out.movepools[mod] = pools;
		out.species[mod] = species;
		out.moves[mod] = moves;
		for (const kind of Object.keys(out.names)) {
			for (const x of dex[kind].all()) if (x.exists) out.names[kind][x.id] = x.name;
		}
		console.log(`${mod}: ${Object.keys(table).length} species`);
	}
	fs.writeFileSync(OUT, JSON.stringify(out) + '\n');
	console.log(`wrote ${OUT}`);
}

main();
