

const fs = require('fs');
const { Battle } = require(require('path').join(__dirname, '..', 'lib', 'showdown'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const ev = process.argv[3];
const want = process.argv[4] === undefined ? null : +process.argv[4];
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
let step = 0;
const orig = battle.runEvent.bind(battle);
battle.runEvent = function (id, target, source, effect, ...rest) {
  if (id === ev && (want === null || step === want)) {
    const who = target && target.name ? target.name : '';
    console.log(`${id} step ${step} target ${who} effect ${effect && effect.id}`);
    for (const p of battle.getAllActive()) {
      console.log(`   ${p.side.id} ${p.name} ${p.species.name} speed ${p.speed} spe ${p.storedStats.spe} boosts ${JSON.stringify(p.boosts)} ab ${p.ability} item ${p.item} hp ${p.hp}`);
    }
  }
  return orig(id, target, source, effect, ...rest);
};
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
scenario.turns.forEach((t, i) => {
  step = i + 1;
  if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
  if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
});
