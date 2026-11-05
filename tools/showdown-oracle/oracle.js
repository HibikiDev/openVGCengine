'use strict';













const { runBattle, DEFAULT_FORMAT } = require('./lib/run-battle');

function parseArgs(argv) {
	const args = { seed: 1, format: DEFAULT_FORMAT, maxTurns: 100 };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--seed') args.seed = Number(argv[++i]);
		else if (a === '--format') args.format = argv[++i];
		else if (a === '--max-turns') args.maxTurns = Number(argv[++i]);
		else throw new Error(`Unknown arg: ${a}`);
	}
	return args;
}

(async () => {
	const args = parseArgs(process.argv.slice(2));
	const result = await runBattle(args);
	console.log(JSON.stringify(result, null, 2));
})().catch(err => {
	console.error(err.stack || err);
	process.exitCode = 1;
});
