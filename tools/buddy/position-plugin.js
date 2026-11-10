
























'use strict';

const STATUSES = new Set(['', 'brn', 'par', 'slp', 'frz', 'psn', 'tox']);
const BOOSTS = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion'];
const WEATHERS = new Set(['', 'sunnyday', 'raindance', 'sandstorm', 'snowscape', 'snow', 'hail', 'desolateland', 'primordialsea', 'deltastream']);
const TERRAINS = new Set(['', 'electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain']);
const TIMED_SIDE = ['tailwind', 'reflect', 'lightscreen', 'auroraveil', 'safeguard'];
const LAYERED_SIDE = {stealthrock: 1, spikes: 3, toxicspikes: 2, stickyweb: 1};
const ID = /^[a-z0-9]{1,40}$/;
const GHOST_WEATHER = new Set(['none', 'sunnyday', 'raindance', 'sandstorm', 'snowscape', 'snow', 'hail', 'desolateland', 'primordialsea', 'deltastream']);
const GHOST_FIELD = new Set(['electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain', 'trickroom', 'gravity', 'magicroom', 'wonderroom']);
const GHOST_SIDE = new Set(['tailwind', 'reflect', 'lightscreen', 'auroraveil', 'safeguard', 'stealthrock', 'spikes', 'toxicspikes', 'stickyweb']);
const toID = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '');

const VOLATILES = new Set(['confusion', 'substitute', 'taunt', 'focusenergy', 'yawn', 'leechseed']);

function bad(what) {
	return new Chat.ErrorMessage(`openposition: ${what}`);
}

function int(v, lo, hi, what) {
	if (!Number.isInteger(v) || v < lo || v > hi) throw bad(`${what} must be a whole number ${lo}-${hi}`);
	return v;
}

function check(spec) {
	if (!spec || typeof spec !== 'object') throw bad('not a position');
	const format = Dex.formats.get(spec.format);
	if (!format.exists || !format.id.endsWith('buddy')) throw bad('a buddy format only');
	const out = {format: format.id, ots: !!spec.ots, turn: int(spec.turn, 1, 999, 'turn'), players: {}, mons: {}, sides: {}};
	for (const sid of ['p1', 'p2']) {
		const p = spec[sid] || {};
		if (typeof p.name !== 'string' || !p.name.trim() || p.name.length > 18) throw bad(`${sid}.name`);
		if (typeof p.team !== 'string' || p.team.length > 6000) throw bad(`${sid}.team`);
		const order = (Array.isArray(p.order) ? p.order : []).map(x => int(x, 1, 6, `${sid}.order`));
		if (order.length < 1 || new Set(order).size !== order.length) throw bad(`${sid}.order`);
		out.players[sid] = {name: p.name.trim(), team: p.team, order};
		const mons = ((spec.mons || {})[sid]) || [];
		if (!Array.isArray(mons) || mons.length !== order.length) throw bad(`mons.${sid} needs one entry per brought mon`);
		let alive = true;
		out.mons[sid] = mons.map((m, i) => {
			m = m || {};
			const status = m.status || '';
			if (!STATUSES.has(status)) throw bad(`mons.${sid}[${i}].status`);
			const boosts = {};
			for (const b of BOOSTS) boosts[b] = int((m.boosts || {})[b] || 0, -6, 6, `boost ${b}`);
			const ppUsed = {};
			for (const [k, v] of Object.entries(m.ppUsed || {})) {
				if (!ID.test(k)) throw bad(`mons.${sid}[${i}].ppUsed`);
				ppUsed[k] = int(v, 0, 64, 'ppUsed');
			}
			const hp = int(m.hp, 0, 1000, 'hp');
			if (hp > 0 && !alive) throw bad(`${sid}: the fainted mons go last in order`);
			if (hp === 0) alive = false;
			const vols = Array.isArray(m.vols) ? m.vols : [];
			if (!vols.every(v => VOLATILES.has(v))) throw bad(`mons.${sid}[${i}].vols`);
			return {hp, status, toxStage: int(m.toxStage || 0, 0, 15, 'toxStage'), boosts, ppUsed, stall: int(m.stall || 0, 0, 6, 'stall'),
				vols: [...new Set(vols)], choiceLock: m.choiceLock && ID.test(m.choiceLock) ? m.choiceLock : '',
				activeTurns: int(m.activeTurns || 0, 0, 999, 'activeTurns'), acted: !!m.acted,
				lastMove: m.lastMove && ID.test(m.lastMove) ? m.lastMove : '', timesAttacked: int(m.timesAttacked || 0, 0, 999, 'timesAttacked'),
				lastFailed: !!m.lastFailed, fallen: int(m.fallen || 0, 0, 5, 'fallen'), seen: !!m.seen,
				noItem: !!m.noItem, mega: !!m.mega, tera: !!m.tera};
		});
		const sc = (spec.sides || {})[sid] || {};
		const side = {};
		for (const k of TIMED_SIDE) if (sc[k]) side[k] = int(sc[k], 1, 8, `${sid}.${k}`);
		for (const k in LAYERED_SIDE) if (sc[k]) side[k] = int(sc[k], 1, LAYERED_SIDE[k], `${sid}.${k}`);
		out.sides[sid] = side;
	}
	const f = spec.field || {};
	const weather = f.weather || '';
	const terrain = f.terrain || '';
	if (!WEATHERS.has(weather)) throw bad('field.weather');
	if (!TERRAINS.has(terrain)) throw bad('field.terrain');
	out.field = {weather, weatherTurns: int(f.weatherTurns || 0, 0, 8, 'weatherTurns'), terrain,
		terrainTurns: int(f.terrainTurns || 0, 0, 8, 'terrainTurns'), trickRoom: int(f.trickRoom || 0, 0, 5, 'trickRoom'),
		gravity: int(f.gravity || 0, 0, 5, 'gravity')};


	const ghost = Array.isArray(spec.ghost) ? spec.ghost : [];
	if (ghost.length > 4000) throw bad('ghost too long');
	const named = (name, ids) => {
		if (typeof name !== 'string' || !/^(move: )?[A-Za-z][A-Za-z ]{0,29}$/.test(name)) return false;
		return ids.has(toID(name.replace(/^move: /, '')));
	};
	out.ghost = ghost.map((g, i) => {
		g = g || {};
		if (g.k === 'turn') return {k: 'turn', n: int(g.n, 2, 999, `ghost[${i}].n`)};
		if (g.k === 'upkeep') return {k: 'upkeep'};
		if (g.k === 'weather' && named(g.name, GHOST_WEATHER)) return {k: 'weather', name: g.name, upkeep: !!g.upkeep};
		if ((g.k === 'fieldstart' || g.k === 'fieldend') && named(g.name, GHOST_FIELD)) return {k: g.k, name: g.name};
		if ((g.k === 'sidestart' || g.k === 'sideend') && ['p1', 'p2'].includes(g.side) && named(g.name, GHOST_SIDE)) {
			return {k: g.k, side: g.side, name: g.name};
		}
		throw bad(`ghost[${i}]`);
	});
	return out;
}




