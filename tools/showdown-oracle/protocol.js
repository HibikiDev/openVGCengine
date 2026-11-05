'use strict';














const fs = require('fs');
const { Battle } = require('./lib/showdown');

function main() {
	const scenarioPath = process.argv[2];
	if (!scenarioPath) throw new Error('usage: node protocol.js <scenario.json>');
	const scenario = JSON.parse(fs.readFileSync(scenarioPath, 'utf8'));
	const pending = { p1: [], p2: [] };
	const requests = { p1: null, p2: null };
	const battle = new Battle({
		formatid: scenario.format,
		seed: scenario.seed,
		p1: { name: 'p1', team: scenario.team1 },
		p2: { name: 'p2', team: scenario.team2 },
		send: (type, data) => {
			const text = Array.isArray(data) ? data.join('\n') : data;
			if (type === 'update') {
				const lines = text.split('\n');
				for (let i = 0; i < lines.length; i++) {
					const m = /^\|split\|(p[12])$/.exec(lines[i]);
					if (m) {
						const owner = m[1];
						for (const p of ['p1', 'p2']) pending[p].push(p === owner ? lines[i + 1] : lines[i + 2]);
						i += 2;
						continue;
					}
					if (lines[i] === '') continue;
					for (const p of ['p1', 'p2']) pending[p].push(lines[i]);
				}
			} else if (type === 'sideupdate') {
				const [side, ...rest] = text.split('\n');
				for (const line of rest) {
					if (line.startsWith('|request|')) requests[side] = JSON.parse(line.slice('|request|'.length));
				}
			}
		},
	});
	const steps = [];
	const snapshot = () => {
		const entry = {};
		for (const p of ['p1', 'p2']) {
			const req = battle[p].activeRequest;
			const waiting = !req || req.wait || req.teamPreview;
			entry[p] = { lines: pending[p].splice(0), request: waiting ? null : requests[p] };
		}
		steps.push(entry);
	};
	const choose = (side, input) => {
		if (input.trim() === 'pass, pass') return;
		if (!battle.choose(side, input)) throw new Error(`choice rejected: ${side} "${input}"`);
	};
	choose('p1', 'team 1234');
	choose('p2', 'team 1234');
	battle.sendUpdates();
	snapshot();
	for (const t of scenario.turns) {
		choose('p1', t.p1);
		choose('p2', t.p2);
		battle.sendUpdates();
		snapshot();
	}
	console.log(JSON.stringify({ scenario: scenarioPath, steps }));
}

main();
