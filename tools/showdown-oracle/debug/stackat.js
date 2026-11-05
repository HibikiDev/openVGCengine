
const fs = require('fs');
const { Battle } = require(require('path').join(__dirname, '..', 'lib', 'showdown'));
const { startTrace } = require(require('path').join(__dirname, '..', 'lib', 'rng-trace'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const want = Number(process.argv[3]);
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
const { trace, stop } = startTrace();
const proto = Object.getPrototypeOf(battle.prng);
const real = proto.random;
let done = false;
proto.random = function (...a) {
  const before = trace.length;
  const r = real.apply(this, a);
  if (!done && before <= want && trace.length > want) {
    done = true;
    console.log(`draw ${want}: random(${a.join(',')}) = ${r}`);
    for (const s of battle.sides) for (const p of s.active) if (p) console.log('  ', s.id, p.name, p.species.name, 'spe', p.getStat('spe'), 'vol', Object.keys(p.volatiles).join(','), 'item', p.item, 'ab', p.ability, 'status', p.status);
    console.log(new Error().stack.split('\n').slice(2, 22).map(l => l.replace(/C:.*pokemon-showdown.dist./, '')).join('\n'));
  }
  return r;
};
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
for (const t of scenario.turns) {
  if (done) break;
  if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
  if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
}
proto.random = real;
stop();
