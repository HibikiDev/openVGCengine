#!/usr/bin/env node
'use strict';





















const fs = require('fs');
const path = require('path');
const zlib = require('zlib');
const { Dex, TeamValidator } = require(path.join(__dirname, '..', '..', 'vendor', 'pokemon-showdown', 'dist', 'sim'));

const args = {};
for (let i = 2; i < process.argv.length; i++) {
	const a = process.argv[i];
	if (a.startsWith('--')) args[a.slice(2)] = process.argv[++i];
}
const format = args.format;
const files = (args.stats || '').split(',').filter(Boolean);
const count = Number(args.count || 200);
const minUsage = Number(args['min-usage'] || 0.005);
const coherent = Boolean(args['species-lists']);
const gmaxDefault = 'gmax-default' in args;
if (!format || !files.length || !args.out) throw new Error('usage: --format F --stats a,b --out path');
const validator = TeamValidator.get(format);
const dex = Dex.forFormat(Dex.formats.get(format));


function withGmax(team) {
	if (!gmaxDefault) return team;
	for (const set of team) if (dex.species.get(set.species).canGigantamax) set.gigantamax = true;
	for (const p of validator.validateTeam(team.map(x => ({ ...x }))) || []) {
		const set = team.find(x => x.gigantamax && p.startsWith(`${dex.species.get(x.species).name} is flagged as gigantamax`));
		if (set) delete set.gigantamax;
	}
	return team;
}


let s = Number(args.seed || 1) >>> 0;
const rand = () => {
	s = (s + 0x6d2b79f5) >>> 0;
	let t = s;
	t = Math.imul(t ^ (t >>> 15), t | 1);
	t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
	return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
};
const num = v => (typeof v === 'number' && Number.isFinite(v) ? v : 0);
const pick = (entries) => {
	const total = entries.reduce((a, [, w]) => a + w, 0);
	if (total <= 0) return null;
	let r = rand() * total;
	for (const [k, w] of entries) if ((r -= w) <= 0) return k;
	return entries[entries.length - 1][0];
};


const species = new Map();
let slots = 0;
for (const f of files) {
	const raw = fs.readFileSync(f);
	const doc = JSON.parse((f.endsWith('.gz') ? zlib.gunzipSync(raw) : raw).toString('utf8'));
	for (const [name, mon] of Object.entries(doc.data || {})) {
		if (!mon || typeof mon !== 'object') continue;
		const w = Object.values(mon.Abilities || {}).reduce((a, v) => a + num(v), 0);
		if (w <= 0) continue;
		slots += w;
		const acc = species.get(name) || { w: 0, Abilities: {}, Items: {}, Moves: {}, Spreads: {}, Teammates: {} };
		acc.w += w;
		for (const kind of ['Abilities', 'Items', 'Moves', 'Spreads', 'Teammates']) {
			for (const [k, v] of Object.entries(mon[kind] || {})) acc[kind][k] = (acc[kind][k] || 0) + num(v);
		}
		species.set(name, acc);
	}
}
const pool = [...species].filter(([, m]) => m.w / slots * 6 >= minUsage);
const usage = new Map(pool.map(([n, m]) => [n, m.w / slots * 6]));

const HP_TYPES = ['fighting', 'flying', 'poison', 'ground', 'rock', 'bug', 'ghost', 'steel', 'fire', 'water', 'grass', 'electric',
	'psychic', 'ice', 'dragon', 'dark'];
function hpIvs(type) {
	const order = ['hp', 'atk', 'def', 'spe', 'spa', 'spd'];
	const cost = { hp: 1, atk: 2, def: 1, spe: 6, spa: 2, spd: 1 };
	let best = null, bestCost = Infinity;
	for (let mask = 0; mask < 64; mask++) {
		const low = order.map((_, i) => (mask >> i) & 1);
		const t = Math.floor((low[0] + 2 * low[1] + 4 * low[2] + 8 * low[3] + 16 * low[4] + 32 * low[5]) * 15 / 63);
		const c = order.reduce((a, k, i) => a + (low[i] ? 0 : cost[k]), 0);
		if (HP_TYPES[t] === type && c < bestCost) { best = low; bestCost = c; }
	}
	return Object.fromEntries(order.map((k, i) => [k, best[i] ? 31 : 30]));
}

