

const fs = require('fs');
const path = require('path');
const { Battle } = require('../lib/showdown');
const { legalChoices } = require('../lib/legal-probe');

const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const step = parseInt(process.argv[3], 10);
const sideId = process.argv[4] || 'p1';
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
battle.choose('p1', 'team 1234');
battle.choose('p2', 'team 1234');
for (const t of scenario.turns.slice(0, step - 1)) {
	if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
	if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
const side = battle[sideId];
console.log(`turn ${battle.turn}, step ${step} choices: ${JSON.stringify(scenario.turns[step - 1])}`);
console.log('request:', JSON.stringify(side.activeRequest && (side.activeRequest.active || side.activeRequest.forceSwitch), null, 0));
for (const p of side.active) {
	if (!p) continue;
	console.log(`${p.name} ${p.species.name} hp=${p.hp} item=${p.item} ability=${p.ability} volatiles=[${Object.keys(p.volatiles)}]`);
	for (const m of p.moveSlots) console.log(`   ${m.id} pp=${m.pp} disabled=${m.disabled} src=${m.disabledSource || ''}`);
}
const legal = legalChoices(battle, side);
console.log(`${legal ? legal.length : 'null'} legal:`, legal && legal.join(' | '));
