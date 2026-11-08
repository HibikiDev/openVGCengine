







'use strict';
const fs = require('fs');
const path = require('path');

const logArg = process.argv.find(a => a.startsWith("--log="));
const [src, turnArg, specPath, serverDir] = process.argv.slice(2).filter(a => !a.startsWith("--"));
if (!src || !turnArg || !specPath) {
	console.error('usage: node check_position.js <game.log.json> <turn> <spec.json> [<buddy server dir>]');
	process.exit(2);
}
const turn = parseInt(turnArg, 10);
const dir = path.resolve(serverDir || path.join(__dirname, '../../trainer/runs/buddy_server'));
const {BattleStream} = require(path.join(dir, 'dist/sim/battle-stream'));
global.Dex = require(path.join(dir, 'dist/sim')).Dex;
const {Teams} = require(path.join(dir, 'dist/sim'));
global.Chat = {ErrorMessage: class extends Error {}};
const plugin = require('./position-plugin.js');

const spec = plugin.check(JSON.parse(fs.readFileSync(specPath, 'utf8')));


const built = new BattleStream({noCatch: true});
const P = spec.players;
for (const line of [
	`>start ${JSON.stringify({formatid: spec.format})}`,
	`>player p1 ${JSON.stringify({name: P.p1.name, team: P.p1.team})}`,
	`>player p2 ${JSON.stringify({name: P.p2.name, team: P.p2.team})}`,
	...(spec.ots ? ['>show-openteamsheets'] : []),
	`>p1 team ${P.p1.order.join(',')}`, `>p2 team ${P.p2.order.join(',')}`,
]) built._writeLines(line);
const B = built.battle;
plugin.apply(B, {mons: spec.mons, sides: spec.sides, field: spec.field, ghost: spec.ghost, turn: spec.turn});



let R = B;
if (src !== '-') {
	const game = JSON.parse(fs.readFileSync(src, 'utf8'));
	const real = new BattleStream({noCatch: true});
	for (const line of game.inputLog) {
		if (/^>p\d /.test(line) && real.battle && real.battle.turn >= turn) break;
		real._writeLines(line);
	}
	R = real.battle;
	if (!R || R.turn < turn) {
		console.error(`check_position: the game never reached turn ${turn}`);
		process.exit(2);
	}
}

