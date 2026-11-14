


const fs = require('fs');
const path = require('path');
const { Battle } = require(path.join(__dirname, '..', 'lib', 'showdown'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const want = process.argv[3];
const onlyTurn = process.argv[4] ? Number(process.argv[4]) : null;
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
const stack = [];
const realRun = battle.runEvent.bind(battle);
battle.runEvent = (eventid, ...rest) => { stack.push(eventid); try { return realRun(eventid, ...rest); } finally { stack.pop(); } };
const realSort = battle.speedSort.bind(battle);
battle.speedSort = (list, ...rest) => {
	realSort(list, ...rest);
	if (stack[stack.length - 1] === want && (onlyTurn === null || battle.turn === onlyTurn) && list.length) {
		const who = h => (h.effectHolder && h.effectHolder.name) || '-';
		console.log(`turn ${battle.turn} ${want}: ` + list.map(h =>
			`${h.effect.effectType}:${h.effect.id}@${who(h)} p=${h.priority} o=${h.order} sub=${h.subOrder} s=${h.speed}`).join(' | '));
	}
};
for (const t of scenario.turns) {
	if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
	if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
