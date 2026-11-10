




'use strict';
const fs = require('fs');
const path = require('path');

const [specPath, serverDir] = process.argv.slice(2);
const dir = path.resolve(serverDir || path.join(__dirname, '../../trainer/runs/buddy_server'));
const {BattleStream} = require(path.join(dir, 'dist/sim/battle-stream'));
global.Dex = require(path.join(dir, 'dist/sim')).Dex;
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
const out = {turn: B.turn, field: {weather: B.field.weather, weatherTurns: B.field.weatherState.duration || 0,
	terrain: B.field.terrain, terrainTurns: B.field.terrainState.duration || 0,
	pseudo: Object.fromEntries(Object.entries(B.field.pseudoWeather).map(([k, v]) => [k, v.duration || 0]))}, sides: {}};


const id = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '');
out.shown = {weather: '', terrain: ''};
for (const ln of B.log) {
	const w = /^\|-weather\|([^|]*)/.exec(ln);
	if (w) out.shown.weather = w[1] === 'none' ? '' : id(w[1]);
	const t = /^\|-field(start|end)\|(?:move: )?([^|]*)/.exec(ln);
	if (t && id(t[2]).endsWith('terrain')) out.shown.terrain = t[1] === 'start' ? id(t[2]) : '';
}
for (const side of B.sides) {
	out.sides[side.id] = {
		conds: Object.fromEntries(Object.entries(side.sideConditions).map(([k, v]) => [k, v.duration || v.layers || 1])),
		mons: side.pokemon.map(p => ({species: p.species.name, hp: p.hp, maxhp: p.maxhp, status: p.status || '', boosts: p.boosts,
			item: p.item, active: p.isActive ? p.position : null, pp: Object.fromEntries(p.moveSlots.map(m => [m.id, m.pp])),
			volatiles: Object.keys(p.volatiles)})),
	};
}
console.log(JSON.stringify(out));
