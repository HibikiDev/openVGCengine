'use strict';

































const fs = require('fs');
const path = require('path');
const { splitmix32, deriveSeed } = require('./lib/seed');
const { assignGenders } = require('./lib/gender');
const { assignHappiness } = require('./lib/happiness');
const { Dex, Battle } = require('./lib/showdown');
const { legalChoices } = require('./lib/legal-probe');

let MOVE_DEX = Dex.mod('champions');

let FORMAT = 'gen9championsvgc2026regmc';

let PLAY_TURNS = 1;















const SPECIES = [
	'rillaboom', 'sneasler', 'salamence', 'incineroar', 'kingambit', 'indeedeef', 'basculegion',
	'gholdengo', 'floetteeternal', 'garchomp', 'golisopod', 'milotic', 'arcaninehisui', 'sylveon',
	'raichu', 'pelipper', 'farigiraf', 'archaludon', 'charizard', 'tyranitar', 'armarouge',
	'excadrill', 'gardevoir', 'indeedee', 'baxcalibur', 'torkoal', 'lucario', 'volcarona', 'gengar',
	'staraptor', 'sinistcha', 'metagross', 'glimmora', 'whimsicott', 'pawmot', 'politoed', 'kommoo',
	'swampert', 'froslass', 'venusaur', 'grimmsnarl', 'absol', 'dragonite', 'delphox', 'blastoise',
	'aerodactyl', 'hatterene', 'ninetalesalola', 'meowsticf', 'corviknight', 'annihilape', 'blaziken',
	'mawile', 'dragapult', 'talonflame', 'hydreigon', 'ceruledge', 'primarina', 'toxapex',
	'camerupt', 'sirfetchd', 'sinistchamasterpiece', 'altaria', 'toxtricity', 'typhlosionhisui',
	'gallade', 'scrafty', 'vivillon', 'sableye', 'bellibolt', 'pyroar', 'aegislash', 'vanilluxe',
	'alakazam', 'lycanrocdusk', 'mausholdfour', 'tsareena', 'pincurchin', 'zoroarkhisui', 'snorlax',
	'scizor', 'grapploct', 'rotomheat', 'noivern', 'hippowdon', 'gyarados', 'meganium', 'empoleon',
	'cinderace', 'klefki', 'raichualola', 'dragalge', 'mimikyu', 'torterra', 'kangaskhan', 'sceptile',
	'starmie', 'gliscor', 'espathra', 'rotomwash', 'lopunny', 'meowscarada', 'squawkabilly',
	'maushold', 'arboliva', 'scovillain', 'manectric', 'glalie', 'medicham', 'rotommow', 'clefable',
	'perrserker', 'overqwil', 'houndstone', 'typhlosion', 'thievul', 'weavile', 'gogoat', 'zoroark',
	'skeledirge', 'malamar', 'tinkaton', 'chandelure', 'clawitzer', 'abomasnow', 'mudsdale',
	'chimecho', 'aggron', 'crabominable', 'hawlucha', 'basculegionf', 'persianalola', 'arcanine',
	'salazzle',
];













const MOVES = [
	'tackle', 'closecombat', 'earthquake', 'protect', 'swordsdance',
	'raindance', 'sunnyday', 'sandstorm', 'tailwind', 'trickroom',
	'reflect', 'lightscreen', 'auroraveil', 'stealthrock', 'spikes', 'toxicspikes', 'stickyweb',
	'electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain',

	'hypervoice', 'grassyglide', 'woodhammer', 'kowtowcleave', 'wavecrash', 'dazzlinggleam',
	'aquajet', 'nastyplot', 'calmmind', 'powergem', 'extremespeed', 'doubleedge', 'quickattack',
	'dragonclaw', 'armorcannon', 'iceshard', 'dragondance', 'recover', 'clangingscales',
	'shadowclaw', 'bulkup', 'nightslash', 'quiverdance', 'superpower', 'shadowsneak',
	'shellsmash', 'bulletpunch', 'overdrive', 'psychocut', 'machpunch', 'boomburst', 'accelerock',
	'charm', 'irondefense', 'faketears', 'headlongrush', 'leafblade', 'seedbomb', 'vacuumwave',
	'slash', 'slackoff', 'gigatonhammer', 'tickle', 'agility', 'xscissor', 'fakeout',

	'gigadrain', 'drainingkiss', 'drainpunch', 'bitterblade', 'hornleech', 'bravebird',
	'stormthrow', 'flowertrick', 'feint', 'knockoff',






	'dragonpulse', 'aurasphere', 'detect', 'leechlife',

	'electroshot', 'solarbeam',


	'ragepowder',

	'darkestlariat', 'terrainpulse', 'stompingtantrum', 'perishsong', 'bodypress', 'coil', 'psychicfangs', 'lifedew', 'roost', 'doubleshock', 'taunt', 'yawn', 'imprison',

	'psyshock', 'sacredsword', 'foulplay', 'grassknot', 'heavyslam', 'acrobatics', 'hex', 'risingvoltage', 'flamecharge', 'torchsong',

	'brickbreak', 'firstimpression', 'steelroller', 'howl', 'haze', 'powertrip', 'temperflare', 'healpulse',


	'encore',

	'waterspout', 'assurance', 'focusenergy', 'clangoroussoul', 'glaiverush', 'soak', 'psychup', 'psychicnoise', 'alluringvoice',

	'ragefist', 'magicpowder', 'memento', 'finalgambit', 'explosion', 'bugbite', 'quash', 'beatup',

	'skillswap', 'stockpile', 'healingwish', 'gravity',


	'round', 'phantomforce',

	'endure', 'smackdown', 'entrainment',
];



















