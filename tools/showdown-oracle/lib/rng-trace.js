'use strict';































































































const path = require('path');
const { PRNG, Battle, SHOWDOWN_SIM } = require('./showdown');





const { BattleActions } = require(path.join(SHOWDOWN_SIM, 'battle-actions.js'));
const { BattleQueue } = require(path.join(SHOWDOWN_SIM, 'battle-queue.js'));

const realRandom = PRNG.prototype.random;
const realShuffle = PRNG.prototype.shuffle;
const realGetRandomTarget = Battle.prototype.getRandomTarget;
const realSelfDrops = BattleActions.prototype.selfDrops;
const realMoveHit = BattleActions.prototype.moveHit;
const realEachEvent = Battle.prototype.eachEvent;
const realInsertChoice = BattleQueue.prototype.insertChoice;
const realQueueSort = BattleQueue.prototype.sort;
const realResolveAction = BattleQueue.prototype.resolveAction;
const realRunMove = BattleActions.prototype.runMove;
const realUseMoveInner = BattleActions.prototype.useMoveInner;
const realFieldEvent = Battle.prototype.fieldEvent;
const realSpeedSort = Battle.prototype.speedSort;
const realRunEvent = Battle.prototype.runEvent;
const realChangeAction = BattleQueue.prototype.changeAction;