const SPECS = require('path').resolve(__dirname, require('path').basename(__dirname) === 'chat-plugins' ? '../../..' : '../..', 'logs/positions');

function patch(battle, token) {
	if (!/^[a-f0-9]{16}$/.test(token)) throw new Error('openposition: bad token');
	return apply(battle, JSON.parse(require('fs').readFileSync(require('path').join(SPECS, `${token}.json`), 'utf8')));
}












function apply(battle, S) {
	const order = ['atk', 'def', 'spa', 'spd', 'spe', 'accuracy', 'evasion'];
	const capture = fn => {
		const mark = battle.log.length;
		fn();
		return battle.log.splice(mark);
	};
	const startWeather = battle.field.weather ? battle.field.getWeather().name : '';
	const startTerrain = battle.field.terrain ? battle.field.getTerrain().name : '';


	const activeLines = new Map();


	const startDetails = new Map();
	for (const sid of ['p1', 'p2']) {
		battle[sid].pokemon.forEach((p, i) => {
			startDetails.set(p, p.details);
			const m = S.mons[sid][i];
			if (!m) return;

			const lines = capture(() => {
				if (m.mega && p.canMegaEvo) battle.actions.runMegaEvo(p);
				if (m.tera && p.canTerastallize) battle.actions.terastallize(p);
			});
			if (p.isActive) activeLines.set(p, lines);
		});
	}


	const F = S.field;
	const fieldLines = capture(() => {
		if (battle.field.weather && battle.field.weather !== F.weather) battle.field.clearWeather();
		if (F.weather) {
			battle.field.setWeather(F.weather, 'debug');
			if (battle.field.weather === F.weather) battle.field.weatherState.duration = F.weatherTurns;
		}
		if (battle.field.terrain && battle.field.terrain !== F.terrain) battle.field.clearTerrain();
		if (F.terrain) {
			battle.field.setTerrain(F.terrain, 'debug');
			if (battle.field.terrain === F.terrain) battle.field.terrainState.duration = F.terrainTurns;
		}
		for (const [k, v] of [['trickroom', F.trickRoom], ['gravity', F.gravity]]) {
			if (!v) continue;
			battle.field.addPseudoWeather(k, 'debug');
			if (battle.field.pseudoWeather[k]) battle.field.pseudoWeather[k].duration = v;
		}
		for (const sid of ['p1', 'p2']) {
			const side = battle[sid];
			for (const k in S.sides[sid]) {
				const v = S.sides[sid][k];
				const layers = ['stealthrock', 'spikes', 'toxicspikes', 'stickyweb'].includes(k);
				for (let n = 0; n < (layers ? v : 1); n++) side.addSideCondition(k, 'debug');
				if (!layers && side.sideConditions[k]) side.sideConditions[k].duration = v;
			}
		}
	});
	const FIELD_LINE = /^\|-(weather|fieldstart|fieldend|sidestart|sideend)\|/;
	for (const sid of ['p1', 'p2']) {
		const side = battle[sid];
		S.mons[sid].forEach((m, i) => {
			const p = side.pokemon[i];
			if (!p) return;
			const lines = capture(() => setMon(battle, side, p, m));
			if (p.isActive) activeLines.set(p, (activeLines.get(p) || []).concat(lines).filter(l => !FIELD_LINE.test(l)));
		});
	}


	if (S.ghost && S.ghost.length) {
		if (startWeather) battle.add('-weather', 'none');
		if (startTerrain) battle.add('-fieldend', `move: ${startTerrain}`);
		for (const g of S.ghost) {
			if (g.k === 'turn') battle.add('turn', g.n);
			else if (g.k === 'upkeep') battle.add('upkeep');
			else if (g.k === 'weather') battle.add('-weather', g.name, ...(g.upkeep ? ['[upkeep]'] : []));
			else if (g.k === 'fieldstart' || g.k === 'fieldend') battle.add(`-${g.k}`, g.name);
			else battle.add(`-${g.k}`, battle[g.side], g.name);
		}
	} else {
		battle.log.push(...fieldLines);



		let weather = '', terrain = '';
		for (const ln of battle.log) {
			const w = /^\|-weather\|([^|]*)/.exec(ln);
			if (w) weather = w[1] === 'none' ? '' : toID(w[1]);
			const t = /^\|-field(start|end)\|(?:move: )?([^|]*)/.exec(ln);
			if (t && toID(t[2]).endsWith('terrain')) terrain = t[1] === 'start' ? toID(t[2]) : '';
		}
		if (battle.field.weather && weather !== battle.field.weather) battle.add('-weather', battle.field.getWeather().name);
		if (battle.field.terrain && terrain !== battle.field.terrain) battle.add('-fieldstart', `move: ${battle.field.getTerrain().name}`);
	}

	for (const sid of ['p1', 'p2']) {
		const side = battle[sid];
		const lead = side.active[0];
		let revealed = false;
		S.mons[sid].forEach((m, i) => {
			const p = side.pokemon[i];
			if (!p || p.isActive || !m.seen) return;
			const ident = `${sid}a: ${p.name}`;
			battle.add('switch', ident, startDetails.get(p), p.getHealth);
			if (p.details !== startDetails.get(p)) battle.add('detailschange', ident, p.details);
			if (m.mega && p.set.item) {
				battle.add('-mega', ident, battle.dex.species.get(p.set.species).name, battle.dex.items.get(p.set.item).name);
			}
			if (m.tera && p.terastallized) battle.add('-terastallize', ident, p.terastallized);
			if (p.fainted) {
				battle.add('faint', ident);
			} else if (m.noItem && p.set.item) {
				battle.add('-enditem', ident, battle.dex.items.get(p.set.item).name, '[silent]');
			}
			revealed = true;
		});

		if (revealed && lead) battle.add('switch', lead, startDetails.get(lead), lead.getHealth);
	}

	for (const [p, lines] of activeLines) {
		battle.log.push(...lines);
		const m = S.mons[p.side.id][p.side.pokemon.indexOf(p)];
		battle.add('-sethp', p, p.getHealth, '[silent]');
		battle.add('-clearboost', p, '[silent]');
		for (const b of order) if (m.boosts[b]) battle.add('-setboost', p, b, m.boosts[b], '[silent]');
	}
	battle.turn = S.turn;
	battle.add('turn', S.turn);
	battle.makeRequest('move');
	return `position set (turn ${S.turn})`;
}


