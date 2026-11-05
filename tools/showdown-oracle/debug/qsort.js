const fs = require('fs');
const { Battle } = require(require('path').join(__dirname, '..', 'lib', 'showdown'));
const scenario = JSON.parse(fs.readFileSync(process.argv[2], 'utf8'));
const want = +process.argv[3];
const battle = new Battle({ formatid: scenario.format, seed: scenario.seed, p1: { name: 'p1', team: scenario.team1 }, p2: { name: 'p2', team: scenario.team2 } });
const origSort = battle.queue.sort.bind(battle.queue);
let step = 0;
battle.queue.sort = function () { if (step === want) console.log('QSORT', battle.queue.list.map(a => `${a.choice}:${a.pokemon ? a.pokemon.name + (a.pokemon.fainted ? '(fnt)' : '') : ''}:o${a.order}:p${a.priority}:s${a.speed}`).join(' | ')); return origSort(); };
battle.choose('p1', 'team 1234'); battle.choose('p2', 'team 1234');
scenario.turns.forEach((t, i) => {
  step = i + 1;
  if (t.p1.trim() !== 'pass, pass') battle.choose('p1', t.p1);
  if (t.p2.trim() !== 'pass, pass') battle.choose('p2', t.p2);
});