const BRANCHING_MOVES = ['muddywater', 'nightdaze', 'firespin', 'infestation', 'hurricane', 'waterpulse', 'blizzard', 'hyperbeam', 'nuzzle', 'superfang', 'ancientpower', 'trick', 'freezedry', 'fierydance',


	'dualwingbeat', 'twinbeam', 'iciclespear', 'tripleaxel', 'scaleshot', 'populationbomb', 'poltergeist', 'bellydrum', 'minimize',

	'steelbeam', 'highjumpkick', 'icefang',

	'triattack', 'barbbarrage', 'fissure', 'sheercold',

	'allyswitch', 'roar', 'dragontail',

	'substitute',


	'acidarmor', 'acidspray', 'aerialace', 'aircutter', 'amnesia', 'appleacid', 'aquacutter', 'aquastep', 'aquatail', 'aromaticmist',
	'babydolleyes', 'blazekick', 'bonerush', 'brutalswing', 'bulldoze', 'bulletseed', 'chargebeam', 'chillingwater', 'cosmicpower',
	'cottonguard', 'cottonspore', 'crabhammer', 'crosspoison', 'crushclaw', 'decorate', 'doublehit', 'doublekick', 'doubleteam',
	'dragonrush', 'drillpeck', 'eerieimpulse', 'extrasensory', 'featherdance', 'firefang', 'firelash', 'firepunch', 'frostbreath',
	'furyattack', 'glare', 'harden', 'headbutt', 'inferno', 'irontail', 'jetpunch', 'lavaplume', 'lowsweep', 'lunge', 'magicalleaf',
	'megahorn', 'megakick', 'metalsound', 'meteormash', 'mountaingale', 'mudshot', 'mudslap', 'nobleroar', 'peck', 'petalblizzard',
	'pinmissile', 'poisonfang', 'poisonpowder', 'pounce', 'pound', 'powdersnow', 'psyshieldbash', 'razorshell', 'rockblast',
	'rockpolish', 'scaryface', 'screech', 'shadowpunch', 'shelter', 'shiftgear', 'skittersmack', 'slam', 'sludgewave', 'smartstrike',
	'spicyextract', 'steelwing', 'stringshot', 'stunspore', 'surf', 'sweetscent', 'swift', 'tailslap', 'takedown', 'tearfullook',
	'thunderfang', 'toxicthread', 'trailblaze', 'triplearrows', 'tropkick', 'vinewhip', 'volttackle', 'watergun', 'wildcharge',
	'zenheadbutt',

	'blastburn', 'frenzyplant', 'gigaimpact', 'hydrocannon', 'rockwrecker', 'bind', 'wrap', 'sandtomb', 'whirlpool', 'snaptrap', 'flail', 'reversal', 'electroball', 'gyroball', 'heatcrash', 'hardpress', 'storedpower', 'facade', 'venoshock', 'payback', 'skyattack', 'meteorbeam', 'solarblade',

	'dig', 'dive', 'fly', 'bounce',

	'confuseray', 'sweetkiss', 'teeterdance', 'swagger', 'flatter', 'dynamicpunch', 'axekick', 'supercellslam', 'moonlight', 'morningsun', 'synthesis', 'nightshade', 'seismictoss', 'endeavor', 'guillotine', 'horndrill', 'thunder', 'growth', 'clearsmog', 'snowscape',

	'rapidspin', 'mortalspin', 'icespinner', 'stoneaxe', 'ceaselessedge', 'circlethrow', 'whirlwind', 'selfdestruct', 'mistyexplosion', 'infernalparade', 'lashout', 'burningjealousy', 'gravapple', 'ficklebeam', 'painsplit',

	'guardswap', 'powerswap', 'topsyturvy', 'switcheroo', 'spite', 'tidyup', 'defog', 'healbell', 'strengthsap', 'corrosivegas', 'worryseed', 'reflecttype', 'afteryou',

	'covet', 'thief', 'fellstinger', 'flyingpress', 'burnup', 'eeriespell', 'sparklingaria', 'snipeshot', 'courtchange', 'charge', 'watershuriken', 'ragingbull', 'aurawheel',
	'spitup', 'swallow', 'pluck', 'aquaring', 'ingrain', 'magnetrise', 'wish', 'rest', 'snore', 'upperhand',
	'leechseed', 'saltcure', 'syrupbomb', 'curse', 'destinybond', 'powertrick',
	'meanlook', 'block', 'spiritshackle', 'jawlock', 'fairylock',
	'roleplay', 'pollenpuff', 'lastresort', 'lockon',
	'counter', 'mirrorcoat', 'metalburst', 'comeuppance', 'avalanche',
	'powersplit', 'guardsplit', 'speedswap', 'noretreat', 'octolock',
	'forestscurse', 'trickortreat',
	'stuffcheeks', 'teatime', 'belch', 'recycle',
	'outrage', 'thrash', 'petaldance', 'ragingfury',
	'safeguard', 'torment', 'shedtail',
	'focuspunch', 'beakblast', 'chillyreception',
	'magicroom', 'wonderroom', 'electrify', 'magneticflux',
	'gastroacid', 'shellsidearm',
	'dragondarts'];
