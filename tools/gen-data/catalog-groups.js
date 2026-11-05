'use strict';












const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const SHOWDOWN = process.env.SHOWDOWN_PATH || path.join(ROOT, 'vendor', 'pokemon-showdown');
const { Dex } = require(path.join(SHOWDOWN, 'dist', 'sim'));
const g9 = Dex.forGen(9);
const g5 = Dex.mod('gen5');
const cov = require('./out/pool-coverage.json');
const DONE = new Set(['implemented', 'referenced', 'megastone', 'no-effect']);


const legacyPool = dir => Object.fromEntries(['species', 'moves', 'abilities', 'items'].map(k => {
	const f = path.join(__dirname, 'out', dir, `${k}.json`);
	return [k, new Set(fs.existsSync(f) ? require(f).map(e => e.id) : [])];
}));
const VGC13 = legacyPool('vgc13');

const GEN6 = { vgc14: legacyPool('vgc14'), vgc15: legacyPool('vgc15'), vgc16: legacyPool('vgc16') };

const GEN7 = { vgc17: legacyPool('vgc17'), vgc18: legacyPool('vgc18'), vgc19: legacyPool('vgc19') };

const GEN9 = { svc: legacyPool('svc'), svd: legacyPool('svd'), svg: legacyPool('svg'), svi: legacyPool('svi') };

const GEN8 = { vgc20: legacyPool('vgc20'), vgc21: legacyPool('vgc21'), vgc22: legacyPool('vgc22') };
const inLegacy = (kind, id) => VGC13[kind].has(id) || [...Object.values(GEN6), ...Object.values(GEN7)].some(p => p[kind].has(id));


const MOVE_DATA = new Set(['num', 'name', 'accuracy', 'basePower', 'category', 'pp', 'priority', 'flags', 'target', 'type', 'secondary',
	'secondaries', 'boosts', 'self', 'selfBoost', 'status', 'drain', 'recoil', 'heal', 'multihit', 'multiaccuracy', 'critRatio', 'willCrit',
	'selfSwitch', 'breaksProtect', 'desc', 'shortDesc', 'contestType', 'isNonstandard', 'zMove', 'maxMove', 'gen', 'noSketch']);

function moveFamily(m) {
	if (m.isZ) return 'gimmick: Z-Move';
	if (m.isMax) return 'gimmick: Max / G-Max move';
	if (m.id === 'terablast' || m.id === 'terastarstorm') return 'gimmick: Tera';
	const keys = Object.keys(m).filter(k => !['id', 'isZ', 'isMax'].includes(k) && (!MOVE_DATA.has(k) || typeof m[k] === 'function'));
	const fn = k => typeof m[k] === 'function';
	if (!keys.length) return 'data-only (MoveData fields)';
	if (m.ohko) return 'OHKO';
	if (keys.some(k => ['basePowerCallback', 'damageCallback', 'damage'].includes(k))) return 'variable power / fixed damage';
	if (m.weather || m.terrain || m.pseudoWeather) return 'field: weather / terrain / room';
	if (m.sideCondition || m.slotCondition) return 'side / slot condition (screens, hazards, wishes)';
	if (m.volatileStatus && m.condition) return `volatile with its own condition (${m.volatileStatus})`;
	if (m.volatileStatus) return 'volatile (existing condition)';
	if (m.forceSwitch) return 'force switch';
	if (m.selfdestruct) return 'self-KO';
	if (keys.includes('onTryHit') || keys.includes('onTry') || keys.includes('onPrepareHit')) return 'custom try / fail logic';
	if (keys.includes('onHit') || keys.includes('onAfterHit') || keys.includes('onAfterMoveSecondarySelf')) return 'custom on-hit effect';
	if (keys.some(k => k.startsWith('onModify') || k === 'onBasePower' || k === 'onEffectiveness')) return 'move-time modifier (type / power / effectiveness)';
	if (keys.includes('ignoreImmunity') || keys.includes('ignoreAbility') || keys.includes('ignoreDefensive') || keys.includes('ignoreEvasion')) return 'ignores (immunity / ability / boosts)';
	if (keys.some(fn)) return 'other callback: ' + keys.filter(fn).sort().join('+');
	return 'other field: ' + keys.sort().join('+');
}


