'use strict';











const { ordered, poolAndCatalog } = require('./id-registry');


function loadSpeciesSorted() {
	const species = poolAndCatalog('species');
	return ordered('species', species);
}


function buildSpeciesIdMap() {
	const sorted = loadSpeciesSorted();
	const byShowdownId = new Map();
	const byName = new Map();
	sorted.forEach((s, i) => {
		const id = i + 1;
		byShowdownId.set(s.id, id);
		byName.set(s.name, id);
	});
	return { sorted, byShowdownId, byName };
}

module.exports = { loadSpeciesSorted, buildSpeciesIdMap };
