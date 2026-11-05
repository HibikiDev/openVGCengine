

const fs = require('fs');
const path = require('path');
const { Battle } = require(path.join(__dirname, '..', 'lib', 'showdown'));
const { startTrace } = require(path.join(__dirname, '..', 'lib', 'rng-trace'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const want = Number(process.argv[3]);
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
const { trace, stop } = startTrace();
const proto = Object.getPrototypeOf(battle);
const realSort = proto.speedSort;
let done = false;
proto.speedSort = function (list, ...rest) {
	const snapshot = list.map(h => ({
		effect: h.effect ? `${h.effect.effectType}:${h.effect.id}` : (h.choice || '?'),
		holder: h.effectHolder ? (h.effectHolder.name || h.effectHolder.id || '?') : (h.pokemon ? h.pokemon.name : ''),
		order: h.order, priority: h.priority, speed: h.speed, subOrder: h.subOrder, effectOrder: h.effectOrder,
	}));
	const before = trace.length;
	const r = realSort.call(this, list, ...rest);
	if (!done && before <= want && trace.length > want) {
		done = true;
		console.log(`draw ${want} came from a speedSort of ${snapshot.length}:`);
		for (const h of snapshot) console.log('  ', JSON.stringify(h));
	}
	return r;
};
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
for (const t of scenario.turns) {
	if (done) break;
	if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
	if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
proto.speedSort = realSort;
stop();
if (!done) console.log(`draw ${want} did not come from a speedSort`);