function setMon(battle, side, p, m) {
	for (const slot of p.moveSlots) {
		if (m.ppUsed[slot.id]) slot.pp = Math.max(0, slot.maxpp - m.ppUsed[slot.id]);
	}
	if (m.noItem && p.item) {
		if (p.isActive) battle.add('-enditem', p, p.getItem().name, '[silent]');
		p.item = '';
		p.itemState = battle.initEffectState({id: '', target: p});
	}
	if (m.hp === 0) {
		p.hp = 0;
		p.fainted = true;
		p.switchFlag = false;
		p.status = '';
		if (side.pokemonLeft) side.pokemonLeft--;
		side.totalFainted++;
		return;
	}
	p.hp = Math.max(1, Math.round(p.maxhp * m.hp / 1000));
	if (!m.noItem && !p.item && p.set.item) {

		p.item = battle.toID(p.set.item);
		p.itemState = battle.initEffectState({id: p.item, target: p});
		if (p.volatiles['unburden']) p.removeVolatile('unburden');
	}
	if (m.status && p.status !== m.status) {
		p.setStatus(m.status, null, null, true);
		if (m.status === 'tox' && p.statusState) p.statusState.stage = m.toxStage;
	}
	if (!p.isActive) return;
	p.boosts = Object.assign({}, m.boosts);
	if (m.stall) {


		for (let n = 0; n < m.stall; n++) p.addVolatile('stall');
		if (p.volatiles['stall']) p.volatiles['stall'].duration = 1;
	}

	p.activeTurns = m.activeTurns;
	p.activeMoveActions = m.acted ? 1 : 0;
	if (m.lastMove && p.moveSlots.some(s => s.id === m.lastMove)) {
		const mv = battle.dex.getActiveMove(m.lastMove);
		p.lastMove = mv;
		p.lastMoveUsed = mv;
		p.lastMoveEncore = mv;
	}
	p.timesAttacked = m.timesAttacked;
	if (m.lastFailed) p.moveLastTurnResult = false;
	if (p.hasAbility('supremeoverlord')) {

		if (p.abilityState.fallen) battle.add('-end', p, `fallen${p.abilityState.fallen}`, '[silent]');
		p.abilityState.fallen = m.fallen;
		if (m.fallen) battle.add('-start', p, `fallen${m.fallen}`, '[silent]');
	}
	if (m.choiceLock && p.getItem().isChoice && p.moveSlots.some(s => s.id === m.choiceLock)) {

		p.volatiles['choicelock'] = battle.initEffectState({id: 'choicelock', target: p, move: m.choiceLock});
	}
	for (const v of m.vols) {
		const foe = side.foe.active.find(x => x && !x.fainted);
		p.addVolatile(v, v === 'leechseed' ? foe : null);

		if (v === 'yawn' && p.volatiles['yawn']) p.volatiles['yawn'].duration = 1;
	}
}

