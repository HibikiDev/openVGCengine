
const fs = require('fs');
const { Battle } = require(require('path').join(__dirname, '..', 'lib', 'showdown'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
const proto = Object.getPrototypeOf(battle);
const real = proto.fieldEvent;
proto.fieldEvent = function (eventid, ...args) {
  if (eventid === 'Residual') {
    const rows = [];
    for (const s of battle.sides) for (const p of s.active) if (p) rows.push(`${s.id}${'ab'[p.position]} ${p.species.name} speed=${p.speed} hp=${p.hp} status=${p.status} item=${p.item}`);
    console.log(`turn ${battle.turn} residual: trickroom=${!!battle.field.pseudoWeather.trickroom}\n   ` + rows.join('\n   '));
  }
  return real.call(this, eventid, ...args);
};
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
for (const t of scenario.turns) {
  if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
  if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