const key = p => p.baseSpecies.baseSpecies.toLowerCase();
const diffs = [];
let mons = 0, exactHp = 0, hpOff = [], statOff = [];
for (const sid of ['p1', 'p2']) {
	const rs = R[sid], bs = B[sid];
	for (const r of rs.pokemon) {
		const b = bs.pokemon.find(x => key(x) === key(r));
		const tag = `${sid} ${r.name}`;
		if (!b) {
			diffs.push(`${tag}: not brought in the rebuild`);
			continue;
		}
		mons++;
		const d = [];
		if (r.fainted !== b.fainted) d.push(`fainted ${r.fainted} vs ${b.fainted}`);
		if (!r.fainted) {
			const rp = r.hp / r.maxhp, bp = b.hp / b.maxhp;
			if (r.hp === b.hp && r.maxhp === b.maxhp) exactHp++;
			hpOff.push(Math.abs(rp - bp));
			if (r.hp !== b.hp || r.maxhp !== b.maxhp) d.push(`HP ${r.hp}/${r.maxhp} vs ${b.hp}/${b.maxhp}`);
			const so = ['atk', 'def', 'spa', 'spd', 'spe'].filter(s => r.storedStats[s] !== b.storedStats[s]);
			statOff.push(so.length + (r.maxhp !== b.maxhp ? 1 : 0));
			if (so.length) d.push('stats ' + so.map(s => `${s} ${r.storedStats[s]}/${b.storedStats[s]}`).join(' '));
			if (r.status !== b.status) d.push(`status '${r.status}' vs '${b.status}'`);
			if (r.isActive !== b.isActive) d.push(`active ${r.isActive} vs ${b.isActive}`);
			else if (r.isActive && r.position !== b.position) d.push(`slot ${r.position} vs ${b.position}`);
			if (r.isActive) {
				const bo = Object.keys(r.boosts).filter(k => r.boosts[k] !== b.boosts[k]);
				if (bo.length) d.push('boosts ' + bo.map(k => `${k} ${r.boosts[k]}/${b.boosts[k]}`).join(' '));


				const since = p => [`activeTurns ${p.activeTurns}`, `acted ${p.activeMoveActions > 0}`, `lastMove ${p.lastMove ? p.lastMove.id : '-'}`,
					`timesAttacked ${p.timesAttacked}`, `lastFailed ${p.moveLastTurnResult === false}`, `fallen ${p.abilityState.fallen || 0}`];
				const rs_ = since(r), bs_ = since(b);
				const sd = rs_.map((x, k) => x !== bs_[k] ? `${x}/${bs_[k].split(' ')[1]}` : null).filter(Boolean);
				if (sd.length) d.push('since ' + sd.join(' '));
				const vs = p => Object.entries(p.volatiles).map(([k, v]) => k + (v.counter ? `x${v.counter}` : '') + (v.duration ? `:${v.duration}` : '')).sort().join(',');
				const rv = vs(r), bv = vs(b);
				if (rv !== bv) d.push(`volatiles [${rv}] vs [${bv}]`);
			}
			if (r.item !== b.item) d.push(`item '${r.item}' vs '${b.item}'`);
			if (r.ability !== b.ability) d.push(`ability '${r.ability}' vs '${b.ability}'`);
			if (r.species.id !== b.species.id) d.push(`forme ${r.species.id} vs ${b.species.id}`);
			if ((r.terastallized || '') !== (b.terastallized || '')) d.push(`tera '${r.terastallized || ''}' vs '${b.terastallized || ''}'`);
			const ms = p => p.moveSlots.map(m => `${m.id}:${m.pp}`).sort().join(' ');
			const rm = ms(r), bm = ms(b);
			if (rm !== bm) d.push(`moves/PP [${rm}] vs [${bm}]`);
		}
		if (d.length) diffs.push(`${tag}: ${d.join('; ')}`);
	}
	const sc = s => Object.entries(s.sideConditions).map(([k, v]) => `${k}${v.layers ? 'x' + v.layers : ''}:${v.duration || '-'}`).sort().join(' ');
	if (sc(rs) !== sc(bs)) diffs.push(`${sid} side: [${sc(rs)}] vs [${sc(bs)}]`);
	if (rs.pokemonLeft !== bs.pokemonLeft) diffs.push(`${sid} mons left ${rs.pokemonLeft} vs ${bs.pokemonLeft}`);
	if (rs.totalFainted !== bs.totalFainted) diffs.push(`${sid} fainted so far ${rs.totalFainted} vs ${bs.totalFainted}`);
	if (rs.pokemon.some(p => p.canMegaEvo) !== bs.pokemon.some(p => p.canMegaEvo)) diffs.push(`${sid} Mega still available differs`);
}
const fieldOf = f => [`weather ${f.weather || '-'}:${f.weather ? f.weatherState.duration : '-'}`, `terrain ${f.terrain || '-'}:${f.terrain ? f.terrainState.duration : '-'}`,
	...Object.entries(f.pseudoWeather).map(([k, v]) => `${k}:${v.duration}`)].join(' ');
if (fieldOf(R.field) !== fieldOf(B.field)) diffs.push(`field: [${fieldOf(R.field)}] vs [${fieldOf(B.field)}]`);
if (R.turn !== B.turn) diffs.push(`turn ${R.turn} vs ${B.turn}`);

