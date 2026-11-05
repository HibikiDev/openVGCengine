const fs = require('fs');
const { Battle } = require(require('path').join(__dirname, '..', 'lib', 'showdown'));
const { startTrace } = require(require('path').join(__dirname, '..', 'lib', 'rng-trace'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const inline = process.argv[3] === 'inline';
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
const { trace, stop } = startTrace();
let seen = 0;
if (inline) {

	const realAdd = battle.add.bind(battle);
	battle.add = (...args) => {
		while (seen < trace.length) {
			const d = trace[seen];
			realAdd('~rng', `${seen}`, `${d.from}${d.to != null ? ',' + d.to : ''}=${d.result}${d.bookkeeping ? ' B' : ''}`);
			seen++;
		}
		return realAdd(...args);
	};
	const realRunEvent = battle.runEvent.bind(battle);
	battle.runEvent = (eventid, target, source, effect, relayVar, ...rest) => {
		const r = realRunEvent(eventid, target, source, effect, relayVar, ...rest);
		if (eventid === 'Accuracy') battle.add('~acc', effect && effect.name, `in=${relayVar}`, `out=${r}`, `src=${source && source.name}:${source && source.ability}/${source && Object.keys(source.volatiles)}`, `tgt=${target && target.name}:${target && target.ability}/${target && Object.keys(target.volatiles)}`, `field=${Object.keys(battle.field.pseudoWeather)}`);
		return r;
	};
	const realGetDamage = battle.actions.getDamage.bind(battle.actions);
	battle.actions.getDamage = (source, target, move, suppress) => {
		const d = realGetDamage(source, target, move, suppress);
		const mv = typeof move === 'string' ? move : move.name;
		let atk = '?', def = '?';
		battle.add('~dmg', `${source.name}->${target.name}`, mv, `dmg=${d}`, `bp=${typeof move === 'string' ? '' : move.basePower}`, `atk=${atk}`, `def=${def}`);
		return d;
	};
}
for (const t of scenario.turns) {
	if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
	if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
stop();
console.log(JSON.stringify(trace.map(d => [d.from, d.to, d.result, d.bookkeeping ? 'B' : ''])));
console.log(battle.log.join('\n'));
