'use strict';


const { Battle } = require('../lib/showdown');
const [file, from = '1', to = '9999'] = process.argv.slice(2);
const scenario = require(require('path').resolve(file));
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
battle.choose('p1', 'team 1234');
battle.choose('p2', 'team 1234');
scenario.turns.forEach((step, k) => {
	const n = k + 1;
	const start = battle.log.length;
	for (const id of ['p1', 'p2']) if (step[id] !== 'pass, pass') battle.choose(id, step[id]);
	if (n >= +from && n <= +to) {
		console.log(`--- step ${n}: p1 "${step.p1}" p2 "${step.p2}"`);
		for (const line of battle.log.slice(start)) if (!line.startsWith('|split|') && line !== '|') console.log(line);
	}
});
