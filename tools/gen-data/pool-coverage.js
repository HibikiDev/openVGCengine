'use strict';






















const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const SHOWDOWN = process.env.SHOWDOWN_PATH || path.join(ROOT, 'vendor', 'pokemon-showdown');
const { Dex } = require(path.join(SHOWDOWN, 'dist', 'sim'));
const dex = Dex.mod('champions');
const simCoded = require('./lib/sim-coded').simCodedChecker(SHOWDOWN);


const INERT = new Set([
	'name', 'num', 'id', 'fullname', 'effectType', 'exists', 'gen', 'rating', 'flags', 'desc', 'shortDesc', 'isNonstandard',
	'fling', 'spritenum', 'isPokeball', 'isGem', 'isBerry', 'naturalGift', 'itemUser', 'sourceEffect', 'kind', 'noCopy',
	'condition', 'duration', 'effectOrder', 'infiltrates', 'suppressWeather', 'realMove', 'isPermanent',
]);

function engineSource() {
	const dir = path.join(ROOT, 'crates', 'engine-core', 'src');


	const code = src => src.split(/#\[cfg\(test\)\]\s*(?:pub(?:\(crate\))?\s+)?mod\s/)[0];
	return fs.readdirSync(dir).filter(f => f.endsWith('.rs')).map(f => code(fs.readFileSync(path.join(dir, f), 'utf8'))).join('\n');
}

function rustIdent(id) {
	return id.toUpperCase().replace(/[^A-Z0-9]/g, '');
}

function corpusCounts() {
	const counts = { moves: new Map(), abilities: new Map(), items: new Map() };
	const file = path.join(ROOT, 'tools', 'corpus', 'out', 'teams-sets.json');
	const bump = (m, k) => m.set(k, (m.get(k) || 0) + 1);
	for (const t of JSON.parse(fs.readFileSync(file, 'utf8')).teams) {
		for (const s of t.sets) {
			for (const mv of s.moves) bump(counts.moves, Dex.toID(mv));
			if (s.ability) bump(counts.abilities, Dex.toID(s.ability));
			if (s.item) bump(counts.items, Dex.toID(s.item));
		}
	}
	return counts;
}

function hasHandlers(def) {

	return Object.keys(def).some(k => !INERT.has(k));
}

function main() {
	const src = engineSource();
	const corpus = corpusCounts();
	const implementedMoves = new Set(
		(fs.readFileSync(path.join(__dirname, 'codegen-moves.js'), 'utf8').match(/MOVE_IDS = \[([\s\S]*?)\];/)[1].match(/'([a-z0-9]+)'/g) || [])
			.map(s => s.slice(1, -1)));
	const report = { moves: [], abilities: [], items: [] };
	for (const m of require('./out/moves.json')) {
		const status = implementedMoves.has(m.id) ? 'implemented' : dex.moves.get(m.id).isNonstandard ? 'past' : 'missing';
		report.moves.push({ id: m.id, status, corpus: corpus.moves.get(m.id) || 0 });
	}
	const abilityData = dex.data.Abilities;
	const abilityStatus = a => {
		if (new RegExp(`ability_ids::${rustIdent(a.id)}\\b`).test(src)) return 'referenced';
		if (!hasHandlers(abilityData[a.id] || {}) && !simCoded(a.id, a.name)) return 'no-effect';
		return 'unported';
	};
	const itemData = dex.data.Items;
	const itemStatus = it => {
		if (new RegExp(`item_ids::${rustIdent(it.id)}\\b`).test(src)) return 'referenced';
		if (it.megaStone) return 'megastone';

		const z = dex.items.get(it.id);
		if (z.zMove) return z.zMoveFrom && !implementedMoves.has(Dex.toID(z.zMove)) ? 'unported' : 'zcrystal';
		if (!hasHandlers(itemData[it.id] || {}) && !simCoded(it.id, it.name)) return 'no-effect';
		return 'unported';
	};
	for (const a of require('./out/abilities.json')) report.abilities.push({ id: a.id, status: abilityStatus(a), corpus: corpus.abilities.get(a.id) || 0 });
	for (const it of require('./out/items.json')) report.items.push({ id: it.id, status: itemStatus(it), corpus: corpus.items.get(it.id) || 0 });
	writeIfChanged('pool-coverage.json', report);


	const catalog = { abilities: [], items: [] };
	const catalogFile = kind => path.join(__dirname, 'out', `catalog-${kind}.json`);
	if (fs.existsSync(catalogFile('abilities'))) {
		for (const a of require(catalogFile('abilities'))) catalog.abilities.push({ id: a.id, status: abilityStatus(a) });
		for (const it of require(catalogFile('items'))) catalog.items.push({ id: it.id, status: itemStatus(it) });
		writeIfChanged('catalog-coverage.json', catalog);
	}
	if (process.argv.includes('--emit')) {
		emitSupportTable({ abilities: [...report.abilities, ...catalog.abilities], items: [...report.items, ...catalog.items] });
	}

	const listArg = process.argv.indexOf('--list');
	const list = listArg >= 0 ? process.argv[listArg + 1] : null;
	for (const [kind, rows] of Object.entries(report)) {
		const by = {};
		for (const r of rows) by[r.status] = (by[r.status] || 0) + 1;
		const unvalidated = rows.filter(r => (r.status === 'referenced' || r.status === 'implemented') && r.corpus === 0).length;
		console.log(`${kind}: ${rows.length} in the legal pool -`, Object.entries(by).map(([k, v]) => `${k} ${v}`).join(', '),
			`(${unvalidated} referenced/implemented but never in the corpus)`);
		if (list) {
			const sel = rows.filter(r => r.status === list).sort((a, b) => b.corpus - a.corpus || a.id.localeCompare(b.id));
			if (sel.length) console.log('  ' + sel.map(r => r.corpus ? `${r.id}(${r.corpus})` : r.id).join(' '));
		}
	}
}


function writeIfChanged(name, data) {
	const file = path.join(__dirname, 'out', name);
	const text = JSON.stringify(data, null, '\t') + '\n';
	if (!fs.existsSync(file) || fs.readFileSync(file, 'utf8') !== text) fs.writeFileSync(file, text);
}

function emitSupportTable(report) {
	const ids = (rows, mod) => rows.filter(r => r.status === 'unported').map(r => `    ${mod}::${rustIdent(r.id)},`).join('\n');
	const abilityIds = ids(report.abilities, 'ability_ids'), itemIds = ids(report.items, 'item_ids');

	const use_ = (table, mod, type, list) => (list ? `use crate::${table}::{${mod}, ${type}};` : `use crate::${table}::${type};`);
	const rust = `//! Generated by tools/gen-data/pool-coverage.js --emit. DO NOT EDIT BY HAND: port the effect, then re-run it.
//!
//! The abilities and items - of the legal pool and of the wider catalog (catalog-data.js) - whose effects the engine doesn't
//! implement. A team using one is refused (\`engine_core::team::build_mon\` panics, \`vgc_engine.BattlePool.register_team\`
//! raises) rather than battled with the effect silently missing. Unported moves: \`moves_table::MOVE_PORTED\`.
//! Implemented means engine-core names the id, or it's a Mega Stone, or Showdown gives it no battle effect (no handler, and
//! nothing tests for it by name: lib/sim-coded.js).

${use_('abilities_table', 'ability_ids', 'AbilityId', abilityIds)}
${use_('items_table', 'item_ids', 'ItemId', itemIds)}

pub const UNPORTED_ABILITIES: &[AbilityId] = &[
${abilityIds}
];

pub const UNPORTED_ITEMS: &[ItemId] = &[
${itemIds}
];

pub fn ability_supported(id: AbilityId) -> bool {
    !UNPORTED_ABILITIES.contains(&id)
}

pub fn item_supported(id: ItemId) -> bool {
    !UNPORTED_ITEMS.contains(&id)
}
`;
	fs.writeFileSync(path.join(ROOT, 'crates', 'engine-data', 'src', 'support_table.rs'), rust);
}

main();