function startTrace() {
	const trace = [];
	let bookkeepingDepth = 0;






	let untargetedAction = false;





	BattleQueue.prototype.resolveAction = function (action, ...rest) {
		const saved = untargetedAction;




		const target = action.choice === 'move' && this.battle.dex.moves.get(action.zmove || action.maxMove || action.move || action.moveid).target;


		const spread = action.choice === 'move' && action.moveid === 'terastarstorm' && !!action.pokemon &&
			action.pokemon.species.name === 'Terapagos-Stellar';
		untargetedAction = action.choice === 'move' && !action.targetLoc && !spread &&
			(['normal', 'any', 'adjacentFoe', 'scripted'].includes(target) ||
				(target === 'randomNormal' && !!action.pokemon && action.pokemon.hasAbility(['stalwart', 'propellertail'])));
		try {
			return realResolveAction.call(this, action, ...rest);
		} finally {
			untargetedAction = saved;
		}
	};


	let smartRetarget = false;


	let overrideRetarget = false;



	let selfLocRetarget = false;
	BattleActions.prototype.runMove = function (moveOrMoveName, pokemon, targetLoc, ...rest) {


		const options = rest[0] || {};
		const moveTarget = this.dex.moves.get(options.maxMove || options.zMove || moveOrMoveName).target;
		untargetedAction = moveTarget === 'randomNormal';
		smartRetarget = !!this.dex.moves.get(moveOrMoveName).smartTarget;
		selfLocRetarget = moveTarget === 'normal' && !!pokemon && !!targetLoc && targetLoc === pokemon.getLocOf(pokemon) &&
			!!pokemon.volatiles['twoturnmove'];
		try {
			return realRunMove.call(this, moveOrMoveName, pokemon, targetLoc, ...rest);
		} finally {
			untargetedAction = false;
			smartRetarget = false;
			overrideRetarget = false;
			selfLocRetarget = false;
		}
	};





	let calledMoveTarget = false;
	BattleActions.prototype.useMoveInner = function (moveOrMoveName, pokemon, options, ...rest) {
		const caller = (options && options.sourceEffect) || this.battle.effect;
		const saved = calledMoveTarget;
		calledMoveTarget = !(options && options.target !== undefined) && !!(caller && (caller.callsMove || caller.id === 'snatch'));
		try {
			return realUseMoveInner.call(this, moveOrMoveName, pokemon, options, ...rest);
		} finally {
			calledMoveTarget = saved;
		}
	};
	Battle.prototype.getRandomTarget = function (...args) {
		const saved = bookkeepingDepth;
		const curse = this.activeMove && this.activeMove.id === 'curse' && args[0] && args[0].hasType('Ghost');


		const bide = this.activeMove && this.activeMove.id === 'bide' && args[1] && (args[1].id || args[1]) === 'pound';
		bookkeepingDepth = untargetedAction || curse || smartRetarget || calledMoveTarget || bide || overrideRetarget || selfLocRetarget ? 0 : saved + 1;
		untargetedAction = false;
		smartRetarget = false;
		overrideRetarget = false;
		selfLocRetarget = false;
		calledMoveTarget = false;
		try {
			return realGetRandomTarget.apply(this, args);
		} finally {
			bookkeepingDepth = saved;
		}
	};




	let selfDropsBase = null;
	BattleActions.prototype.selfDrops = function (targets, source, move, moveData, isSecondary) {
		const wasted = moveData?.self?.boosts && moveData.self.chance === undefined;
		const savedBase = selfDropsBase;
		if (wasted) {
			selfDropsBase = bookkeepingDepth;
			bookkeepingDepth++;
		}
		try {
			return realSelfDrops.call(this, targets, source, move, moveData, isSecondary);
		} finally {
			if (wasted) bookkeepingDepth--;
			selfDropsBase = savedBase;
		}
	};
	BattleActions.prototype.moveHit = function (...args) {
		if (selfDropsBase === null) return realMoveHit.apply(this, args);
		const saved = bookkeepingDepth;
		const savedBase = selfDropsBase;
		bookkeepingDepth = selfDropsBase;
		selfDropsBase = null;
		try {
			return realMoveHit.apply(this, args);
		} finally {
			bookkeepingDepth = saved;
			selfDropsBase = savedBase;
		}
	};





	let inEachEvent = 0;
	const eachEventReal = [];
	Battle.prototype.eachEvent = function (...args) {
		inEachEvent++;
		const seekers = args[0] === 'Update' ? this.getAllActive().filter(p => p.ability === 'trace' && p.abilityState && p.abilityState.seek) : [];
		eachEventReal.push(seekers.length > 1 && seekers.some(p => p.adjacentFoes().some(
			t => !t.getAbility().flags['notrace'] && t.ability !== 'noability')));
		try {
			return realEachEvent.apply(this, args);
		} finally {
			inEachEvent--;
			eachEventReal.pop();
		}
	};



	let changingAction = 0;
	BattleQueue.prototype.changeAction = function (...args) {
		changingAction++;
		try {
			return realChangeAction.apply(this, args);
		} finally {
			changingAction--;
		}
	};



	BattleQueue.prototype.insertChoice = function (...args) {
		const placement = changingAction > 0;
		const megaReinsert = !placement && this.battle.gen === 7 && args[1] === true && !!args[0] && args[0].mega === 'done';
		if (!placement) bookkeepingDepth++;
		const battle = this.battle;
		if (megaReinsert) {
			const realRandom = Object.getPrototypeOf(battle).random;
			battle.random = function (...r) {
				if (r.length !== 2) return realRandom.apply(this, r);
				bookkeepingDepth--;
				try {
					return realRandom.apply(this, r);
				} finally {
					bookkeepingDepth++;
				}
			};
		}
		try {
			return realInsertChoice.apply(this, args);
		} finally {
			if (megaReinsert) delete battle.random;
			if (!placement) bookkeepingDepth--;
		}
	};

	BattleQueue.prototype.sort = function (...args) {



		const switchOnly = !this.list.some(action => ['move', 'switch', 'instaswitch'].includes(action.choice));
		if (switchOnly) bookkeepingDepth++;
		try {
			return realQueueSort.apply(this, args);
		} finally {
			if (switchOnly) bookkeepingDepth--;
		}
	};



	let residualFieldEvent = 0;
	Battle.prototype.fieldEvent = function (eventid, ...args) {
		const residual = eventid === 'Residual';
		if (residual) residualFieldEvent++;
		try {
			return realFieldEvent.call(this, eventid, ...args);
		} finally {
			if (residual) residualFieldEvent--;
		}
	};
	Battle.prototype.speedSort = function (...args) {
		const caller = new Error().stack.split(String.fromCharCode(10))[2] || '';
		const direct = (residualFieldEvent > 0 && /fieldEvent/.test(caller)) ||
			(inEachEvent > 0 && /eachEvent/.test(caller) && !eachEventReal[eachEventReal.length - 1]);
		if (direct) bookkeepingDepth++;
		try {
			return realSpeedSort.apply(this, args);
		} finally {
			if (direct) bookkeepingDepth--;
		}
	};





	Battle.prototype.runEvent = function (eventid, ...args) {
		if (eventid === 'OverrideAction') {
			const changed = realRunEvent.call(this, eventid, ...args);
			overrideRetarget = !!changed && changed !== true;
			return changed;
		}


		if (eventid === 'ModifySpe' || eventid === 'ModifyBoost') {
			bookkeepingDepth++;
			try {
				return realRunEvent.call(this, eventid, ...args);
			} finally {
				bookkeepingDepth--;
			}
		}
		if (eventid !== 'FractionalPriority') return realRunEvent.call(this, eventid, ...args);
		const saved = bookkeepingDepth;
		bookkeepingDepth = 0;
		try {
			return realRunEvent.call(this, eventid, ...args);
		} finally {
			bookkeepingDepth = saved;
		}
	};

	PRNG.prototype.random = function (from, to) {
		const result = realRandom.call(this, from, to);
		trace.push({ from: from ?? null, to: to ?? null, result, bookkeeping: bookkeepingDepth > 0 });
		return result;
	};





	PRNG.prototype.shuffle = function (items, start = 0, end = items.length) {
		const group = items.slice(start, end);
		const future = residualFieldEvent > 0 && group.length > 1 && group.every(h => h?.effect?.id === 'futuremove');


		const moody = residualFieldEvent > 0 && group.length > 1 && group.every(h => h?.effect?.id === 'moody' && h?.effectHolder?.getSlot);
		realShuffle.call(this, items, start, end);
		if (future || moody) {
			const slotOf = h => String(future ? h.state?.targetSlot ?? '' : h.effectHolder.getSlot());
			const canonical = group.slice().sort((a, b) => (slotOf(a) < slotOf(b) ? -1 : slotOf(a) > slotOf(b) ? 1 : 0));
			const final = items.slice(start, end);
			for (let i = 0; i < final.length - 1; i++) {
				const j = canonical.indexOf(final[i], i);
				trace.push({ from: i, to: final.length, result: j, bookkeeping: false });
				[canonical[i], canonical[j]] = [canonical[j], canonical[i]];
			}
		}
	};

	return {
		trace,
		stop: () => {
			PRNG.prototype.random = realRandom;
			PRNG.prototype.shuffle = realShuffle;
			Battle.prototype.getRandomTarget = realGetRandomTarget;
			BattleQueue.prototype.resolveAction = realResolveAction;
			BattleActions.prototype.runMove = realRunMove;
			BattleActions.prototype.useMoveInner = realUseMoveInner;
			BattleActions.prototype.selfDrops = realSelfDrops;
			BattleActions.prototype.moveHit = realMoveHit;
			Battle.prototype.eachEvent = realEachEvent;
			BattleQueue.prototype.insertChoice = realInsertChoice;
			BattleQueue.prototype.sort = realQueueSort;
			Battle.prototype.fieldEvent = realFieldEvent;
			Battle.prototype.speedSort = realSpeedSort;
			Battle.prototype.runEvent = realRunEvent;
			BattleQueue.prototype.changeAction = realChangeAction;
		},
	};
}

module.exports = { startTrace };
