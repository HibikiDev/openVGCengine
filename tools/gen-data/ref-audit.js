'use strict';










const fs = require('fs');
const path = require('path');

const ROOT = path.join(__dirname, '..', '..');
const cov = require('./out/pool-coverage.json');

const catalogFile = path.join(__dirname, 'out', 'catalog-coverage.json');
if (fs.existsSync(catalogFile)) {
	const catalog = JSON.parse(fs.readFileSync(catalogFile, 'utf8'));
	for (const kind of ['abilities', 'items']) cov[kind] = cov[kind].concat(catalog[kind].map(r => ({ ...r, corpus: 0, catalog: true })));
}
const dir = path.join(ROOT, 'crates', 'engine-core', 'src');
const files = fs.readdirSync(dir).filter(f => f.endsWith('.rs')).map(f => [f, fs.readFileSync(path.join(dir, f), 'utf8').split('\n')]);
const suspectOnly = process.argv.includes('--suspect');

for (const [kind, ns] of [['abilities', 'ability_ids'], ['items', 'item_ids']]) {
	for (const e of cov[kind].filter(r => r.status === 'referenced')) {
		const re = new RegExp('(' + ns + '::|\\b)' + e.id.toUpperCase() + '\\b');
		const fns = new Set();
		for (const [file, lines] of files) {
			let fn = '?';
			let inTests = false;
			for (const line of lines) {
				if (/^mod tests/.test(line)) inTests = true;
				const m = line.match(/^\s*(?:pub(?:\([a-z]+\))? )?(?:const )?fn ([a-z0-9_]+)/);
				if (m) fn = m[1];
				if (!inTests && re.test(line)) fns.add(`${file}:${fn}`);
			}
		}
		const list = [...fns];
		const suspect = list.every(f => /(^|_)ties?(_|$)/.test(f.split(':')[1]));
		if (suspectOnly && !suspect) continue;
		console.log(`${kind} ${e.id}${e.catalog ? ' [catalog]' : ''} (corpus ${e.corpus}): ${list.join(', ') || '-'}`);
	}
}
