'use strict';







const { Teams, BattleStream, getPlayerStreams } = require('./showdown');
const { RandomPlayerAI } = require('./showdown');
const { deriveSeed } = require('./seed');

const DEFAULT_FORMAT = 'gen9championsvgc2026regmc';

function snapshotPokemon(p) {
	return {
		species: p.species.name,
		nickname: p.name,
		hp: p.hp,
		maxhp: p.maxhp,
		fainted: p.fainted,
		status: p.status || '',
		statusTurns: p.statusState ? (p.statusState.turns ?? null) : null,
		boosts: { ...p.boosts },
		ability: p.ability,
		item: p.item,
		types: typeof p.getTypes === 'function' ? p.getTypes() : p.types,
		moves: p.moveSlots.map(m => ({ id: m.id, pp: m.pp, maxpp: m.maxpp, disabled: !!m.disabled })),
		position: p.position,
		isActive: p.isActive,
		terastallized: p.terastallized || null,
	};
}

function snapshotSideConditions(side) {
	const out = {};
	for (const [id, cond] of Object.entries(side.sideConditions || {})) {
		const { name, id: _id, ...rest } = cond;
		out[id] = rest;
	}
	return out;
}

function snapshotField(field) {
	return {
		weather: field.weather || '',
		weatherTurns: field.weatherState ? (field.weatherState.turns ?? null) : null,
		terrain: field.terrain || '',
		terrainTurns: field.terrainState ? (field.terrainState.turns ?? null) : null,
		pseudoWeather: Object.keys(field.pseudoWeather || {}),
	};
}

function snapshotBattle(battle, rngCalls) {
	return {
		turn: battle.turn,
		ended: battle.ended,
		winner: battle.winner || null,
		rngCalls,
		field: snapshotField(battle.field),
		sides: battle.sides.map(side => ({
			id: side.id,
			active: side.active.map(p => (p ? p.position : null)),
			sideConditions: snapshotSideConditions(side),
			pokemon: side.pokemon.map(snapshotPokemon),
		})),
	};
}









async function runBattle({ seed, format = DEFAULT_FORMAT, maxTurns = 100 }) {
	const team1 = Teams.generate(format, { seed: deriveSeed(seed, 'team1') });
	const team2 = Teams.generate(format, { seed: deriveSeed(seed, 'team2') });

	const battleStream = new BattleStream();
	const streams = getPlayerStreams(battleStream);

	const p1 = new RandomPlayerAI(streams.p1, { seed: deriveSeed(seed, 'p1policy') });
	const p2 = new RandomPlayerAI(streams.p2, { seed: deriveSeed(seed, 'p2policy') });
	void p1.start();
	void p2.start();

	const spec = { formatid: format, seed: deriveSeed(seed, 'battle') };
	const p1spec = { name: 'p1', team: Teams.pack(team1) };
	const p2spec = { name: 'p2', team: Teams.pack(team2) };

	const turns = [];
	let rngCalls = 0;
	let hooked = false;
	let forcedEnd = false;

	void streams.omniscient.write(
		`>start ${JSON.stringify(spec)}\n>player p1 ${JSON.stringify(p1spec)}\n>player p2 ${JSON.stringify(p2spec)}`
	);

	for await (const chunk of streams.omniscient) {
		if (!hooked && battleStream.battle) {
			const prng = battleStream.battle.prng;
			const origRandom = prng.random.bind(prng);
			prng.random = (...a) => {
				rngCalls++;
				return origRandom(...a);
			};
			hooked = true;
		}
		if (/\|turn\|/.test(chunk) || /\|win\|/.test(chunk) || /\|tie\|/.test(chunk)) {
			turns.push(snapshotBattle(battleStream.battle, rngCalls));
		}
		if (!forcedEnd && turns.length >= maxTurns && !battleStream.battle.ended) {
			forcedEnd = true;
			void streams.omniscient.write('>forcetie');
		}
	}

	return { seed, format, turnCount: turns.length, turns };
}

module.exports = { runBattle, DEFAULT_FORMAT };
