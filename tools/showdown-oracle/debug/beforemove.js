

const fs = require('fs');
const path = require('path');
const { Battle } = require(path.join(__dirname, '..', 'lib', 'showdown'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const onlyTurn = process.argv[3] ? Number(process.argv[3]) : null;
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
const realFind = battle.findEventHandlers.bind(battle);
battle.findEventHandlers = (target, eventName, source) => {
	const handlers = realFind(target, eventName, source);
	if (eventName === 'BeforeMove' && (onlyTurn === null || battle.turn === onlyTurn)) {
		const sorted = handlers.slice();
		battle.speedSort(sorted);
		console.log(`turn ${battle.turn} BeforeMove ${target.name}: ` + sorted.map(h =>
			`${h.effect.effectType}:${h.effect.id} p=${h.priority} s=${h.speed} sub=${h.subOrder}`).join(' | '));
	}
	return handlers;
};
for (const t of scenario.turns) {
	if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
	if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
