












'use strict';

const {t} = (() => {
	try { return require(require('path').join(__dirname.split(/[\\/]dist[\\/]/)[0], 'dist', 'server', 'openvgc-i18n.js')); } catch { return require('./openvgc-i18n.js'); }
})();

const COACH = 'openvgccoach';
const toID = s => String(s).toLowerCase().replace(/[^a-z0-9]+/g, '');
const esc = s => String(s).replace(/[&<>"']/g, c => ({'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'}[c]));
const pct = p => `${Math.round(Math.max(0, Math.min(1, p)) * 100)}%`;

function bad(msg) {
	return new Error(`openvgccoach: ${msg}`);
}

function label(s, max) {
	if (typeof s !== 'string' || !s.length || s.length > max) throw bad(`a label must be a string of 1-${max} characters`);
	return s;
}

function share(p) {
	if (typeof p !== 'number' || !(p >= 0 && p <= 1)) throw bad('a share must be a number from 0 to 1');
	return p;
}

function count(k, max) {
	if (!Number.isInteger(k) || k < 0 || k > max) throw bad(`a count must be an integer from 0 to ${max}`);
	return k;
}


function check(d) {
	if (!d || typeof d !== 'object') throw bad('not an object');
	const out = {to: toID(label(d.to, 18)), turn: count(d.turn, 999), win: share(d.win), guessed: !!d.guessed};
	if (!Array.isArray(d.slots) || d.slots.length > 2) throw bad('slots: a list of up to two');
	const mons = (list, what) => {
		if (!Array.isArray(list) || list.length > 2) throw bad(`${what}: a list of up to two`);
		return list.map(sl => {
			if (!sl || !Array.isArray(sl.top) || sl.top.length > 3) throw bad(`${what}: each needs a top list of up to three`);
			return {mon: label(sl.mon, 40), top: sl.top.map(x => [label(x[0], 80), share(x[1])])};
		});
	};
	out.slots = mons(d.slots, 'slots');
	out.foe = d.foe === undefined || d.foe === null ? [] : mons(d.foe, 'foe');
	out.n = count(d.n, 16);
	out.votes = count(d.votes, out.n);
	out.best = d.best === null || d.best === undefined ? null : label(d.best, 160);
	out.alt = d.alt === null || d.alt === undefined || !out.best ? null : label(d.alt, 160);
	out.alt_votes = out.alt ? count(d.alt_votes, out.n - out.votes) : 0;
	return out;
}



function panel(d) {
	let body;
	if (d.best && d.alt) {
		body = `<div>${t('The searches split:')} <strong>${esc(d.best)}</strong> <small>(${t('{k} of {n}', {k: d.votes, n: d.n})})</small>` +
			` ${t('or')} <strong>${esc(d.alt)}</strong> <small>(${t('{k} of {n}', {k: d.alt_votes, n: d.n})})</small></div>`;
	} else if (d.best) {
		body = `<div>${t('Suggested:')} <strong>${esc(d.best)}</strong> <small>(${d.votes === d.n ? (d.n === 2 ? t('both searches agree') : t('all {n} searches agree', {n: d.n})) : t('the top line in {k} of {n} searches', {k: d.votes, n: d.n})})</small></div>`;
	} else {
		body = `<div><small>${t("No search this turn; the model's quick read:")}</small></div>` + d.slots.map(sl => `<div><strong>${esc(sl.mon)}</strong>: ` +
			sl.top.map(([l, p]) => `${esc(l)} <small>${pct(p)}</small>`).join(' · ') + '</div>').join('');
	}

	const foe = d.foe.length ? `<div><small>${t('Expected from them:')}</small> ` + d.foe.map(sl => `<strong>${esc(sl.mon)}</strong>: ` +
		sl.top.map(([l, p]) => `${esc(l)} <small>${pct(p)}</small>`).join(' · ')).join('; ') + '</div>' : '';
	const note = d.guessed ? `<div><small>${t("The other side's sets are partly guessed.")}</small></div>` : '';
	return `<div class="infobox"><strong>${t('Coach · turn {turn}', {turn: d.turn})}</strong> · ${t('win estimate {pct}', {pct: pct(d.win)})}${body}${foe}${note}` +
		`<div><small>${t("Only you see this. Turn it off with the Coach box on the dashboard's Buddy page.")}</small></div></div>`;
}

exports.check = check;
exports.panel = panel;

exports.commands = {
	openvgccoach(target, room, user) {
		if (user.id !== COACH) return this.errorReply('Only the coach account sends coach panels.');
		if (!room || !room.battle) return this.errorReply('Not a battle room.');
		let d;
		try {
			d = check(JSON.parse(target));
		} catch (e) {
			return this.errorReply(e.message);
		}
		const to = Users.get(d.to);
		if (!to || !room.battle.playerTable[to.id]) return this.errorReply('Coach panels go to a player of this battle.');
		room.sendUser(to, `|uhtml|openvgccoach${d.turn}|${panel(d)}`);
	},
};
