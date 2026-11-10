





'use strict';
const I = (() => {
	try { return require(require('path').join(__dirname.split(/[\\/]dist[\\/]/)[0], 'dist', 'server', 'openvgc-i18n.js')); } catch { return require('./openvgc-i18n.js'); }
})();
const LEGACY = {ja: 'japanese', en: 'english'};

exports.loginfilter = (user) => {
	if (user.language) return;
	const lang = LEGACY[I.language()];
	if (!lang || lang === 'english') return;
	user.language = lang;
	user.update();
};
