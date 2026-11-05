'use strict';








const fs = require('fs');
const path = require('path');

const [dir, format, outFile] = process.argv.slice(2);
if (!outFile) throw new Error('usage: node scenario-teams.js <scenario dir> <format> <out.json>');
const teams = [];
for (const f of fs.readdirSync(dir).filter(name => /^scenario-\d+\.json$/.test(name))) {
	const s = JSON.parse(fs.readFileSync(path.join(dir, f), 'utf8'));
	for (const [k, team] of [['a', s.team1], ['b', s.team2]]) {
		teams.push({
			id: `${f.replace('.json', '')}${k}`,
			sets: team.map(m => ({
				species: m.species, item: m.item, ability: m.ability, moves: m.moves, nature: m.nature, evs: m.evs, ivs: m.ivs, level: 50,
				gender: m.gender || '', ...(m.teraType ? { teraType: m.teraType } : {}),
			})),
		});
	}
}
fs.writeFileSync(outFile, JSON.stringify({ format, source: `random-legal ${dir}`, teams }, null, '\t'));
console.log(`${teams.length} teams -> ${outFile}`);