let movePool = MOVES;
let fullMovePool = MOVES;



const CHOOSABLE_TARGETS = new Set(['normal', 'any', 'adjacentAlly', 'adjacentAllyOrSelf', 'adjacentFoe']);
const NEEDS_TARGET = new Set([
	'hurricane', 'waterpulse',
	'ragefist', 'magicpowder', 'memento', 'finalgambit', 'bugbite', 'quash', 'skillswap', 'round', 'roar', 'phantomforce', 'smackdown', 'entrainment', 'dragontail', 'beatup', 'triattack', 'barbbarrage', 'fissure', 'sheercold',
	'assurance', 'glaiverush', 'soak', 'psychup', 'psychicnoise', 'alluringvoice', 'steelbeam', 'highjumpkick', 'icefang',
	'superfang', 'knockoff',
	'feint', 'stormthrow', 'flowertrick', 'firespin', 'infestation',
	'nightdaze', 'gigadrain', 'drainingkiss', 'drainpunch', 'bitterblade', 'hornleech', 'bravebird',
	'tackle', 'closecombat',
	'grassyglide', 'woodhammer', 'kowtowcleave', 'wavecrash', 'aquajet', 'powergem',
	'extremespeed', 'doubleedge', 'quickattack', 'dragonclaw', 'armorcannon', 'iceshard',
	'shadowclaw', 'nightslash', 'superpower', 'shadowsneak', 'bulletpunch', 'psychocut',
	'machpunch', 'accelerock', 'charm', 'faketears', 'headlongrush', 'leafblade', 'seedbomb',
	'vacuumwave', 'slash', 'gigatonhammer', 'tickle', 'xscissor', 'fakeout', 'nuzzle',
	'dragonpulse', 'aurasphere', 'leechlife', 'electroshot', 'solarbeam', 'hyperbeam', 'encore', 'darkestlariat', 'terrainpulse', 'ancientpower', 'stompingtantrum', 'bodypress', 'psychicfangs', 'doubleshock', 'taunt', 'yawn', 'trick',
	'psyshock', 'sacredsword', 'foulplay', 'grassknot', 'heavyslam', 'acrobatics', 'hex', 'freezedry', 'risingvoltage', 'flamecharge', 'torchsong', 'fierydance',
	'dualwingbeat', 'twinbeam', 'iciclespear', 'tripleaxel', 'scaleshot', 'populationbomb',
	'brickbreak', 'firstimpression', 'steelroller', 'powertrip', 'poltergeist', 'temperflare', 'healpulse',
]);
for (const id of [...MOVES, ...BRANCHING_MOVES]) {
	if (CHOOSABLE_TARGETS.has(MOVE_DEX.moves.get(id).target)) NEEDS_TARGET.add(id);
}

const NATURES = [
	'hardy', 'lonely', 'brave', 'adamant', 'naughty', 'bold', 'docile', 'relaxed', 'impish', 'lax',
	'timid', 'hasty', 'serious', 'jolly', 'naive', 'modest', 'mild', 'quiet', 'bashful', 'rash',
	'calm', 'gentle', 'sassy', 'careful', 'quirky',
];



























