const EVENT_FAMILIES = [
	[/^on(Source)?Modify(Atk|SpA|Def|SpD|Spe|Accuracy|CritRatio|Damage|Weight|STAB)|^onBasePower|^on(Ally|Source)?BasePower|^onAnyModify|^onFoeModify/, 'stat / damage modifier'],
	[/^onModifyPriority|^onFractionalPriority/, 'priority'],
	[/^onModifyType|^onModifyMove|^onSourceModifyMove/, 'move rewriting (type / properties)'],
	[/^onEffectiveness|^onSourceEffectiveness|^onImmunity|^onTryImmunity|^onTryHit|^onAllyTryHit|^onAnyTryHit|^onFoeTryHit|^onAnyInvulnerability/, 'immunity / absorb / redirect'],
	[/^onDamagingHit|^onAfterMoveSecondary|^onSourceDamagingHit|^onAfterDamage|^onHit$/, 'when hit / after hitting'],
	[/^onBoost|^onTryBoost|^onAfterBoost|^onAfterEachBoost|^onAnyAfterBoost|^onChangeBoost|^onFoeAfterBoost/, 'stat-change interaction'],
	[/^onEat|^onTryEatItem/, 'berry / threshold trigger'],
	[/^onSwitchIn|^onStart|^onPreStart|^onEnd|^onSwitchOut|^onAnySwitchIn/, 'entry / exit'],
	[/^onUpdate/, 'state check (onUpdate)'],
	[/^onResidual/, 'end of turn'],
	[/^onSetStatus|^onAllySetStatus|^onTryAddVolatile|^onCureStatus|^onAfterSetStatus/, 'status interaction'],
	[/^onWeather|^onAnyWeather|^onTerrain|^onAnySetWeather|^onImmunity/, 'weather / terrain interaction'],
	[/^onDamage|^onSourceDamage|^onAnyDamage|^onTryHeal|^onDragOut|^onFaint|^onSourceAfterFaint|^onAnyFaint/, 'damage / heal / faint interaction'],
	[/^onTrapPokemon|^onMaybeTrapPokemon|^onFoeTrapPokemon|^onFoeMaybeTrapPokemon/, 'trapping'],
	[/^onTakeItem|^onAfterUseItem|^onFoeAfterUseItem|^onSourceTryPrimaryHit/, 'item interaction'],
];

const NOT_HANDLERS = new Set(['onPlate', 'onMemory', 'onDrive']);
function handlers(e) {
	const on = o => Object.keys(o || {}).filter(k => k.startsWith('on') && !NOT_HANDLERS.has(k));
	return [...on(e), ...on(e.condition)];
}


const simHardcoded = require('./lib/sim-coded').simCodedChecker(SHOWDOWN);

function eventFamily(fns) {
	for (const [re, fam] of EVENT_FAMILIES) if (fns.some(f => re.test(f))) return fam;
	return fns.length ? 'other: ' + fns.slice(0, 3).join('+') : 'no handler (data only)';
}

function abilityFamily(a) {
	const fns = handlers(a);
	if (a.id === 'commander') return 'sim mechanism (Commander)';
	if (!fns.length && simHardcoded(a.id, a.name)) return 'sim-hardcoded (no data handler)';
	if (a.isPermanent && fns.length === 0) return 'forme / permanent';
	return eventFamily(fns);
}

function itemFamily(i) {
	if (i.zMove) return 'gimmick: Z-Crystal';
	if (i.megaStone || i.megaEvolves) return 'Mega Stone (data)';
	if (i.isGem) return 'gem';
	if (i.onPlate || i.onMemory || i.onDrive || i.forcedForme || i.itemUser) return 'forme / type item (plates, memories, drives, orbs)';
	if (i.isBerry) return 'berry: ' + eventFamily(handlers(i));
	const fns = handlers(i);
	if (!fns.length && simHardcoded(i.id, i.name)) return 'sim-hardcoded (no data handler)';
	if (!fns.length) return i.fling ? 'fling-only / no battle effect' : 'no handler (data only)';
	return eventFamily(fns);
}

