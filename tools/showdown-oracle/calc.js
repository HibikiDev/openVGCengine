'use strict';










const fs = require('fs');
const { Battle, Dex } = require('./lib/showdown');

const FORMAT = 'gen9championsvgc2026regmcbo3';
const FILLER = { species: 'Snorlax', item: '', ability: 'Gluttony', nature: 'Serious', evs: { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 }, moves: ['Rest'], level: 50 };
const tr = (x, bits) => (bits ? (x >>> 0) % (2 ** bits) : Math.trunc(x));

function statOf(base, pts, nature, stat) {
	if (stat === 'hp') return base.hp + pts + 75;
	let v = base[stat] + pts + 20;
	const n = Dex.natures.get(nature);
	if (n.plus === stat) v = tr(tr(v * 110, 16) / 100);
	else if (n.minus === stat) v = tr(tr(v * 90, 16) / 100);
	return v;
}

function setOf(s) {
	return { name: s.species, species: s.species, item: s.item || '', ability: s.ability || '', nature: s.nature || 'Serious',
		evs: Object.assign({ hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 }, s.evs || {}), moves: s.moves || ['Tackle'], level: 50, gender: s.gender || '' };
}

function run(c) {
	const battle = new Battle({ formatid: FORMAT, seed: [1, 2, 3, 4], p1: { name: 'A', team: [setOf(c.atk), FILLER] }, p2: { name: 'D', team: [setOf(c.def), FILLER] } });
	battle.choose('p1', 'team 12');
	battle.choose('p2', 'team 12');
	const src = battle.p1.active[0], tgt = battle.p2.active[0];
	if (c.atkForme && c.atkForme !== src.species.name) src.formeChange(c.atkForme, src.getItem(), true);
	if (c.defForme && c.defForme !== tgt.species.name) tgt.formeChange(c.defForme, tgt.getItem(), true);

	const base = tgt.species.baseStats;
	for (const st of ['def', 'spd']) {
		const f = statOf(base, setOf(c.def).evs[st], setOf(c.def).nature, st);
		if (f !== tgt.storedStats[st]) throw new Error(`stat formula mismatch: ${tgt.species.name} ${st} sim ${tgt.storedStats[st]} formula ${f}`);
	}
	battle.field.clearWeather();
	const filler = battle.p1.active[1];
	if (c.weather) battle.field.setWeather(c.weather.toLowerCase().replace(/[^a-z]/g, ''), filler);
	battle.field.clearTerrain();
	if (c.terrain) battle.field.setTerrain(c.terrain.toLowerCase().replace(/[^a-z]/g, ''), filler);
	for (const sc of c.screens || []) battle.p2.addSideCondition(sc.toLowerCase().replace(/[^a-z]/g, ''), battle.p2.active[1]);
	for (const [mon, b] of [[src, c.atkBoosts], [tgt, c.defBoosts]]) {
		mon.clearBoosts();
		for (const [k, v] of Object.entries(b || {})) mon.boosts[k] = v;
	}
	if (c.hh) src.addVolatile('helpinghand');
	const fresh = () => {
		let move = battle.dex.getActiveMove(c.move);
		battle.activeMove = move; battle.activePokemon = src; battle.activeTarget = tgt;
		battle.singleEvent('ModifyType', move, null, src, tgt, move, move);
		battle.singleEvent('ModifyMove', move, null, src, tgt, move, move);
		move = battle.runEvent('ModifyType', src, tgt, move, move);
		move = battle.runEvent('ModifyMove', src, tgt, move, move);
		move.willCrit = false;
		if (c.spread) move.spreadHit = true;

		if (['protean', 'libero'].includes(src.ability) && move.type !== '???' && src.getTypes().join() !== move.type) src.setType(move.type);
		return move;
	};
	const rolls = () => {
		const out = [];
		for (let r = 0; r < 16; r++) {
			battle.random = () => r;
			const move = fresh();
			battle.activeMove = move; battle.activePokemon = src; battle.activeTarget = tgt;
			const d = battle.actions.getDamage(src, tgt, move);
			battle.log.length = 0; battle.sentLogPos = 0;
			out.push(typeof d === 'number' ? d : 0);
		}
		return out;
	};
	const mv = fresh();
	const res = { move: c.move, type: mv.type, category: mv.category, atk: { forme: src.species.name, atk: src.storedStats.atk, spa: src.storedStats.spa, spe: src.storedStats.spe },
		def: { forme: tgt.species.name, hp: tgt.maxhp, def: tgt.storedStats.def, spd: tgt.storedStats.spd, spe: tgt.storedStats.spe }, rolls: rolls(), candidates: [], atkCandidates: [] };
	const keep = { maxhp: tgt.maxhp, def: tgt.storedStats.def, spd: tgt.storedStats.spd };
	for (const cand of c.candidates || []) {
		const nat = cand.nature || setOf(c.def).nature;
		const hp = statOf(base, cand.hp, nat, 'hp');
		tgt.maxhp = tgt.hp = hp;
		tgt.storedStats.def = statOf(base, cand.def, nat, 'def');
		tgt.storedStats.spd = statOf(base, cand.spd, nat, 'spd');
		res.candidates.push({ ...cand, hpStat: hp, defStat: tgt.storedStats.def, spdStat: tgt.storedStats.spd, rolls: rolls() });
	}
	tgt.maxhp = tgt.hp = keep.maxhp; tgt.storedStats.def = keep.def; tgt.storedStats.spd = keep.spd;

	const abase = src.species.baseStats;
	for (const cand of c.atkCandidates || []) {
		const nat = cand.nature || setOf(c.atk).nature;
		const a0 = src.storedStats.atk, s0 = src.storedStats.spa;
		src.storedStats.atk = statOf(abase, cand.atk, nat, 'atk');
		src.storedStats.spa = statOf(abase, cand.spa, nat, 'spa');
		res.atkCandidates.push({ ...cand, atkStat: src.storedStats.atk, spaStat: src.storedStats.spa, rolls: rolls() });
		src.storedStats.atk = a0; src.storedStats.spa = s0;
	}
	return res;
}

const cases = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const out = cases.map(c => { try { return run(c); } catch (e) { return { error: String(e && e.message || e) }; } });
process.stdout.write(JSON.stringify(out));
