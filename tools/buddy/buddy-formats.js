'use strict';









const BASE = [
	'[Gen 9 Champions] VGC 2026 Reg M-C', '[Gen 9 Champions] VGC 2026 Reg M-C (Bo3)',
	'[Gen 5] VGC 2013', '[Gen 6] VGC 2014', '[Gen 6] VGC 2015', '[Gen 6] VGC 2016',
	'[Gen 7] VGC 2017', '[Gen 7] VGC 2018', '[Gen 7] VGC 2019',
	'[Gen 8] VGC 2020', '[Gen 8] VGC 2021', '[Gen 8] VGC 2022',
	'[Gen 9] VGC 2023 Reg C', '[Gen 9] VGC 2023 Reg D', '[Gen 9] VGC 2024 Reg G', '[Gen 9] VGC 2025 Reg I',
];
const all = require('./formats-showdown').Formats;
const twins = BASE.map(name => {
	const f = all.find(x => x.name === name);
	if (!f) throw new Error(`buddy formats: no format named ${name} in this server`);
	const copy = Object.assign({}, f, {name: `${name} buddy`});
	delete copy.section; delete copy.column;
	return copy;
});
exports.Formats = [{section: 'Training buddy (local)', column: 1}, ...twins];
