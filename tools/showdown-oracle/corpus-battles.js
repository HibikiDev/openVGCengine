'use strict';





















const fs = require('fs');
const path = require('path');
const { Battle, Teams } = require('./lib/showdown');
const { splitmix32, deriveSeed } = require('./lib/seed');
const { assignGenders } = require('./lib/gender');
const { assignHappiness } = require('./lib/happiness');
const { legalChoices } = require('./lib/legal-probe');

let FORMAT = 'gen9championsvgc2026regmc';
const TEAMS_PATH = path.join(__dirname, '..', 'corpus', 'out', 'teams-champions-mc.json');

const LEGAL_MOVES = new Set(require('../gen-data/out/moves.json').map(m => m.id));
const toId = s => s.toLowerCase().replace(/[^a-z0-9]/g, '');

function pick(rng, arr) {
	return arr[rng() % arr.length];
}

function shuffle(rng, arr) {
	const a = [...arr];
	for (let i = a.length - 1; i > 0; i--) {
		const j = rng() % (i + 1);
		[a[i], a[j]] = [a[j], a[i]];
	}
	return a;
}






function loadTeamFile(file, requireItems) {
	const doc = JSON.parse(fs.readFileSync(file, 'utf8'));
	if (doc.format && doc.format !== FORMAT) {


		FORMAT = doc.format;
		const ported = new Set(require('../gen-data/out/ported-moves.json'));
		const portedMove = m => ported.has(/^hiddenpower/.test(toId(m)) ? 'hiddenpower' : toId(m));
		const out = name => require(path.join(__dirname, '..', 'gen-data', 'out', name));
		const unported = new Set([...out('pool-coverage.json').abilities, ...out('catalog-coverage.json').abilities,
			...out('pool-coverage.json').items, ...out('catalog-coverage.json').items].filter(e => e.status === 'unported').map(e => e.id));
		return doc.teams.filter(t => t.sets.every(s => s.moves.every(portedMove) && !unported.has(toId(s.item || '')) && !unported.has(toId(s.ability || ''))))
			.map(t => ({ id: t.id, sets: t.sets.map(s => ({ ...s, evs: { ...s.evs }, ivs: { ...s.ivs } })) }));
	}
	const cov = JSON.parse(fs.readFileSync(path.join(__dirname, '..', 'gen-data', 'out', 'pool-coverage.json'), 'utf8'));
	const missing = new Set([
		...cov.moves.filter(m => m.status !== 'implemented').map(m => m.id),
		...cov.abilities.filter(a => a.status === 'unported').map(a => a.id),
		...cov.items.filter(i => i.status === 'unported').map(i => i.id),
	]);

	const legalItems = new Set(cov.items.map(i => i.id));
	const out = [];
	for (const t of JSON.parse(fs.readFileSync(file, 'utf8')).teams) {
		const ids = t.sets.flatMap(s => [...s.moves.map(toId), toId(s.ability || ''), toId(s.item || '')]);
		if (ids.some(id => missing.has(id))) continue;
		if (t.sets.some(s => s.item && !legalItems.has(toId(s.item)))) continue;
		if (requireItems && !t.sets.some(s => [s.item, s.ability].some(x => requireItems.includes(toId(x || ''))))) continue;
		out.push({ id: t.id, sets: t.sets.map(s => ({ ...s, evs: { ...s.evs } })) });
	}
	return out;
}

function loadTeams() {
	const raw = JSON.parse(fs.readFileSync(TEAMS_PATH, 'utf8')).teams;
	const out = [];
	for (const t of raw) {
		if (!t.has_evs) continue;
		const sets = Teams.import(t.text);
		if (!sets || sets.length !== 6) continue;

		for (const s of sets) {
			if (!/^groudon/i.test(s.species)) s.moves = s.moves.map(mv => (mv.toLowerCase().replace(/[^a-z]/g, '') === 'precipiceblades' ? 'Protect' : mv));
		}
		if (sets.some(s => s.moves.some(mv => !LEGAL_MOVES.has(toId(mv))))) continue;
		out.push({ id: t.team_id, sets });
	}
	return out;
}

