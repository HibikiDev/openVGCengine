'use strict';



const { Dex } = require('./showdown');

function genderFor(species, rng) {
	const s = Dex.species.get(species);
	if (s.gender) return s.gender;
	return (rng() / 4294967296) < s.genderRatio.M ? 'M' : 'F';
}

function assignGenders(sets, rng) {
	for (const set of sets) set.gender = genderFor(set.species, rng);
}

module.exports = { genderFor, assignGenders };
