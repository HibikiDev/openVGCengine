
const fs = require('fs');
const S = require('path').join(__dirname, '..', 'lib', 'showdown');
const { Battle } = require(S);
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
const actions = Object.getPrototypeOf(battle.actions);
const real = actions.runSwitch;
let step = 0;
actions.runSwitch = function (pokemon) {
  const rows = [];
  for (const s of battle.sides) for (const p of s.active) if (p) rows.push(`${s.id}${'ab'[p.position]} ${p.species.name} cached=${p.speed} live=${p.getActionSpeed()} fnt=${p.fainted}`);
  console.log(`step ${step} turn ${battle.turn} runSwitch(${pokemon.side.id} ${pokemon.species.name}):\n   ` + rows.join('\n   '));
  return real.call(this, pokemon);
};
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
for (const t of scenario.turns) {
  step++;
  if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
  if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