function toFixtureSet(set, i) {
	return {
		name: `Mon${i}`, species: set.species, item: set.item || '', ability: set.ability || '', moves: [...set.moves], nature: set.nature || 'Hardy',
		evs: { hp: set.evs.hp || 0, atk: set.evs.atk || 0, def: set.evs.def || 0, spa: set.evs.spa || 0, spd: set.evs.spd || 0, spe: set.evs.spe || 0 },
		ivs: set.ivs ? { ...set.ivs } : { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, level: 50, gender: 'N',

		...(set.teraType ? { teraType: set.teraType } : {}),
	};
}







function chooseFor(rng, battle, side, opts) {
	let legal = legalChoices(battle, side);
	if (!legal || !legal.length) return null;
	if (!opts.switches && !side.activeRequest.forceSwitch) {
		const noSwitch = legal.filter(c => !c.includes('switch'));
		if (noSwitch.length) legal = noSwitch;
	}


	const notPass = legal.filter(c => c !== 'pass, pass');
	if (notPass.length) legal = notPass;
	const choice = pick(rng, legal);
	return battle.choose(side.id, choice) ? choice : null;
}

function playBattle(rng, team1, team2, seed, maxTurns, opts) {
	const battle = new Battle({ formatid: FORMAT, seed, p1: { name: 'p1', team: team1 }, p2: { name: 'p2', team: team2 } });
	if (!battle.choose('p1', 'team 1234') || !battle.choose('p2', 'team 1234')) return null;
	const turns = [];
	while (!battle.ended && turns.length < maxTurns) {
		const entry = {};


		const requests = battle.sides.map(side => ({ side, req: side.activeRequest }));
		for (const { side, req } of requests) {
			if (!req || req.wait || req.teamPreview) { entry[side.id] = 'pass, pass'; continue; }
			const choice = chooseFor(rng, battle, side, opts);
			if (choice === null) return null;
			entry[side.id] = choice;
		}
		turns.push(entry);
	}
	return turns;
}

function main() {
	const args = { count: 20, seed: 1, outDir: null, maxTurns: 12, switches: true, inject: null, injectPerMon: 2 };
	const argv = process.argv.slice(2);
	for (let i = 0; i < argv.length; i++) {
		if (argv[i] === '--count') args.count = parseInt(argv[++i], 10);
		else if (argv[i] === '--seed') args.seed = parseInt(argv[++i], 10);
		else if (argv[i] === '--out-dir') args.outDir = argv[++i];
		else if (argv[i] === '--max-turns') args.maxTurns = parseInt(argv[++i], 10);
		else if (argv[i] === '--no-switch') args.switches = false;
		else if (argv[i] === '--inject') args.inject = argv[++i].split(',');
		else if (argv[i] === '--inject-per-mon') args.injectPerMon = parseInt(argv[++i], 10);
		else if (argv[i] === '--teams-file') args.teamsFile = argv[++i];
		else if (argv[i] === '--require-items') args.requireItems = argv[++i].split(',');
		else if (argv[i] === '--inject-abilities') args.injectAbilities = argv[++i].split(',');
		else if (argv[i] === '--inject-items') args.injectItems = argv[++i].split(',');
		else throw new Error(`Unknown arg: ${argv[i]}`);
	}
	if (!args.outDir) throw new Error('--out-dir is required');
	fs.mkdirSync(args.outDir, { recursive: true });
	const teams = args.teamsFile ? loadTeamFile(args.teamsFile, args.requireItems) : loadTeams();
	const rng = splitmix32(args.seed);
	let written = 0;
	for (let i = 0; i < args.count; i++) {
		const a = pick(rng, teams);
		let b = pick(rng, teams);
		while (b === a) b = pick(rng, teams);
		const cut = t => shuffle(rng, t.sets).slice(0, 4).map(toFixtureSet);
		const team1 = cut(a);
		const team2 = cut(b);
		if (args.inject) {
			for (const set of [...team1, ...team2]) {
				for (const slot of shuffle(rng, [0, 1, 2, 3]).slice(0, args.injectPerMon)) {

					const fresh = args.inject.filter(m => !set.moves.some(x => toId(x) === m) && !(m === 'transform' && /ite( ?[xyz])?$/i.test(set.item)));
					if (fresh.length) set.moves[slot] = pick(rng, fresh);
				}

				set.moves = set.moves.filter(m => m);
			}
		}
		if (args.injectAbilities) {


			for (const set of [...team1, ...team2]) {
				if (rng() % 2) {
					const ability = pick(rng, args.injectAbilities);
					if (!(ability === 'Imposter' && /ite( ?[xyz])?$/i.test(set.item))) set.ability = ability;
				}
			}
		}
		if (args.injectItems) {

			for (const set of [...team1, ...team2]) if (rng() % 2 && !/ite( ?[xyz])?$/i.test(set.item)) set.item = pick(rng, args.injectItems);
		}

		assignGenders([...team1, ...team2], splitmix32(((args.seed | 0) * 7919 + i) ^ 0x6e6));
		assignHappiness([...team1, ...team2], splitmix32(((args.seed | 0) * 7919 + i) ^ 0x4a9));
		const seed = deriveSeed(args.seed, `corpus-${i}`);
		let turns;
		try {
			turns = playBattle(rng, team1, team2, seed, args.maxTurns, { switches: args.switches });
		} catch (e) {
			console.error(`scenario ${i} (${a.id} vs ${b.id}) threw while generating: ${e.message}`);
			continue;
		}
		if (!turns) { console.error(`scenario ${i}: no legal choice found`); continue; }
		const scenario = { format: FORMAT, seed, team1, team2, turns, teams: [a.id, b.id] };
		fs.writeFileSync(path.join(args.outDir, `scenario-${i}.json`), JSON.stringify(scenario, null, '\t'));
		written++;
	}
	console.log(`wrote ${written} corpus battles to ${args.outDir}`);
}

main();
