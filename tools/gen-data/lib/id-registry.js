'use strict';
















const fs = require('fs');
const path = require('path');

const IDS_DIR = path.join(__dirname, '..', 'ids');

function registryPath(kind) {
	return path.join(IDS_DIR, `${kind}.json`);
}








function ordered(kind, entries) {
	const file = registryPath(kind);
	const registry = fs.existsSync(file) ? JSON.parse(fs.readFileSync(file, 'utf8')) : [];
	const byId = new Map(entries.map(e => [e.id, e]));
	const missing = registry.filter(id => !byId.has(id));
	if (missing.length) {
		throw new Error(`${kind}: registered ids missing from the pool (ids must never shift): ${missing.join(', ')}`);
	}
	const known = new Set(registry);
	const added = entries.map(e => e.id).filter(id => !known.has(id)).sort((a, b) => a.localeCompare(b));
	if (added.length) {
		fs.mkdirSync(IDS_DIR, { recursive: true });
		fs.writeFileSync(file, JSON.stringify([...registry, ...added], null, '\t') + '\n');
		console.error(`${kind}: appended ${added.length} new id(s): ${added.join(', ')}`);
	}
	return [...registry, ...added].map(id => byId.get(id));
}






function poolAndCatalog(kind) {
	const out = path.join(__dirname, '..', 'out');
	const catalog = path.join(out, `catalog-${kind}.json`);
	return [...require(path.join(out, `${kind}.json`)), ...(fs.existsSync(catalog) ? require(catalog) : [])];
}

module.exports = { ordered, poolAndCatalog };