function catalog(kind) {

	const catCov = fs.existsSync(path.join(__dirname, 'out', 'catalog-coverage.json')) ? require('./out/catalog-coverage.json') : {};
	const done = new Set([...cov[kind], ...(catCov[kind] || [])].filter(x => DONE.has(x.status)).map(x => x.id));

	if (kind === 'moves') {
		const src = fs.readFileSync(path.join(__dirname, 'codegen-moves.js'), 'utf8').match(/MOVE_IDS = \[([\s\S]*?)\];/)[1];
		for (const m of src.match(/'([a-z0-9]+)'/g) || []) done.add(m.slice(1, -1));
	}
	const table = kind === 'moves' ? g9.moves : kind === 'abilities' ? g9.abilities : g9.items;
	const t5 = kind === 'moves' ? g5.moves : kind === 'abilities' ? g5.abilities : g5.items;
	const fam = kind === 'moves' ? moveFamily : kind === 'abilities' ? abilityFamily : itemFamily;
	const raw = kind === 'moves' ? g9.data.Moves : kind === 'abilities' ? g9.data.Abilities : g9.data.Items;
	const groups = {};
	const seen = new Set();
	for (const e of table.all()) {
		if (!e.exists || done.has(e.id) || seen.has(e.id)) continue;
		seen.add(e.id);
		const tier = !e.isNonstandard ? 'sv' : e.isNonstandard === 'Past' ? 'past' : inLegacy(kind, e.id) ? 'legacy' : null;
		if (!tier) continue;
		const e5 = t5.get(e.id);
		const in5 = !!(e5 && e5.exists && !e5.isNonstandard);
		const def = Object.assign({}, raw[e.id] || {}, { id: e.id, isZ: e.isZ, isMax: e.isMax, zMove: (raw[e.id] || {}).zMove });
		const f = fam(kind === 'moves' ? def : Object.assign({}, raw[e.id] || {}, { id: e.id }));
		(groups[f] = groups[f] || []).push({ id: e.id, tier, gen5: in5, vgc13: VGC13[kind].has(e.id),
			...Object.fromEntries([...Object.entries(GEN6), ...Object.entries(GEN7), ...Object.entries(GEN8), ...Object.entries(GEN9)].map(([k, p]) => [k, p[kind].has(e.id)])) });
	}
	return groups;
}

function speciesGap() {
	const done = new Set(require('./ids/species.json'));
	const sv = [], past = [], gen5only = [];
	for (const s of g9.species.all()) {
		if (!s.exists || done.has(s.id)) continue;
		if (!s.isNonstandard) sv.push(s.id);
		else if (s.isNonstandard === 'Past') past.push(s.id);
	}
	for (const s of g5.species.all()) {
		if (s.exists && !s.isNonstandard && !done.has(s.id) && !sv.includes(s.id) && !past.includes(s.id)) gen5only.push(s.id);
	}
	return { implemented: done.size, sv: sv.length, past: past.length, gen5_extra: gen5only.length, sv_ids: sv, past_ids: past };
}

function main() {
	const out = { generated: new Date().toISOString(), species: speciesGap() };
	for (const kind of ['moves', 'abilities', 'items']) {
		const g = catalog(kind);
		out[kind] = Object.fromEntries(Object.entries(g).sort((a, b) => b[1].length - a[1].length));
		const n = Object.values(g).flat();
		console.log(`\n${kind}: ${n.length} missing (SV ${n.filter(x => x.tier === 'sv').length}, Past ${n.filter(x => x.tier === 'past').length}; in Gen 5 ${n.filter(x => x.gen5).length}; VGC13 ${n.filter(x => x.vgc13).length}; VGC14 ${n.filter(x => x.vgc14).length}; VGC15 ${n.filter(x => x.vgc15).length}; VGC16 ${n.filter(x => x.vgc16).length}; VGC17 ${n.filter(x => x.vgc17).length}; VGC18 ${n.filter(x => x.vgc18).length}; VGC19 ${n.filter(x => x.vgc19).length}; Reg C ${n.filter(x => x.svc).length}; Reg D ${n.filter(x => x.svd).length}; Reg G ${n.filter(x => x.svg).length}; Reg I ${n.filter(x => x.svi).length}; VGC20 ${n.filter(x => x.vgc20).length}; VGC21 ${n.filter(x => x.vgc21).length}; VGC22 ${n.filter(x => x.vgc22).length})`);
		for (const [f, xs] of Object.entries(out[kind])) {
			console.log(`  ${String(xs.length).padStart(4)}  ${f}  [SV ${xs.filter(x => x.tier === 'sv').length}, VGC13 ${xs.filter(x => x.vgc13).length}, VGC15 ${xs.filter(x => x.vgc15).length}]  e.g. ${xs.slice(0, 4).map(x => x.id).join(', ')}`);
		}
	}
	const s = out.species;
	console.log(`\nspecies: registered ${s.implemented} (data only: a species needs no port of its own); missing SV ${s.sv}, Past ${s.past}, Gen-5-only extra ${s.gen5_extra}`);
	fs.writeFileSync(path.join(__dirname, 'out', 'catalog-groups.json'), JSON.stringify(out, null, 1));
}

main();
