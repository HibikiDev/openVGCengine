'use strict';



const toID = s => String(s).toLowerCase().replace(/[^a-z0-9]/g, '');

function assignHappiness(sets, rng) {
	for (const set of sets) {
		if (!set.moves.some(m => ['return', 'frustration'].includes(toID(m)))) continue;
		const r = rng() % 3;
		set.happiness = r === 0 ? 0 : r === 1 ? 255 : rng() % 256;
	}
}

module.exports = { assignHappiness };
