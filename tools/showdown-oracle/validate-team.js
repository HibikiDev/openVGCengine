'use strict';













const { Dex, Teams, TeamValidator } = require('./lib/showdown');

const STATS = ['hp', 'atk', 'def', 'spa', 'spd', 'spe'];


function outOfBattle(dex, set) {
	const sp = dex.species.get(set.species);
	if (!sp.exists) return set;
	const base = sp.battleOnly ? dex.species.get(Array.isArray(sp.battleOnly) ? sp.battleOnly[0] : sp.battleOnly)
		: (sp.isMega || sp.isPrimal) ? dex.species.get(sp.baseSpecies) : sp;
	if (base === sp) return set;
	const abilities = [...new Set(Object.values(base.abilities))];
	const ability = abilities.map(a => dex.abilities.get(a).name).includes(dex.abilities.get(set.ability).name) || abilities.length !== 1 ? set.ability : abilities[0];
	return { ...set, species: base.name, ability };
}

function main() {
	const fi = process.argv.indexOf('--format');
	const format = fi >= 0 ? process.argv[fi + 1] : null;
	if (!format) {
		console.error('usage: validate-team.js --format <format id> < paste');
		process.exit(2);
	}
	const text = require('fs').readFileSync(0, 'utf8');

	const sets = text.trimStart().startsWith('[') ? JSON.parse(text) : Teams.import(text);
	if (!sets || !sets.length) {
		console.log(JSON.stringify({ problems: ['no sets found in that text'] }));
		return;
	}
	const dex = Dex.forFormat(format);
	const checked = sets.map(s => outOfBattle(dex, { ...s, level: 50 }));
	const problems = process.argv.includes('--parse-only') ? null : TeamValidator.get(format).validateTeam(checked);
	if (problems) {
		console.log(JSON.stringify({ problems }));
		return;
	}
	console.log(JSON.stringify({
		sets: checked.map(s => ({
			name: s.name || s.species,
			species: s.species,
			item: s.item || '',
			ability: s.ability,
			moves: s.moves,
			nature: s.nature || 'Serious',
			evs: Object.fromEntries(STATS.map(k => [k, (s.evs && s.evs[k]) || 0])),
			ivs: Object.fromEntries(STATS.map(k => [k, s.ivs && s.ivs[k] !== undefined ? s.ivs[k] : 31])),
			gender: s.gender || '',
			level: 50,
			...(s.teraType ? { teraType: s.teraType } : {}),
			...(s.gigantamax ? { gigantamax: true } : {}),
		})),
	}));
}

main();