exports.patch = patch;
exports.apply = apply;
exports.check = check;

exports.commands = {
	openposition(target, room, user) {
		let spec;
		try {
			spec = JSON.parse(target);
		} catch {
			throw bad('not JSON');
		}
		spec = check(spec);
		const P = spec.players;
		const lines = [
			`>start ${JSON.stringify({formatid: spec.format})}`,
			`>player p1 ${JSON.stringify({name: P.p1.name, team: P.p1.team})}`,
			`>player p2 ${JSON.stringify({name: P.p2.name, team: P.p2.team})}`,
		];
		if (spec.ots) lines.push('>show-openteamsheets');
		lines.push(`>p1 team ${P.p1.order.join(',')}`, `>p2 team ${P.p2.order.join(',')}`);
		const battleRoom = Rooms.createBattle({format: spec.format, players: [], inputLog: lines.join('\n')});
		if (!battleRoom) return;
		battleRoom.auth.set(user.id, Users.HOST_SYMBOL);
		const token = require('crypto').randomBytes(8).toString('hex');
		require('fs').mkdirSync(SPECS, {recursive: true});
		require('fs').writeFileSync(require('path').join(SPECS, `${token}.json`),
			JSON.stringify({mons: spec.mons, sides: spec.sides, field: spec.field, ghost: spec.ghost, turn: spec.turn}));
		void battleRoom.battle.stream.write(`>eval require('./openvgc-position').patch(battle, '${token}')`);
		this.parse(`/join ${battleRoom.roomid}`);
		setTimeout(() => {
			const {t} = (() => {
				try { return require(require('path').join(__dirname.split(/[\\/]dist[\\/]/)[0], 'dist', 'server', 'openvgc-i18n.js')); } catch { return require('./openvgc-i18n.js'); }
			})();
			battleRoom.add(`|uhtmlchange|invites|<div class="broadcast broadcast-blue"><strong>${t('A position rebuilt from a replay')}</strong><br />` +
				t("HP from the replay's percentages, guessed spreads and unseen sets, a new seed. Turns 1 to now replay the field and the mons already seen as the log showed them.") +
				`</div>`);
			battleRoom.add(`|uhtml|invites|`).update();
			battleRoom.battle.sendInviteForm(user);
		}, 500);
	},
};
