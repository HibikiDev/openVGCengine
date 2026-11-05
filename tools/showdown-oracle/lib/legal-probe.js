'use strict';
















function slotCandidates(side, request, slot) {
	const party = side.pokemon.length;
	const switches = [];
	for (let pos = 1; pos <= party; pos++) switches.push(`switch ${pos}`);
	if (request.forceSwitch) {
		return request.forceSwitch[slot] ? ['pass', ...switches] : ['pass'];
	}
	const mon = side.active[slot];


	if (!mon || mon.fainted || mon.volatiles['commanding']) return ['pass'];
	const parts = ['pass', ...switches];
	const moves = request.active[slot].moves.length;
	for (let i = 1; i <= moves; i++) {
		for (const t of ['', ' 1', ' 2', ' -1', ' -2']) {
			parts.push(`move ${i}${t}`);

			if (request.active[slot].canMegaEvo) parts.push(`move ${i}${t} mega`);

			if (request.active[slot].canZMove) parts.push(`move ${i}${t} zmove`);
			if (request.active[slot].canUltraBurst) parts.push(`move ${i}${t} ultra`);

			if (request.active[slot].canTerastallize) parts.push(`move ${i}${t} terastallize`);

			if (request.active[slot].canDynamax) parts.push(`move ${i}${t} dynamax`);
		}
	}
	return parts;
}


function attempt(side, input, needDone) {
	const flags = side.active.map(p => p && p.switchFlag);
	side.clearChoice();
	const ok = side.choose(input) && (!needDone || side.isChoiceDone());
	side.clearChoice();
	side.active.forEach((p, i) => { if (p) p.switchFlag = flags[i]; });
	return ok;
}

const tryChoice = (side, input) => attempt(side, input, true);
const acceptsPrefix = (side, input) => attempt(side, input, false);





function legalChoices(battle, side) {
	const request = side.activeRequest;
	if (!request || request.wait || request.teamPreview || battle.ended) return null;
	const first = slotCandidates(side, request, 0).filter(a => acceptsPrefix(side, a));
	const second = slotCandidates(side, request, 1);
	const legal = [];
	for (const a of first) {
		for (const b of second) {
			const input = `${a}, ${b}`;
			if (tryChoice(side, input)) legal.push(input);
		}
	}
	return legal;
}

module.exports = { legalChoices };
