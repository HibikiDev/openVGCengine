'use strict';


















const fs = require('fs');
const path = require('path');
const { Dex, toID } = require('./lib/showdown');
const { extractSpecies, extractMoves, extractAbilities, extractItems } = require('./gen-data');

const OUT_DIR = path.join(__dirname, 'out');
const g9 = Dex.forGen(9);
const dex = Dex.mod('champions');

const OPEN = { isBannedSpecies: () => false, isBanned: () => false };

const inScope = e => e && e.exists && (!e.isNonstandard || e.isNonstandard === 'Past');
const pool = name => new Set(require(path.join(OUT_DIR, `${name}.json`)).map(e => e.id));

const LEGACY = fs.readdirSync(OUT_DIR, { withFileTypes: true }).filter(d => d.isDirectory() && fs.existsSync(path.join(OUT_DIR, d.name, 'summary.json')))
	.map(d => path.join(OUT_DIR, d.name));
const legacy = kind => new Set(LEGACY.flatMap(dir => require(path.join(dir, `${kind}.json`)).map(e => e.id)));

function main() {
	const poolSpecies = pool('species'), poolAbilities = pool('abilities'), poolItems = pool('items'), poolMoves = pool('moves');

	const speciesIds = new Set(g9.species.all().filter(s => inScope(s) && !poolSpecies.has(s.id)).map(s => s.id));
	for (const id of legacy('species')) if (!poolSpecies.has(id)) speciesIds.add(id);
	const species = extractSpecies(dex, OPEN).filter(s => speciesIds.has(s.id));
	if (species.length !== speciesIds.size) {
		const got = new Set(species.map(s => s.id));
		throw new Error(`species missing from the champions dex: ${[...speciesIds].filter(id => !got.has(id)).join(', ')}`);
	}

	const abilityIds = new Set(g9.abilities.all().filter(a => inScope(a) && !poolAbilities.has(a.id)).map(a => a.id));
	for (const id of legacy('abilities')) if (!poolAbilities.has(id)) abilityIds.add(id);
	for (const s of species) for (const name of Object.values(s.abilities)) if (!poolAbilities.has(toID(name))) abilityIds.add(toID(name));
	const abilities = [...abilityIds].map(id => dex.abilities.get(id))
		.filter(a => a.exists)
		.map(a => ({ id: a.id, name: a.name, rating: a.rating, flags: Object.keys(a.flags).filter(k => a.flags[k]).sort() }))
		.sort((a, b) => a.id.localeCompare(b.id));
	if (abilities.length !== abilityIds.size) throw new Error('an ability is missing from the champions dex');

	const itemIds = new Set(g9.items.all().filter(i => inScope(i) && !poolItems.has(i.id)).map(i => i.id));
	for (const id of legacy('items')) if (!poolItems.has(id)) itemIds.add(id);
	const items = extractItems(dex, OPEN, true).filter(i => itemIds.has(i.id));



	const moveIds = new Set(g9.moves.all().filter(m => inScope(m) && !poolMoves.has(m.id)).map(m => m.id));

	for (const m of g9.moves.all()) if (m.exists && m.isNonstandard === 'Gmax' && !poolMoves.has(m.id)) moveIds.add(m.id);
	for (const id of legacy('moves')) if (!poolMoves.has(id)) moveIds.add(id);
	const moves = extractMoves(dex, OPEN, moveIds);

	const write = (name, data) => fs.writeFileSync(path.join(OUT_DIR, name), JSON.stringify(data, null, '\t') + '\n');
	write('catalog-species.json', species);
	write('catalog-abilities.json', abilities);
	write('catalog-items.json', items);
	write('catalog-moves.json', moves);


	const metronomePool = mod => Dex.mod(mod).moves.all()
		.filter(m => (!m.isNonstandard || m.isNonstandard === 'Unobtainable') && m.flags['metronome'])
		.sort((a, b) => a.num - b.num).map(m => m.id);
	write('metronome-pools.json', { championsmc: metronomePool('champions'), gen5vgc13: metronomePool('gen5'), gen6vgc: metronomePool('gen6'),


		gen7vgc: metronomePool('gen7'),

		gen9sv: metronomePool('gen9'), gen9svpredlc: metronomePool('gen9predlc'),

		gen8vgc: metronomePool('gen8') });


	const gen5 = Dex.mod('gen5');

	const gen5Ids = gen5.moves.all().filter(m => m.exists && m.gen >= 1 && m.gen <= 5 && !m.isNonstandard && !/^hiddenpower./.test(m.id) && m.id !== 'vcreate')
		.map(m => m.id);
	write('gen5-moves.json', extractMoves(gen5, OPEN, new Set(gen5Ids)));


	const gen6 = Dex.mod('gen6');
	const gen6Ids = gen6.moves.all().filter(m => m.exists && m.gen >= 1 && m.gen <= 6 && !m.isNonstandard && !/^hiddenpower./.test(m.id) && m.id !== 'vcreate')
		.map(m => m.id);
	write('gen6-moves.json', extractMoves(gen6, OPEN, new Set(gen6Ids)));



	const gen7 = Dex.mod('gen7');
	const gen7Ids = gen7.moves.all().filter(m => m.exists && m.gen >= 1 && m.gen <= 7 && !m.isNonstandard && !/^hiddenpower./.test(m.id) && m.id !== 'vcreate')
		.map(m => m.id);
	write('gen7-moves.json', extractMoves(gen7, OPEN, new Set(gen7Ids)));





	for (const [mod, file] of [['gen9', 'gen9-moves.json'], ['gen9predlc', 'gen9predlc-moves.json'], ['gen8', 'gen8-moves.json']]) {
		const d = Dex.mod(mod);
		const ids = d.moves.all().filter(m => m.exists && (!m.isNonstandard || m.isNonstandard === 'Unobtainable' || (mod === 'gen8' && m.isNonstandard === 'Gmax')) && !/^hiddenpower./.test(m.id))
			.map(m => m.id);
		write(file, extractMoves(d, OPEN, new Set(ids)));
	}
	console.log(`catalog (not in the legal pool): ${species.length} species, ${abilities.length} abilities, ${items.length} items, ` +
		`${moves.length} moves`);
}

main();