const ABILITIES = [
	'pressure', 'rivalry', 'shielddust', 'drizzle', 'drought', 'sandstream', 'snowwarning', 'intimidate', 'levitate',
	'clearbody', 'whitesmoke', 'hypercutter', 'innerfocus', 'scrappy', 'guarddog', 'rattled',
	'adaptability', 'defiant', 'competitive', 'electricsurge', 'grassysurge', 'psychicsurge',
	'roughskin', 'goodasgold', 'stamina', 'rockhead', 'sandrush',
	'blaze', 'torrent', 'chlorophyll', 'hospitality', 'thermalexchange',
	'justified', 'weakarmor', 'technician', 'ironfist', 'sharpness', 'soundproof', 'telepathy',
	'prankster', 'overgrow', 'raindish', 'filter', 'solidrock', 'infiltrator',
	'unburden', 'flashfire', 'pixilate', 'aerilate', 'armortail', 'flowerveil', 'toxicdebris',
	'mirrorarmor', 'lightningrod',

	'swiftswim', 'surgesurfer', 'contrary', 'superluck', 'moldbreaker', 'shellarmor', 'unaware', 'solarpower', 'thickfat',
	'furcoat', 'grasspelt', 'megalauncher', 'steelyspirit', 'multiscale', 'compoundeyes', 'friendguard',

	'moxie', 'voltabsorb', 'limber', 'magicguard', 'queenlymajesty', 'sturdy', 'naturalcure', 'bulletproof', 'seedsower',
	'cloudnine', 'damp', 'pickpocket', 'protean', 'libero', 'electromorphosis', 'stalwart', 'frisk', 'pressure',

	'klutz',

	'leafguard', 'waterbubble', 'supremeoverlord', 'reckless', 'sapsipper', 'marvelscale', 'bigpecks', 'heatproof', 'magmaarmor',
	'steadfast', 'eartheater',

	'slushrush', 'icebody', 'guts', 'swarm', 'motordrive', 'hungerswitch',

	'waterabsorb', 'dryskin', 'immunity', 'battlearmor', 'aftermath', 'gooey', 'quickfeet', 'longreach', 'merciless', 'analytic',

	'hydration', 'stakeout', 'liquidooze', 'purifyingsalt', 'suctioncups',

	'runaway', 'stall', 'poisonheal', 'sandspit', 'curiousmedicine', 'anticipation', 'gluttony',

	'cheekpouch', 'ripen', 'cudchew', 'receiver',
];



const BRANCHING_ABILITIES = ['moody', 'angerpoint', 'poisonpoint', 'illusion', 'keeneye', 'static', 'quickdraw', 'hustle', 'stench', 'shedskin', 'tangledfeet', 'illuminate', 'effectspore', 'forewarn', 'supersweetsyrup', 'harvest', 'pickup'];
let abilityPool = ABILITIES;
let itemPool = null;
let speciesPool = SPECIES;



const ITEMS = [
	'', 'leftovers', 'focussash', 'lifeorb', 'damprock', 'heatrock', 'icyrock', 'smoothrock', 'terrainextender',
	'lightclay', 'sitrusberry', 'miracleseed', 'fairyfeather', 'charcoal', 'blackglasses',
	'rockyhelmet', 'chopleberry', 'occaberry', 'colburberry',
	'passhoberry', 'roseliberry', 'habanberry', 'kasibberry', 'cobaberry', 'rindoberry',
	'choicescarf', 'whiteherb', 'electricseed', 'grassyseed', 'mistyseed', 'psychicseed',


	'mysticwater', 'twistedspoon', 'sharpbeak', 'nevermeltice', 'softsand', 'hardstone', 'magnet', 'expertbelt', 'normalgem',
	'babiriberry', 'tangaberry', 'ironball', 'lumberry', 'chestoberry', 'mentalherb', 'widelens', 'zoomlens',

	'chartiberry', 'kebiaberry', 'payapaberry', 'shucaberry', 'wacanberry', 'yacheberry', 'chilanberry', 'blackbelt', 'dragonfang',
	'metalcoat', 'poisonbarb', 'silkscarf', 'silverpowder', 'spelltag', 'muscleband', 'wiseglasses', 'cheriberry', 'aspearberry',
	'pechaberry', 'rawstberry', 'persimberry', 'scopelens', 'bigroot',


	'oranberry', 'shedshell',
];

function pick(rng, arr) {
	return arr[rng() % arr.length];
}


function randStatPoint(rng) {
	return rng() % 33;
}