function makeSet(name, usedItems, forcedItem = null) {
	const m = species.get(name);
	const ability = pick(Object.entries(m.Abilities).filter(([, w]) => w > 0));
	const items = Object.entries(m.Items).filter(([k, w]) => w > 0 && k !== 'nothing' && !usedItems.has(k));
	const item = forcedItem || (items.length ? pick(items) : '');
	const moves = [];

	const attacksOnly = /^choice/.test(item) || item === 'assaultvest';
	let cands = Object.entries(m.Moves).filter(([k, w]) => w > 0 && k && k !== 'nothing' &&
		!(attacksOnly && dex.moves.get(k).category === 'Status'));


	let spread = null;
	if (coherent) {
		spread = pick(Object.entries(m.Spreads).filter(([, w]) => w > 0)) || 'Serious:0/0/0/0/0/0';
		const { plus, minus } = dex.natures.get(spread.split(':')[0]);
		const off = item === 'choiceband' || plus === 'atk' || minus === 'spa' ? 'Special'
			: item === 'choicespecs' || plus === 'spa' || minus === 'atk' ? 'Physical' : null;
		if (off) cands = cands.map(([k, w]) => [k, dex.moves.get(k).category === off ? w * 0.1 : w]);
	}
	while (moves.length < 4 && cands.length) {
		const mv = pick(cands);
		moves.push(mv);
		const hp = mv.startsWith('hiddenpower');
		cands = cands.filter(([k]) => k !== mv && !(hp && k.startsWith('hiddenpower')));
	}
	spread = spread || pick(Object.entries(m.Spreads).filter(([, w]) => w > 0)) || 'Serious:0/0/0/0/0/0';
	const [nature, evs] = spread.split(':');
	const e = evs.split('/').map(Number);
	const set = {
		species: name, item: item ? dex.items.get(item).name : '', ability: dex.abilities.get(ability).name,
		moves: moves.map(id => dex.moves.get(id).name), nature,
		evs: { hp: e[0], atk: e[1], def: e[2], spa: e[3], spd: e[4], spe: e[5] }, level: 50,
	};
	const hp = moves.find(id => id.startsWith('hiddenpower') && id.length > 'hiddenpower'.length);
	if (hp) set.ivs = hpIvs(hp.slice('hiddenpower'.length));
	return { set, item };
}

function makeTeam() {
	const team = [], names = [], nums = new Set(), usedItems = new Set();
	while (team.length < 6) {
		const cands = [];
		for (const [n] of pool) {
			const sp = dex.species.get(n);
			if (!sp.exists || nums.has(sp.num)) continue;
			let score = usage.get(n);
			if (names.length) {
				const dev = names.reduce((a, c) => a + num(species.get(c).Teammates[n]) / species.get(c).w, 0) / names.length;
				score += dev;
			}
			cands.push([n, Math.max(score, 1e-4)]);
		}
		const n = pick(cands);
		if (!n) return null;
		const { set, item } = makeSet(n, usedItems);
		team.push(set);
		names.push(n);
		nums.add(dex.species.get(n).num);
		if (item) usedItems.add(item);
	}
	return team;
}


function listTeam(slugs) {
	const mons = slugs.map(slug => {
		const sp = dex.species.get(slug.replace(/-/g, ''));
		if (!sp.exists) throw new Error(`unknown species ${slug}`);
		const isMega = sp.forme && sp.forme.startsWith('Mega');
		const name = species.has(sp.name) ? sp.name : sp.baseSpecies;
		if (!species.has(name)) throw new Error(`${slug}: no stats for ${sp.name} / ${sp.baseSpecies}`);
		return { name, forced: isMega ? dex.items.get(sp.requiredItem).id : null };
	});
	const usedItems = new Set(mons.filter(m => m.forced).map(m => m.forced));
	return mons.map(m => {
		const { set, item } = makeSet(m.name, usedItems, m.forced);
		if (item) usedItems.add(item);
		return set;
	});
}

const teams = [];
const seen = new Set();
let tries = 0;
if (args['species-lists']) {
	const doc = JSON.parse(fs.readFileSync(args['species-lists'], 'utf8'));
	let skipped = 0, failed = 0;
	for (const l of doc.lists) {
		const key = [...l.species].sort().join('|');
		if (l.team_id || seen.has(key)) { skipped++; continue; }
		let team = null;
		for (let k = 0; k < 200 && !team; k++) {
			const t = withGmax(listTeam(l.species));
			if (!validator.validateTeam(t)) team = t;
		}
		if (!team) { failed++; console.log(`list ${l.event}#${l.place} (${l.species.join(', ')}): no valid draw`); continue; }
		seen.add(key);
		teams.push({ id: `${args.prefix || 'L'}-${l.event}-${l.place}`, sets: team });
	}
	const out = { format, source: `usage-teams.js --species-lists ${path.basename(args['species-lists'])} --seed ${args.seed || 1} from ${files.map(f => path.basename(path.dirname(f)) + '/' + path.basename(f)).join(', ')}`, teams };
	fs.writeFileSync(args.out, JSON.stringify(out, null, '\t') + '\n');
	console.log(`${teams.length} teams from ${doc.lists.length} lists (${skipped} skipped: full list or repeat; ${failed} without a valid draw) -> ${args.out}`);
	process.exit(0);
}
while (teams.length < count && tries < count * 50) {
	tries++;
	const team = makeTeam();
	if (!team) continue;
	withGmax(team);
	const key = team.map(x => x.species).sort().join('|');
	if (seen.has(key)) continue;
	if (validator.validateTeam(team)) continue;
	seen.add(key);
	teams.push({ id: `${args.prefix || 'U'}-${teams.length + 1}`, sets: team });
}
const out = { format, source: `usage-teams.js --seed ${args.seed || 1} from ${files.map(f => path.basename(path.dirname(f)) + '/' + path.basename(f)).join(', ')}`, teams };
fs.writeFileSync(args.out, JSON.stringify(out, null, '\t') + '\n');
console.log(`${teams.length} teams (${tries} drawn; ${pool.length} species >= ${minUsage} usage) -> ${args.out}`);
