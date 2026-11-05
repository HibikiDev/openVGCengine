'use strict';


























const fs = require('fs');
const { Battle } = require('./lib/showdown');
const { startTrace } = require('./lib/rng-trace');
const { legalChoices } = require('./lib/legal-probe');

function snapshotPokemon(p) {
	return {
		species: p.species.name,
		hp: p.hp,
		maxhp: p.maxhp,
		fainted: p.fainted,
		status: p.status || '',
		boosts: { ...p.boosts },
		pp: p.moveSlots.map(m => m.pp),
		item: p.item || '',
		ability: p.ability,
		types: typeof p.getTypes === 'function' ? p.getTypes() : p.types,
		stats: { ...p.storedStats },
		position: p.position,
		isActive: p.isActive,
	};
}

function snapshotSideConditions(side) {



	const conds = {};
	for (const [id, cond] of Object.entries(side.sideConditions)) {
		conds[id] = { layers: cond.layers || 0 };
	}
	return conds;
}

function snapshotBattle(battle) {
	return {
		turn: battle.turn,
		ended: battle.ended,
		winner: battle.winner || null,
		weather: battle.field.weather || '',
		terrain: battle.field.terrain || '',
		pseudoWeather: Object.keys(battle.field.pseudoWeather || {}),



		sides: battle.sides.map(side => {
			const teamIndex = p => side.team.indexOf(p.set);
			const ordered = [...side.pokemon].sort((a, b) => teamIndex(a) - teamIndex(b));
			return {
			id: side.id,
			active: side.active.map(p => (p ? teamIndex(p) : null)),
			pokemon: ordered.map(snapshotPokemon),
			sideConditions: snapshotSideConditions(side),
			};
		}),
	};
}

function runScenario(scenarioPath, probeLegal, withLog) {
	const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));

	const battle = new Battle({
		formatid: scenario.format,
		seed: scenario.seed,
		p1: { name: 'p1', team: scenario.team1 },
		p2: { name: 'p2', team: scenario.team2 },
	});

	const snapshots = [];
	const legal = [];

	function choose(side, input) {

		if (input.trim() === 'pass, pass') return;
		if (!battle.choose(side, input)) {
			throw new Error(`choice rejected: ${side} "${input}"\n${battle.inputLog.join('\n')}`);
		}
	}






	const { trace, stop } = startTrace();
	try {

		choose('p1', 'team 1234');
		choose('p2', 'team 1234');
		snapshots.push({ ...snapshotBattle(battle), rngLen: trace.length });

		for (const turnChoices of scenario.turns) {
			if (probeLegal) {
				const drawsBefore = trace.length;
				legal.push({ p1: legalChoices(battle, battle.p1), p2: legalChoices(battle, battle.p2) });
				if (trace.length !== drawsBefore) throw new Error(`probing legal choices drew from the RNG at step ${legal.length}`);
			}
			choose('p1', turnChoices.p1);
			choose('p2', turnChoices.p2);
			snapshots.push({ ...snapshotBattle(battle), rngLen: trace.length });
		}
	} finally {
		stop();
	}


	const log = withLog ? { log: battle.log } : {};
	return { scenario: scenarioPath, snapshots, legal, rng_trace: trace, ...log };
}

function main() {
	const probeLegal = !process.argv.includes('--no-legal');
	const withLog = process.argv.includes('--log');


	if (process.argv.includes('--serve')) {
		const rl = require('readline').createInterface({ input: process.stdin, terminal: false });
		rl.on('line', line => {
			if (!line.trim()) return;
			let out;
			try {
				out = JSON.stringify(runScenario(line.trim(), probeLegal, withLog));
			} catch (e) {
				out = JSON.stringify({ error: String((e && e.stack) || e) });
			}
			process.stdout.write(out + '\n');
		});
		return;
	}
	const scenarioPath = process.argv[2];
	if (!scenarioPath) throw new Error('usage: node scripted.js <scenario.json> | --serve');
	console.log(JSON.stringify(runScenario(scenarioPath, probeLegal, withLog), null, 2));
}

main();