function randomMon(rng, i) {
	const species = pick(rng, speciesPool);
	const nature = pick(rng, NATURES);
	const moves = [];

	const pool = movePool.length >= 4 ? movePool : null;
	while (moves.length < 4) {
		const m = pool ? pick(rng, pool) : moves.length < movePool.length ? pick(rng, movePool) : pick(rng, fullMovePool);
		if (!moves.includes(m)) moves.push(m);
	}
	if (LEGACY_FORMATS[FORMAT]) return evIvMon(rng, i, species, nature, moves);
	const evs = {
		hp: 32,
		atk: randStatPoint(rng), def: randStatPoint(rng), spa: randStatPoint(rng),
		spd: randStatPoint(rng), spe: randStatPoint(rng),
	};



	return {
		name: `Mon${i}`, species, item: pick(rng, itemPool), ability: pick(rng, abilityPool), moves, nature, evs,
		ivs: { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, level: 50, gender: 'N',
	};
}



const LEGACY_FORMATS = {
	gen5vgc2013: { mod: 'gen5', pool: 'vgc13' },
	gen6vgc2014: { mod: 'gen6xy', pool: 'vgc14' },
	gen6vgc2015: { mod: 'gen6', pool: 'vgc15' },
	gen6vgc2016: { mod: 'gen6', pool: 'vgc16' },

	gen7vgc2017: { mod: 'gen7sm', pool: 'vgc17' },
	gen7vgc2018: { mod: 'gen7', pool: 'vgc18' },
	gen7vgc2019: { mod: 'gen7', pool: 'vgc19' },


	gen9vgc2023regc: { mod: 'gen9predlc', pool: 'svc' },
	gen9vgc2023regd: { mod: 'gen9predlc', pool: 'svd' },
	gen9vgc2024regg: { mod: 'gen9', pool: 'svg' },
	gen9vgc2025regi: { mod: 'gen9', pool: 'svi' },



	gen8vgc2020: { mod: 'gen8dlc1', pool: 'vgc20' },
	gen8vgc2021: { mod: 'gen8', pool: 'vgc21' },
	gen8vgc2022: { mod: 'gen8', pool: 'vgc22' },
};



function evIvMon(rng, i, species, nature, moves) {
	const evs = { hp: 0, atk: 0, def: 0, spa: 0, spd: 0, spe: 0 };
	let left = 127;
	for (const stat of Object.keys(evs)) {
		const units = Math.min(rng() % 64, left);
		evs[stat] = units * 4;
		left -= units;
	}
	const ivs = {};
	for (const stat of Object.keys(evs)) ivs[stat] = rng() % 4 === 0 ? rng() % 32 : 31;
	return {
		name: `Mon${i}`, species, item: pick(rng, itemPool), ability: pick(rng, abilityPool), moves, nature, evs, ivs, level: 50,
		gender: 'N',
	};
}






function useLegacyPools(format) {
	const { mod, pool } = LEGACY_FORMATS[format];
	const out = name => require(path.join(__dirname, '..', 'gen-data', 'out', name));
	const unported = new Set([...out('pool-coverage.json').abilities, ...out('catalog-coverage.json').abilities,
		...out('pool-coverage.json').items, ...out('catalog-coverage.json').items].filter(e => e.status === 'unported').map(e => e.id));
	const ported = new Set(out('ported-moves.json'));
	const NO_REQUEST = new Set(['uturn', 'voltswitch', 'batonpass', 'ejectbutton']);

	NO_REQUEST.add('metronome');
	FORMAT = format;
	MOVE_DEX = Dex.mod(mod);

	speciesPool = out(`${pool}/species.json`).filter(sp => !sp.battleOnly && sp.forme !== 'Gmax')
		.map(sp => sp.id);
	movePool = out(`${pool}/moves.json`).map(m => m.id).filter(id => ported.has(id) && !NO_REQUEST.has(id));
	fullMovePool = movePool;

	abilityPool = out(`${pool}/abilities.json`).map(a => a.id).filter(id => !unported.has(id));
	itemPool = ['', ...out(`${pool}/items.json`).map(it => it.id).filter(id => !unported.has(id) && !NO_REQUEST.has(id))];
	for (const id of movePool) if (CHOOSABLE_TARGETS.has(MOVE_DEX.moves.get(id).target)) NEEDS_TARGET.add(id);
}

function randomTeam(rng) {
	return [0, 1, 2, 3].map(i => randomMon(rng, i));
}



function randomChoice(rng, team, leads = null) {
	const pickFor = slot => {
		const moves = leads ? leads[slot].moves : team[slot].moves;
		let moveIdx = rng() % 4;


		const vest = team[slot].item === 'assaultvest';
		const berry = !!MOVE_DEX.items.get(team[slot].item || '').isBerry;
		const disabled = m => m === 'belch' || (m === 'stuffcheeks' && !berry) || (vest && m !== 'mefirst' && MOVE_DEX.moves.get(m).category === 'Status');
		while (LEGACY_FORMATS[FORMAT] && disabled(moves[moveIdx]) && moves.some(m => !disabled(m))) moveIdx = rng() % 4;

		if (LEGACY_FORMATS[FORMAT] && moves.every(disabled)) return 'move 1';
		const moveId = moves[moveIdx];
		if (!NEEDS_TARGET.has(moveId)) return `move ${moveIdx + 1}`;



		const species = MOVE_DEX.species.get(team[slot].species);
		const typeForme = /^gen[567]/.test(FORMAT) && ['Arceus', 'Silvally'].includes(species.baseSpecies);
		const types = leads ? leads[slot].types : typeForme ? ['Normal'] : species.types;

		if (moveId === 'curse' && (!types.includes('Ghost') || MOVE_DEX.moves.get('curse').target === 'randomNormal')) return `move ${moveIdx + 1}`;

		const target = MOVE_DEX.moves.get(moveId).target;
		if (target === 'adjacentAlly') return `move ${moveIdx + 1} -${2 - slot}`;
		if (target === 'adjacentAllyOrSelf') return `move ${moveIdx + 1} -${(rng() % 2) + 1}`;
		const targetSlot = (rng() % 2) + 1;
		return `move ${moveIdx + 1} ${targetSlot}`;
	};
	if (FORMAT.startsWith('gen9vgc')) {

		const trng = splitmix32((rng() ^ 0x7e7a) >>> 0);
		const [c0, c1] = [pickFor(0), pickFor(1)];
		const isMove = c => /^move \d+( -?\d+)?$/.test(c);
		const which = trng() % 4;

		const canTera = slot => !leads || leads[slot].canTera;
		if (which === 0 && isMove(c0) && canTera(0)) return `${c0} terastallize, ${c1}`;
		if (which === 1 && isMove(c1) && canTera(1)) return `${c0}, ${c1} terastallize`;
		return `${c0}, ${c1}`;
	}
	if (!FORMAT.startsWith('gen7')) return `${pickFor(0)}, ${pickFor(1)}`;


	const zrng = splitmix32((rng() ^ 0x5a7e) >>> 0);
	let zUsed = false;
	const withZ = (choice, slot) => {
		const m = /^move (\d+)( -?\d+)?$/.exec(choice);
		if (!m || zUsed) return choice;
		const set = leads ? leads[slot] : team[slot];
		const moves = leads ? leads[slot].moves : team[slot].moves;
		const z = zMoveFor(set.item, set.species, moves[Number(m[1]) - 1]);
		if (!z || zrng() % 2) return choice;
		zUsed = true;
		const needsTarget = CHOOSABLE_TARGETS.has(MOVE_DEX.moves.get(z).target);
		const target = m[2] || (needsTarget ? ` ${(zrng() % 2) + 1}` : '');
		return `move ${m[1]}${needsTarget ? target : ''} zmove`;
	};
	return `${withZ(pickFor(0), 0)}, ${withZ(pickFor(1), 1)}`;
}


function zMoveFor(itemId, species, moveId) {
	const item = MOVE_DEX.items.get(itemId || '');
	const move = MOVE_DEX.moves.get(moveId);
	if (!item.exists || !item.zMove || !move.exists) return undefined;
	if (item.itemUser && !item.itemUser.includes(MOVE_DEX.species.get(species).name)) return undefined;
	if (item.zMoveFrom) return move.name === item.zMoveFrom ? Dex.toID(item.zMove) : undefined;
	if (move.type !== item.zMoveType) return undefined;
	if (move.category === 'Status') return move.id;
	return move.zMove && move.zMove.basePower ? MOVE_DEX.moves.all().find(z => z.isZ === item.id).id : undefined;
}


let Z_FOCUS = false;
let GMAX_FOCUS = false;



function giveGigantamax(team, gr) {

	const gmax = MOVE_DEX.species.all().filter(s => s.canGigantamax && speciesPool.includes(s.id));
	const gmaxMoves = [...new Set(gmax.map(s => s.canGigantamax))];
	const set = team[gr() % 2];
	const move = gmaxMoves[gr() % gmaxMoves.length];
	const holders = gmax.filter(s => s.canGigantamax === move);
	const species = holders[gr() % holders.length];
	const type = MOVE_DEX.moves.get(species.canGigantamax).type;
	const moves = fullMovePool.filter(id => {
		const m = MOVE_DEX.moves.get(id);
		return m.type === type && m.category !== 'Status' && !set.moves.includes(id);
	});
	set.species = species.name;
	set.gigantamax = true;
	if (moves.length) set.moves[gr() % set.moves.length] = moves[gr() % moves.length];
}
function giveCrystals(team, zr) {
	for (const set of team) {
		if (zr() % 2) continue;
		const move = MOVE_DEX.moves.get(set.moves[zr() % set.moves.length]);
		const crystal = MOVE_DEX.items.all().find(it => it.zMoveType === move.type && !it.zMoveFrom);
		if (crystal && itemPool.includes(crystal.id)) set.item = crystal.id;
	}
}

function randomScenario(rng, index, genSeed) {
	const team1 = randomTeam(rng);
	const team2 = randomTeam(rng);
	if (Z_FOCUS) {
		const zr = splitmix32(((genSeed | 0) * 7919 + index) ^ 0x2c7);
		giveCrystals(team1, zr);
		giveCrystals(team2, zr);
	}
	if (GMAX_FOCUS) {
		const gr = splitmix32(((genSeed | 0) * 7919 + index) ^ 0x6a3);
		giveGigantamax(team1, gr);
		giveGigantamax(team2, gr);
	}
	const turn = { p1: randomChoice(rng, team1), p2: randomChoice(rng, team2) };

	const grng = splitmix32(((genSeed | 0) * 7919 + index) ^ 0x6e6);
	assignGenders([...team1, ...team2], grng);
	assignHappiness([...team1, ...team2], splitmix32(((genSeed | 0) * 7919 + index) ^ 0x4a9));

	if (FORMAT.startsWith('gen9vgc')) {
		const tr = splitmix32(((genSeed | 0) * 7919 + index) ^ 0x7e2);
		const types = MOVE_DEX.types.all().filter(t => !t.isNonstandard || t.name === 'Stellar').map(t => t.name);
		for (const set of [...team1, ...team2]) set.teraType = types[tr() % types.length];

		const OGERPON_TERA = { ogerpon: 'Grass', ogerponwellspring: 'Water', ogerponhearthflame: 'Fire', ogerponcornerstone: 'Rock' };
		for (const set of [...team1, ...team2]) if (OGERPON_TERA[Dex.toID(set.species)]) set.teraType = OGERPON_TERA[Dex.toID(set.species)];

		for (const set of [...team1, ...team2]) if (Dex.toID(set.species) === 'terapagos') Object.assign(set, { teraType: 'Stellar', ability: 'terashift' });
	}






	const seed = deriveSeed(genSeed, `scenario-${index}`);


	if ([...team1.slice(0, 2), ...team2.slice(0, 2)].some(m => m.ability === 'imposter')) {
		const leads = startedLeads(seed, team1, team2);
		const irng = splitmix32(((genSeed | 0) * 7919 + index) ^ 0x1a7);
		turn.p1 = randomChoice(irng, team1, leads[0]);
		turn.p2 = randomChoice(irng, team2, leads[1]);
	}

	if ([...team1.slice(0, 2), ...team2.slice(0, 2)].some(m => m.ability === 'commander')) {
		const leads = startedLeads(seed, team1, team2);
		for (const [k, side] of ['p1', 'p2'].entries()) {
			const parts = turn[side].split(', ');
			leads[k].forEach((l, slot) => { if (l.commanding) parts[slot] = 'pass'; });
			turn[side] = parts.join(', ');
		}
	}



	const opening = openingSteps(seed, team1, team2, splitmix32(((genSeed | 0) * 7919 + index) ^ 0x3e1));
	const turns = opening || [turn];

	if (PLAY_TURNS > 1) return { format: FORMAT, seed, team1, team2, turns: playOn(seed, team1, team2, turns, splitmix32(((genSeed | 0) * 7919 + index) ^ 0x5d3)) };
	return { format: FORMAT, seed, team1, team2, turns };
}






function playOn(seed, team1, team2, turns, prng) {
	const battle = new Battle({ formatid: FORMAT, seed, p1: { name: 'p1', team: team1 }, p2: { name: 'p2', team: team2 } });
	battle.choose('p1', 'team 1234');
	battle.choose('p2', 'team 1234');
	const out = [];
	for (const step of turns) {
		for (const id of ['p1', 'p2']) if (step[id] !== 'pass, pass' && !battle.choose(id, step[id])) return out.length ? out : turns;
		out.push(step);
		if (battle.ended) return out;
	}
	while (!battle.ended && out.length < PLAY_TURNS) {
		const entry = {};
		const requests = battle.sides.map(side => ({ side, req: side.activeRequest }));
		for (const { side, req } of requests) {
			if (!req || req.wait || req.teamPreview) { entry[side.id] = 'pass, pass'; continue; }
			let legal = legalChoices(battle, side) || [];
			const notPass = legal.filter(c => c !== 'pass, pass');
			if (notPass.length) legal = notPass;
			if (!legal.length) return out;
			const gimmick = legal.filter(c => / (dynamax|terastallize|zmove)/.test(c));
			const pool = gimmick.length && prng() % 2 ? gimmick : legal;
			const choice = pool[prng() % pool.length];
			if (!battle.choose(side.id, choice)) return out;
			entry[side.id] = choice;
		}
		out.push(entry);
	}
	return out;
}


function openingSteps(seed, team1, team2, erng) {
	const battle = new Battle({ formatid: FORMAT, seed, p1: { name: 'p1', team: team1 }, p2: { name: 'p2', team: team2 } });
	battle.choose('p1', 'team 1234');
	battle.choose('p2', 'team 1234');
	const sides = [battle.p1, battle.p2];
	if (!sides.some(s => s.activeRequest && s.activeRequest.forceSwitch)) return null;
	const steps = [];

	for (let guard = 0; guard < 8 && !battle.ended; guard++) {
		const moveRequest = !sides.some(s => s.activeRequest && s.activeRequest.forceSwitch);
		const step = {};
		for (const side of sides) {
			let legal = legalChoices(battle, side) || [];
			const notPass = legal.filter(c => c !== 'pass, pass');
			if (notPass.length) legal = notPass;
			step[side.id] = legal.length ? legal[erng() % legal.length] : 'pass, pass';
		}
		for (const side of sides) if (step[side.id] !== 'pass, pass') battle.choose(side.id, step[side.id]);
		steps.push(step);
		if (moveRequest) return steps;
	}
	return steps;
}


function startedLeads(seed, team1, team2) {
	const battle = new Battle({ formatid: FORMAT, seed, p1: { name: 'p1', team: team1 }, p2: { name: 'p2', team: team2 } });
	battle.choose('p1', 'team 1234');
	battle.choose('p2', 'team 1234');
	return battle.sides.map(side => side.active.map(p => ({
		moves: p.moveSlots.map(m => m.id), types: p.getTypes(), canTera: !!p.canTerastallize, commanding: !!p.volatiles['commanding'],
	})));
}

function parseArgs(argv) {
	const args = { count: 100, seed: 1, outDir: null };
	for (let i = 0; i < argv.length; i++) {
		if (argv[i] === '--count') args.count = parseInt(argv[++i], 10);
		else if (argv[i] === '--seed') args.seed = parseInt(argv[++i], 10);
		else if (argv[i] === '--out-dir') args.outDir = argv[++i];
		else if (argv[i] === '--branching') args.branching = true;
		else if (argv[i] === '--focus') args.focus = argv[++i].split(',');

		else if (argv[i] === '--extra-moves') args.extraMoves = argv[++i].split(',');

		else if (argv[i] === '--extra-abilities') args.extraAbilities = argv[++i].split(',');
		else if (argv[i] === '--focus-abilities') args.focusAbilities = true;

		else if (argv[i] === '--extra-items') args.extraItems = argv[++i].split(',');
		else if (argv[i] === '--focus-items') args.focusItems = true;

		else if (argv[i] === '--extra-species') args.extraSpecies = argv[++i].split(',');

		else if (argv[i] === '--focus-species') args.focusSpecies = true;
		else if (argv[i] === '--format') args.format = argv[++i];

		else if (argv[i] === '--z') args.z = true;

		else if (argv[i] === '--gmax') args.gmax = true;

		else if (argv[i] === '--turns') args.turns = parseInt(argv[++i], 10);
		else throw new Error(`Unknown arg: ${argv[i]}`);
	}
	if (!args.outDir) throw new Error('--out-dir is required');
	return args;
}

function main() {
	const args = parseArgs(process.argv.slice(2));
	const rng = splitmix32(args.seed);
	if (args.branching) { movePool = [...MOVES, ...BRANCHING_MOVES]; abilityPool = [...ABILITIES, ...BRANCHING_ABILITIES]; }
	itemPool = ITEMS;
	if (args.format && args.format !== FORMAT) {
		if (!LEGACY_FORMATS[args.format]) throw new Error(`--format: ${args.format} (one of ${Object.keys(LEGACY_FORMATS).join(', ')})`);
		if (!args.branching) throw new Error(`--format ${args.format} is replay-only: pass --branching`);
		useLegacyPools(args.format);
	}



	const future = (kind, ids) => {
		const bad = (ids || []).filter(id => MOVE_DEX[kind].get(id).isNonstandard === 'Future');
		if (bad.length) throw new Error(`--extra-${kind}: not in ${FORMAT}'s gen yet: ${bad.join(', ')}`);
	};
	future('moves', args.extraMoves);
	future('species', args.extraSpecies);
	future('abilities', args.extraAbilities);
	if (args.extraMoves) {
		const unknown = args.extraMoves.filter(m => !Dex.moves.get(m).exists);
		if (unknown.length) throw new Error(`--extra-moves: unknown moves ${unknown.join(', ')}`);
		movePool = [...movePool, ...args.extraMoves.filter(m => !movePool.includes(m))];
		for (const id of args.extraMoves) if (CHOOSABLE_TARGETS.has(MOVE_DEX.moves.get(id).target)) NEEDS_TARGET.add(id);
	}
	if (args.extraSpecies) {
		const unknown = args.extraSpecies.filter(sp => !Dex.species.get(sp).exists);
		if (unknown.length) throw new Error(`--extra-species: unknown species ${unknown.join(', ')}`);

		speciesPool = args.focusSpecies ? args.extraSpecies : [...speciesPool, ...args.extraSpecies, ...args.extraSpecies];
	}
	if (args.extraItems) {
		const unknown = args.extraItems.filter(it => !Dex.items.get(it).exists);
		if (unknown.length) throw new Error(`--extra-items: unknown items ${unknown.join(', ')}`);
		itemPool = args.focusItems ? ['', ...args.extraItems] : [...itemPool, ...args.extraItems.filter(it => !itemPool.includes(it))];
	}
	if (args.extraAbilities) {
		const unknown = args.extraAbilities.filter(a => !Dex.abilities.get(a).exists);
		if (unknown.length) throw new Error(`--extra-abilities: unknown abilities ${unknown.join(', ')}`);
		abilityPool = args.focusAbilities ? args.extraAbilities : [...abilityPool, ...args.extraAbilities.filter(a => !abilityPool.includes(a))];
	}

	if (args.focus) {
		const missing = args.focus.filter(m => !movePool.includes(m));
		if (missing.length) throw new Error(`--focus moves not in the ${args.branching ? 'branching ' : ''}pool: ${missing.join(', ')}`);
		fullMovePool = movePool;
		movePool = args.focus;
	}
	Z_FOCUS = !!args.z;
	GMAX_FOCUS = !!args.gmax;
	PLAY_TURNS = args.turns || 1;
	fs.mkdirSync(args.outDir, { recursive: true });
	for (let i = 0; i < args.count; i++) {
		const scenario = randomScenario(rng, i, args.seed);
		fs.writeFileSync(path.join(args.outDir, `scenario-${i}.json`), JSON.stringify(scenario, null, '\t'));
	}
	console.log(`wrote ${args.count} scenarios to ${args.outDir}`);
}

main();
