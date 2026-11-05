'use strict';









const crypto = require('crypto');
const { runBattle, DEFAULT_FORMAT } = require('./lib/run-battle');

function parseArgs(argv) {
	const args = { seeds: 1000, format: DEFAULT_FORMAT, maxTurns: 100 };
	for (let i = 0; i < argv.length; i++) {
		const a = argv[i];
		if (a === '--seeds') args.seeds = Number(argv[++i]);
		else if (a === '--format') args.format = argv[++i];
		else if (a === '--max-turns') args.maxTurns = Number(argv[++i]);
		else throw new Error(`Unknown arg: ${a}`);
	}
	return args;
}

function hashOf(result) {
	return crypto.createHash('sha256').update(JSON.stringify(result)).digest('hex').slice(0, 16);
}

(async () => {
	const { seeds, format, maxTurns } = parseArgs(process.argv.slice(2));
	const failures = [];
	const hitMaxTurns = [];
	let totalTurns = 0;
	const start = Date.now();

	for (let seed = 1; seed <= seeds; seed++) {
		try {
			const result = await runBattle({ seed, format, maxTurns });
			totalTurns += result.turnCount;
			const last = result.turns[result.turns.length - 1];
			if (!last || !last.ended) hitMaxTurns.push(seed);
		} catch (err) {
			failures.push({ seed, error: err.stack || String(err) });
		}
	}

	const elapsed = ((Date.now() - start) / 1000).toFixed(1);
	console.log(`ran ${seeds} seeds in ${elapsed}s (${(seeds / elapsed).toFixed(1)}/s), ` +
		`${totalTurns} total turns, format=${format}, maxTurns=${maxTurns}`);
	console.log(`failures: ${failures.length}, hit max-turns without ending: ${hitMaxTurns.length}`);

	if (failures.length) {
		console.log('--- first failures ---');
		for (const f of failures.slice(0, 5)) console.log(`seed ${f.seed}:\n${f.error}\n`);
	}
	if (hitMaxTurns.length) {
		console.log(`seeds hitting max-turns (first 20): ${hitMaxTurns.slice(0, 20).join(', ')}`);
	}


	const sample = [1, Math.ceil(seeds / 2), seeds].filter(s => s >= 1 && s <= seeds);
	let determinismOk = true;
	for (const seed of sample) {
		const a = hashOf(await runBattle({ seed, format, maxTurns }));
		const b = hashOf(await runBattle({ seed, format, maxTurns }));
		if (a !== b) {
			determinismOk = false;
			console.log(`DETERMINISM MISMATCH at seed ${seed}: ${a} != ${b}`);
		}
	}
	console.log(`determinism spot-check (seeds ${sample.join(', ')}): ${determinismOk ? 'ok' : 'FAILED'}`);

	process.exitCode = (failures.length || !determinismOk) ? 1 : 0;
})().catch(err => {
	console.error(err.stack || err);
	process.exitCode = 1;
});
