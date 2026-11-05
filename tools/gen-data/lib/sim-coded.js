'use strict';











const fs = require('fs');
const path = require('path');

function simCodedChecker(showdownRoot) {
	const read = f => { try { return fs.readFileSync(f, 'utf8'); } catch { return ''; } };
	const sim = ['battle', 'battle-actions', 'pokemon', 'side', 'field', 'battle-queue']
		.map(f => read(path.join(showdownRoot, 'sim', f + '.ts'))).join('\n');
	const champions = path.join(showdownRoot, 'data', 'mods', 'champions');
	const data = ['moves', 'conditions', 'abilities', 'items'].map(f => read(path.join(showdownRoot, 'data', f + '.ts')))
		.concat(fs.existsSync(champions) ? fs.readdirSync(champions).filter(f => f.endsWith('.ts')).map(f => read(path.join(champions, f))) : [])
		.join('\n');

	const quoted = s => `['"]${s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')}['"]`;
	return (id, name) => id !== 'pokeball' && [id, name].filter(Boolean).some(s =>
		new RegExp(quoted(s)).test(sim) || new RegExp(`has(Item|Ability)\\(\\[?[^)]*${quoted(s)}`).test(data));
}

module.exports = { simCodedChecker };
