






'use strict';
const fs = require('fs');
const path = require('path');


function root() {
	if (process.env.OPENVGC_ROOT) return process.env.OPENVGC_ROOT;
	let d = __dirname;
	for (let i = 0; i < 10; i++) {
		if (fs.existsSync(path.join(d, 'data', 'i18n', 'ja', 'ui.json'))) return d;
		d = path.dirname(d);
	}
	return null;
}

const cache = new Map();
function load(rel) {
	const r = root();
	if (!r) return {};
	const f = path.join(r, rel);
	let st;
	try {
		st = fs.statSync(f).mtimeMs;
	} catch {
		return {};
	}
	const hit = cache.get(f);
	if (hit && hit.st === st) return hit.v;
	let v = {};
	try {
		v = JSON.parse(fs.readFileSync(f, 'utf8'));
	} catch {}
	cache.set(f, {st, v});
	return v;
}


function language() {
	const l = load('trainer/runs/app_settings.json').language;
	return l === 'ja' || l === 'qps' ? l : 'en';
}

function term(key, lang) {
	const e = load('data/i18n/ja/terms.json')[key] || {};
	return ((lang || language()) !== 'en' ? e.ja : e.en) || e.en || key;
}


function t(text, slots, lang) {
	lang = lang || language();
	let out = text;
	if (lang !== 'en') {
		const e = load('data/i18n/ja/ui.json')[text];
		if (e && e.ja) out = e.ja.replace(/\{t:([a-z0-9_]+)\}/g, (_, k) => term(k, 'ja'));
		if (lang === 'qps') out = `［${text}］`;
	}
	if (slots) out = out.replace(/\{([a-z_][a-z0-9_]*)\}/g, (m, k) => (k in slots ? String(slots[k]) : m));
	return out;
}

module.exports = {language, t, term, root};