console.log(`turn ${turn}: real vs rebuilt (${src.split(/[\\/]/).pop()})`);
for (const d of diffs) console.log('  ' + d);
const mean = a => a.length ? a.reduce((x, y) => x + y, 0) / a.length : 0;
console.log(`summary: ${mons} brought mons; HP exact on ${exactHp} of ${hpOff.length} alive, mean off ${(100 * mean(hpOff)).toFixed(2)}% ` +
	`of max; stats off on ${statOff.filter(Boolean).length} of ${statOff.length}; ${diffs.length} lines differ`);




const shown = [];
for (let k = 0; k < B.log.length; k++) {
	if (B.log[k].startsWith('|split|')) { shown.push(B.log[k + 2]); k += 2; continue; }
	shown.push(B.log[k]);
}
const known = new Set();
let unknown = 0;
for (const ln of shown) {
	const p = ln.split('|');
	if (['switch', 'drag', 'replace'].includes(p[1])) { known.add(p[2].replace(/^(p\d)[a-z]:/, '$1:')); continue; }
	if (['poke', 'player', 'showteam', 'teamsize', 'j', 'J', 'l', 'L', 'c', 'raw', 'html', 'uhtml', ''].includes(p[1])) continue;
	for (const x of p.slice(2)) {
		const m = /^(p\d)[a-z]?: (.+)$/.exec(x.replace(/^\[of\] /, ''));
		if (!m || B.sides.some(s => `${s.id}: ${s.name}` === x)) continue;
		if (!known.has(`${m[1]}: ${m[2]}`)) {
			unknown++;
			console.log(`  display: a line names a mon the client hasn't seen: ${ln}`);
		}
	}
}



const client = {p1: [], p2: []};
const active = {p1: [], p2: []};
const check = (mon, details) => {
	if (details === mon.details) return true;
	if (mon.searchid) return false;
	if (details.includes(', shiny') && check(mon, details.replace(', shiny', ''))) return true;
	return details.replace(/(-[A-Za-z0-9-]+)?(, |$)/, '-*$2') === mon.details;
};
let extra = 0;
for (const ln of shown) {
	const p = ln.split('|');
	if (p[1] === 'poke') client[p[2]].push({details: p[3], searchid: '', fainted: false});
	if (p[1] === 'showteam') {
		client[p[2]] = Teams.unpack(p.slice(3).join('|')).map(s => ({details: s.species + (!s.level || s.level === 100 ? '' : `, L${s.level}`) +
			(!s.gender || s.gender === 'N' ? '' : `, ${s.gender}`) + (s.shiny ? ', shiny' : ''), searchid: '', fainted: false}));
	}
	if (['switch', 'drag'].includes(p[1])) {
		const sid = p[2].slice(0, 2), slot = p[2].charCodeAt(2) - 97, id = `${sid}: ${p[2].split(': ')[1]}`, searchid = `${id}|${p[3]}`;
		let mon = client[sid].find(x => !x.fainted && !active[sid].includes(x) && (x.searchid === searchid || (!x.searchid && check(x, p[3]))));
		if (!mon) {
			mon = {details: p[3], searchid, fainted: false};
			client[sid].push(mon);
			if (client[sid].length > 6) { extra++; console.log(`  display: the client takes this switch-in for a new mon: ${ln}`); }
		}
		Object.assign(mon, {details: p[3], searchid});
		active[sid][slot] = mon;
	}
	if (p[1] === 'detailschange') {
		const sid = p[2].slice(0, 2), mon = active[sid][p[2].charCodeAt(2) - 97];
		if (mon) { mon.details = p[3]; mon.searchid = `${sid}: ${p[2].split(': ')[1]}|${p[3]}`; }
	}
	if (p[1] === 'faint') {
		const sid = p[2].slice(0, 2), mon = active[sid][p[2].charCodeAt(2) - 97];
		if (mon) mon.fainted = true;
	}
}
console.log(`display: ${shown.length} lines, ${unknown} naming an unseen mon, ${extra} switch-ins the client reads as a new mon`);
if (logArg) fs.writeFileSync(logArg.slice(6), shown.join('\n'));
