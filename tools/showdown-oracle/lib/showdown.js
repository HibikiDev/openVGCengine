'use strict';

const path = require('path');






const SHOWDOWN_ROOT = process.env.SHOWDOWN_PATH ||
	path.join(__dirname, '..', '..', '..', 'vendor', 'pokemon-showdown');
const SHOWDOWN_SIM = path.join(SHOWDOWN_ROOT, 'dist', 'sim');

module.exports = {
	SHOWDOWN_ROOT,
	SHOWDOWN_SIM,
	...require(SHOWDOWN_SIM),
	RandomPlayerAI: require(path.join(SHOWDOWN_SIM, 'tools', 'random-player-ai')).RandomPlayerAI,
};
