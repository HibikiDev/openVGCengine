'use strict';















const fs = require('fs');
const path = require('path');
const { Dex, toID } = require('./lib/showdown');

const DEFAULT_FORMAT = 'gen9championsvgc2026regmc';
const OUT_DIR = path.join(__dirname, 'out');

function parseArgs(argv) {
	const args = { format: DEFAULT_FORMAT, outDir: OUT_DIR };
	for (let i = 0; i < argv.length; i++) {
		if (argv[i] === '--format') args.format = argv[++i];
		else if (argv[i] === '--out-dir') args.outDir = path.resolve(argv[++i]);
		else throw new Error(`Unknown arg: ${argv[i]}`);
	}
	return args;
}



function findLearnsetEntry(dex, species) {
	let s = species;
	const seen = new Set();
	while (s && !seen.has(s.id)) {
		seen.add(s.id);
		const entry = dex.data.Learnsets[s.id];
		if (entry) return entry;
		const next = s.battleOnly
			? dex.species.get(Array.isArray(s.battleOnly) ? s.battleOnly[0] : s.battleOnly)
			: (s.prevo ? dex.species.get(s.prevo) : dex.species.get(s.baseSpecies));
		if (!next || next.id === s.id) break;
		s = next;
	}
	return null;
}

function extractSpecies(dex, ruleTable) {
	return dex.species.all()
		.filter(s => s.exists && !ruleTable.isBannedSpecies(s))
		.map(s => ({
			id: s.id,
			name: s.name,
			num: s.num,
			baseSpecies: s.baseSpecies,
			forme: s.forme,
			battleOnly: s.battleOnly || null,
			isMega: !!s.isMega,
			requiredItem: s.requiredItem || null,
			requiredMove: s.requiredMove || null,
			types: s.types,
			baseStats: s.baseStats,
			abilities: s.abilities,
			weightkg: s.weightkg,

			nfe: !!s.nfe,

			...(s.maxHP ? { maxHP: s.maxHP } : {}),

			gender: s.gender || "",
			genderRatio: s.genderRatio,
			prevo: s.prevo || null,
			evos: s.evos,
		}));
}






function extractMoveIds(dex, legalSpecies, minSourceGen) {
	const moveIds = new Set();
	let sketch = false;
	for (const s of legalSpecies) {
		const entry = findLearnsetEntry(dex, s);
		if (!entry || !entry.learnset) continue;
		for (const [moveId, methods] of Object.entries(entry.learnset)) {


			if (dex.moves.get(moveId).isNonstandard) continue;
			if (methods.some(m => parseInt(m, 10) >= minSourceGen && parseInt(m, 10) <= dex.gen)) {
				moveIds.add(moveId);
				if (moveId === 'sketch') sketch = true;
			}
		}
	}
	if (sketch) {
		for (const m of dex.moves.all()) {
			if (m.isNonstandard || m.isZ || m.isMax || m.flags['nosketch'] || m.id === 'struggle') continue;
			if (m.id.startsWith('hiddenpower') && m.id !== 'hiddenpower') continue;
			if (m.gen > 7 && dex.gen === 8) continue;
			moveIds.add(m.id);
		}
	}
	return moveIds;
}

function extractMoves(dex, ruleTable, moveIds) {
	return [...moveIds]
		.map(id => dex.moves.get(id))
		.filter(m => m.exists && !ruleTable.isBanned('move:' + m.id))
		.map(m => ({
			id: m.id,
			name: m.name,
			type: m.type,
			category: m.category,
			basePower: m.basePower,
			accuracy: m.accuracy,
			pp: m.pp,
			priority: m.priority,
			target: m.target,
			critRatio: m.critRatio,
			flags: m.flags,
			secondary: m.secondary || null,
			secondaries: m.secondaries || null,
			boosts: m.boosts || null,
			status: m.status || null,
			volatileStatus: m.volatileStatus || null,
			drain: m.drain || null,
			recoil: m.recoil || null,
			multihit: m.multihit || null,
			multiaccuracy: m.multiaccuracy || null,
			self: m.self || null,
			selfBoost: m.selfBoost || null,
			heal: m.heal || null,
			ignoreImmunity: m.ignoreImmunity,
			selfSwitch: m.selfSwitch ?? null,
			willCrit: m.willCrit ?? null,
			breaksProtect: m.breaksProtect ?? null,
			sleepUsable: m.sleepUsable ?? null,
		}))
		.sort((a, b) => a.id.localeCompare(b.id));
}

function extractAbilities(dex, ruleTable, legalSpecies) {
	const abilityIds = new Set();
	for (const s of legalSpecies) {
		for (const key of Object.keys(s.abilities)) abilityIds.add(toID(s.abilities[key]));
	}
	return [...abilityIds]
		.map(id => dex.abilities.get(id))
		.filter(a => a.exists && !ruleTable.isBanned('ability:' + a.id))
		.map(a => ({ id: a.id, name: a.name, rating: a.rating, flags: Object.keys(a.flags).filter(k => a.flags[k]).sort() }))
		.sort((a, b) => a.id.localeCompare(b.id));
}


function extractItems(dex, ruleTable, nonstandard = false) {
	return dex.items.all()
		.filter(i => i.exists && (nonstandard || !i.isNonstandard) && !ruleTable.isBanned('item:' + i.id))
		.map(i => ({
			id: i.id,
			name: i.name,
			megaStone: i.megaStone || null,
			megaEvolves: i.megaEvolves || null,
			isBerry: !!i.isBerry,
			naturalGift: i.naturalGift || null,
			fling: i.fling || null,
			boosts: i.boosts || null,
		}))
		.sort((a, b) => a.id.localeCompare(b.id));
}

function extractTypes(dex) {
	return dex.types.all()
		.filter(t => t.exists)
		.map(t => ({ id: t.id, name: t.name, damageTaken: t.damageTaken }));
}

function main() {
	const { format: formatId, outDir } = parseArgs(process.argv.slice(2));
	const format = Dex.formats.get(formatId);
	if (!format.exists) throw new Error(`Unknown format: ${formatId}`);

	const dex = Dex.mod(format.mod);
	const ruleTable = Dex.formats.getRuleTable(format);
	const minSourceGen = ruleTable.minSourceGen || dex.gen;

	const legalSpecies = extractSpecies(dex, ruleTable);
	const moveIds = extractMoveIds(dex, legalSpecies, minSourceGen);
	const moves = extractMoves(dex, ruleTable, moveIds);
	const abilities = extractAbilities(dex, ruleTable, legalSpecies);
	const items = extractItems(dex, ruleTable);
	const types = extractTypes(dex);

	fs.mkdirSync(outDir, { recursive: true });
	const write = (name, data) => {
		fs.writeFileSync(path.join(outDir, name), JSON.stringify(data, null, '\t') + '\n');
	};
	write('species.json', legalSpecies);
	write('moves.json', moves);
	write('abilities.json', abilities);
	write('items.json', items);
	write('types.json', types);

	const summary = {
		format: formatId,
		formatName: format.name,
		mod: format.mod,
		gameType: format.gameType,
		minSourceGen,
		ruleset: format.ruleset,
		banlist: format.banlist,
		counts: {
			species: legalSpecies.length,
			megaForms: legalSpecies.filter(s => s.isMega).length,
			moves: moves.length,
			abilities: abilities.length,
			items: items.length,
			types: types.length,
		},
		generatedAt: new Date().toISOString(),
	};
	write('summary.json', summary);
	console.log(JSON.stringify(summary, null, 2));
}

if (require.main === module) main();

module.exports = { extractSpecies, extractMoves, extractAbilities, extractItems };
