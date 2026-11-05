'use strict';





























const fs = require('fs');
const path = require('path');
const { ordered } = require('./lib/id-registry');

const OUT_DIR = path.join(__dirname, 'out');
const ENGINE_DATA_SRC = path.join(__dirname, '..', '..', 'crates', 'engine-data', 'src');



const MOVE_IDS = [
	'tackle', 'closecombat', 'earthquake', 'icebeam', 'thunderbolt', 'moonblast', 'dracometeor',
	'flareblitz', 'protect', 'swordsdance', 'thunderwave', 'willowisp', 'rockslide', 'icywind',
	'psychic', 'shadowball',

	'raindance', 'sunnyday', 'sandstorm', 'tailwind', 'trickroom',

	'reflect', 'lightscreen', 'auroraveil',

	'stealthrock', 'spikes', 'toxicspikes', 'stickyweb',

	'electricterrain', 'grassyterrain', 'mistyterrain', 'psychicterrain',






	'hypervoice', 'grassyglide', 'woodhammer', 'highhorsepower', 'kowtowcleave', 'dazzlinggleam',
	'aquajet', 'makeitrain', 'flamethrower', 'flashcannon', 'powergem', 'sludgebomb', 'focusblast',
	'extremespeed', 'liquidation', 'shadowclaw', 'mysticalfire', 'spiritbreak', 'iciclecrash',
	'superpower', 'strugglebug', 'energyball', 'playrough', 'gunkshot', 'shadowsneak', 'drillrun',
	'drumbeating', 'hydropump', 'bulletpunch', 'crunch', 'powerwhip', 'fireblast', 'psychocut',
	'machpunch', 'electroweb', 'waterfall', 'boomburst', 'accelerock', 'thunderpunch', 'bodyslam',
	'pyroball', 'breakingswipe', 'hammerarm', 'discharge', 'luminacrash', 'bugbuzz', 'stoneedge',
	'leafblade', 'bite', 'seedbomb', 'vacuumwave', 'slash', 'zingzap', 'bittermalice',
	'gigatonhammer', 'icehammer', 'xscissor', 'dragonclaw', 'quickattack', 'iceshard',

	'nightslash', 'crosschop',

	'wavecrash', 'headsmash', 'doubleedge',

	'ironhead', 'heatwave', 'icepunch', 'zapcannon', 'rocktomb', 'poisonjab', 'scorchingsands',
	'nuzzle',

	'snarl', 'overdrive', 'headlongrush', 'earthpower',

	'nastyplot', 'calmmind', 'dragondance', 'bulkup', 'quiverdance', 'shellsmash', 'irondefense',
	'charm', 'agility', 'faketears', 'tickle',

	'armorcannon', 'overheat', 'leafstorm', 'clangingscales'
,

	'hypnosis', 'sleeppowder', 'sing',
	'toxic'

,
	'scald'  ,

	'recover', 'slackoff',


	'lightofruin',








	'fakeout',





	'dragonpulse', 'aurasphere',




	'detect',





	'leechlife',











	'direclaw',





	'partingshot',




	'suckerpunch',








	'helpinghand',






	'expandingforce',






	'weatherball',




	'uturn',



	'followme',


	'lastrespects',



	'lowkick',



	'throatchop',


	'wideguard',


	'eruption',

	'flipturn',




	'quickguard',
	'kingsshield',
	'spikyshield',
	'banefulbunker',





	'bravebird', 'darkpulse', 'airslash', 'drainingkiss', 'gigadrain', 'bitterblade', 'drainpunch',
	'hornleech', 'paraboliccharge', 'matchagotcha', 'coaching',

	'muddywater', 'nightdaze',


	'stormthrow', 'flowertrick', 'feint', 'firespin', 'infestation',


	'superfang', 'knockoff',


	'hurricane', 'waterpulse',

	'blizzard',


	'waterspout', 'assurance', 'steelbeam', 'highjumpkick', 'icefang', 'focusenergy', 'dragoncheer', 'clangoroussoul', 'glaiverush',
	'soak', 'psychup', 'psychicnoise', 'alluringvoice', 'meteorassault',


	'triattack', 'barbbarrage', 'ragefist', 'acupressure', 'magicpowder', 'memento', 'finalgambit', 'explosion', 'fissure', 'sheercold',
	'bugbite', 'quash', 'beatup',

	'skillswap', 'stockpile', 'healingwish', 'gravity',

	'round', 'allyswitch', 'roar', 'phantomforce', 'batonpass',

	'endure', 'smackdown', 'entrainment', 'dragontail',

	'substitute',

	'revivalblessing',

	'struggle',


	'electroshot', 'solarbeam', 'hyperbeam',



	'disable',


	'encore',


	'ragepowder',


	'darkestlariat',


	'terrainpulse', 'ancientpower',


	'stompingtantrum', 'perishsong',


	'bodypress', 'coil', 'psychicfangs', 'lifedew', 'roost', 'doubleshock',


	'taunt', 'yawn', 'trick', 'imprison',



	'psyshock', 'sacredsword', 'foulplay', 'grassknot', 'heavyslam', 'acrobatics', 'hex', 'freezedry', 'risingvoltage',
	'flamecharge', 'torchsong', 'fierydance', 'voltswitch',


	'dualwingbeat', 'twinbeam', 'iciclespear', 'tripleaxel', 'scaleshot', 'populationbomb',



	'brickbreak', 'firstimpression', 'steelroller', 'minimize', 'howl', 'bellydrum', 'milkdrink', 'haze', 'powertrip', 'poltergeist', 'temperflare', 'healpulse',


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



	'blastburn', 'frenzyplant', 'gigaimpact', 'hydrocannon', 'rockwrecker', 'bind', 'wrap', 'sandtomb', 'whirlpool', 'snaptrap', 'flail',
	'reversal', 'electroball', 'gyroball', 'heatcrash', 'hardpress', 'storedpower', 'facade', 'venoshock', 'payback', 'skyattack',
	'meteorbeam', 'solarblade',

	'dig', 'dive', 'fly', 'bounce',


	'confuseray', 'sweetkiss', 'teeterdance', 'swagger', 'flatter', 'dynamicpunch', 'axekick', 'supercellslam', 'moonlight',
	'morningsun', 'synthesis', 'nightshade', 'seismictoss', 'endeavor', 'guillotine', 'horndrill', 'thunder', 'growth', 'clearsmog',
	'snowscape',


	'rapidspin', 'mortalspin', 'icespinner', 'stoneaxe', 'ceaselessedge', 'circlethrow', 'whirlwind', 'selfdestruct',
	'mistyexplosion', 'infernalparade', 'lashout', 'burningjealousy', 'gravapple', 'ficklebeam', 'painsplit',


	'guardswap', 'powerswap', 'topsyturvy', 'switcheroo', 'spite', 'tidyup', 'defog', 'healbell', 'strengthsap', 'corrosivegas',
	'worryseed', 'reflecttype', 'afteryou',


	'covet', 'thief', 'fellstinger', 'flyingpress', 'burnup', 'eeriespell', 'sparklingaria', 'snipeshot', 'courtchange', 'charge',
	'watershuriken', 'ragingbull', 'aurawheel',


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
	'transform',

	'dragondarts',


	'absorb', 'acid', 'armthrust', 'astonish', 'attackorder', 'aurorabeam', 'barrage', 'barrier', 'boneclub', 'bonemerang', 'bubble',
	'bubblebeam', 'cometpunch', 'constrict', 'defendorder', 'doubleslap', 'dragonbreath', 'dualchop', 'eggbomb', 'ember',
	'feintattack', 'flamewheel', 'flash', 'forcepalm', 'furyswipes', 'geargrind', 'grasswhistle', 'growl', 'gust', 'headcharge',
	'healorder', 'heartstamp', 'honeclaws', 'hornattack', 'hyperfang', 'karatechop', 'kinesis', 'leaftornado', 'leer', 'lick',
	'lovelykiss', 'lusterpurge', 'magnetbomb', 'meditate', 'megadrain', 'megapunch', 'metalclaw', 'mirrorshot', 'mistball',
	'mudbomb', 'needlearm', 'octazooka', 'ominouswind', 'payday', 'poisongas', 'poisonsting', 'poisontail', 'razorleaf',
	'rocksmash', 'rockthrow', 'rollingkick', 'sandattack', 'scratch', 'sharpen', 'shockwave', 'silverwind', 'skyuppercut',
	'sludge', 'smog', 'smokescreen', 'softboiled', 'spark', 'spikecannon', 'spore', 'steamroller', 'stomp', 'strength',
	'submission', 'tailglow', 'tailwhip', 'thundershock', 'twineedle', 'twister', 'visegrip', 'vitalthrow', 'wingattack',
	'withdraw', 'workup', 'cut',

	'chatter', 'confide', 'disarmingvoice', 'fairywind', 'playnice', 'poweruppunch', 'sacredfire', 'holdhands', 'holdback',

	'craftyshield', 'matblock',

	'pursuit',

	'darkvoid',

	'celebrate', 'happyhour', 'venomdrench', 'flowershield', 'rototiller', 'powder', 'iondeluge',

	'skydrop',


	'aeroblast', 'blueflare', 'boltstrike', 'dragonascent', 'glaciate', 'landswrath', 'oblivionwing', 'originpulse',
	'precipiceblades', 'roaroftime', 'spacialrend', 'psystrike',





	'geomancy', 'shadowforce', 'freezeshock', 'iceburn', 'fusionbolt', 'fusionflare', 'doomdesire', 'heartswap',
	'hyperspacefury', 'hyperspacehole', 'judgment', 'psychoboost', 'relicsong', 'searingshot', 'secretsword', 'seedflare',
	'steameruption', 'technoblast',


	'dragonhammer', 'fleurcannon', 'leafage', 'prismaticlaser', 'shadowbone', 'vcreate',

	'naturesmadness',

	'moongeistbeam', 'sunsteelstrike', 'photongeyser',

	'catastropika', 'letssnuggleforever', 'maliciousmoonsault', 'menacingmoonrazemaelstrom', 'oceanicoperetta', 'pulverizingpancake',
	'searingsunrazesmash', 'sinisterarrowraid', 'soulstealing7starstrike', '10000000voltthunderbolt', 'stokedsparksurfer', 'extremeevoboost',


	'clangoroussoulblaze', 'guardianofalola',

	'splinteredstormshards',

	'lightthatburnsthesky',


	'mindblown', 'shoreup', 'thousandwaves',

	'thousandarrows',

	'spotlight',

	'anchorshot', 'floralhealing',

	'coreenforcer',

	'attract',



	'confusion', 'psybeam', 'signalbeam', 'dizzypunch', 'rockclimb', 'supersonic', 'clamp', 'magmastorm', 'dragonrage', 'sonicboom',
	'crushgrip', 'wringout', 'punishment', 'smellingsalts', 'wakeupslap', 'revenge', 'brine', 'chipaway', 'falseswipe', 'jumpkick',
	'captivate', 'dreameater', 'synchronoise', 'foresight', 'odorsleuth', 'miracleeye',


	'triplekick', 'splash', 'mindreader', 'healblock', 'trumpcard', 'psychoshift', 'refresh', 'aromatherapy', 'flameburst',
	'incinerate', 'spiderweb', 'camouflage', 'defensecurl',


	'return', 'frustration', 'mist', 'luckychant', 'echoedvoice', 'retaliate',


	'razorwind', 'skullbash', 'mudsport', 'watersport', 'lunardance', 'embargo', 'nightmare', 'magnitude', 'secretpower',
	'autotomize', 'furycutter', 'teleport',

	'rage', 'grudge', 'telekinesis', 'bestow', 'conversion',

	'fling', 'naturalgift',

	'magiccoat',

	'uproar',

	'psywave', 'present',

	'rollout', 'iceball',

	'simplebeam',

	'hail',

	'snatch',

	'copycat',

	'instruct',

	'futuresight',

	'sleeptalk',

	'sketch',
	'mirrormove', 'naturepower',

	'mefirst', 'metronome', 'assist',

	'conversion2',

	'mimic',

	'bide',

	'firepledge', 'grasspledge', 'waterpledge',

	'hiddenpower',

	'terablast',




	'surgingstrikes', 'wickedblow', 'glaciallance', 'astralbarrage', 'bleakwindstorm', 'sandsearstorm', 'wildboltstorm', 'fierywrath',
	'tachyoncutter', 'bloodmoon', 'thunderclap', 'ruination', 'electrodrift', 'collisioncourse', 'psyblade', 'hydrosteam', 'lunarblessing',
	'junglehealing',

	'burningbulwark',

	'behemothblade', 'behemothbash',

	'ivycudgel',

	'terastarstorm',

	'orderup',




	'mysticalpower', 'victorydance', 'esperwing', 'spinout', 'tripledive', 'mightycleave', 'malignantchain', 'revelationdance',
	'multiattack', 'chloroblast', 'takeheart', 'purify', 'laserfocus', 'tarshot', 'gearup',


	'strangesteam', 'dragonenergy', 'dynamaxcannon',


	'thunderouskick', 'hyperdrill', 'springtidestorm',

	'branchpoke', 'falsesurrender', 'freezingglare', 'thundercage',


	'silktrap', 'filletaway', 'doodle',

	'shelltrap',


	'fishiousrend', 'boltbeak', 'obstruct', 'eternabeam',


	'plasmafists', 'spectralthief', 'doubleironbash', 'diamondstorm',

	'genesissupernova',
];






const FIELD_EFFECTS = {
	wideguard: 'WideGuard',
	quickguard: 'QuickGuard',
	craftyshield: 'CraftyShield',
	matblock: 'MatBlock',
	iondeluge: 'IonDeluge',
	raindance: 'Rain',
	sunnyday: 'Sun',
	sandstorm: 'Sand',
	tailwind: 'Tailwind',
	trickroom: 'TrickRoom',
	reflect: 'Reflect',
	lightscreen: 'LightScreen',
	auroraveil: 'AuroraVeil',
	stealthrock: 'StealthRock',
	spikes: 'Spikes',
	toxicspikes: 'ToxicSpikes',
	stickyweb: 'StickyWeb',
	electricterrain: 'ElectricTerrain',
	grassyterrain: 'GrassyTerrain',
	mistyterrain: 'MistyTerrain',
	psychicterrain: 'PsychicTerrain',
	gravity: 'Gravity',
	fairylock: 'FairyLock',
	mudsport: 'MudSport',
	watersport: 'WaterSport',
	magicroom: 'MagicRoom',
	wonderroom: 'WonderRoom',
	safeguard: 'Safeguard',
	mist: 'Mist',
	luckychant: 'LuckyChant',
	snowscape: 'Snow',
	hail: 'Hail',
	chillyreception: 'Snow',
};

const STAT_INDEX = { atk: 0, def: 1, spa: 2, spd: 3, spe: 4, accuracy: 5, evasion: 6 };
const STATUS_VARIANT = { brn: 'Burn', frz: 'Freeze', par: 'Paralysis', psn: 'Poison', tox: 'Toxic', slp: 'Sleep' };

const TARGET_VARIANT = {
	normal: 'Normal',




	any: 'Normal',


	adjacentFoe: 'Normal',
	self: 'Self_',
	allAdjacent: 'AllAdjacent',
	allAdjacentFoes: 'AllAdjacentFoes',
	all: 'All',
	allySide: 'AllySide',
	foeSide: 'FoeSide',

	allies: 'Self_',

	adjacentAllyOrSelf: 'Self_',

	scripted: 'Normal',

	randomNormal: 'Normal',

	allyTeam: 'Self_',
	adjacentAlly: 'AdjacentAlly',
};



const CHOICE_TARGET_VARIANT = {
	normal: 'Adjacent',
	any: 'Adjacent',
	adjacentFoe: 'AdjacentFoe',
	adjacentAlly: 'AdjacentAlly',
	adjacentAllyOrSelf: 'AllyOrSelf',
};

function typeVariant(name) {
	return name === 'Stellar' ? 'Stellar' : name;
}

function boostsArray(boosts) {
	const arr = [0, 0, 0, 0, 0, 0, 0];
	if (boosts) {
		for (const [stat, delta] of Object.entries(boosts)) {
			if (!(stat in STAT_INDEX)) throw new Error(`unhandled boosted stat "${stat}"`);
			arr[STAT_INDEX[stat]] = delta;
		}
	}
	return arr;
}










const BOOSTS_OVERRIDE = {
	partingshot: { atk: -1, spa: -1 },
};










const RANDOM_STATUS_SECONDARY = {
	direclaw: ['psn', 'par', 'slp'],
	triattack: ['brn', 'par', 'frz'],
};




const SECONDARY_HANDLED_BY_MOVE_ID = new Set(['throatchop', 'hurricane', 'waterpulse', 'alluringvoice', 'psychicnoise', 'dynamicpunch', 'axekick', 'burningjealousy', 'stoneaxe', 'ceaselessedge', 'eeriespell', 'sparklingaria', 'saltcure', 'syrupbomb', 'spiritshackle', 'anchorshot', 'confusion', 'psybeam', 'signalbeam', 'dizzypunch', 'rockclimb', 'chatter', 'clangoroussoulblaze', 'strangesteam', 'genesissupernova']);

function secondaryEffect(secondary, moveId) {
	if (RANDOM_STATUS_SECONDARY[moveId]) {
		const variants = RANDOM_STATUS_SECONDARY[moveId].map(s => {
			const variant = STATUS_VARIANT[s];
			if (!variant) throw new Error(`unhandled random-status status "${s}" for ${moveId}`);
			return `Status::${variant}`;
		});
		return `SecondaryEffect::RandomStatus([${variants.join(', ')}])`;
	}
	if (secondary.status) {
		const variant = STATUS_VARIANT[secondary.status];
		if (!variant) throw new Error(`unhandled secondary status "${secondary.status}"`);
		return `SecondaryEffect::Status(Status::${variant})`;
	}
	if (secondary.boosts) {
		return `SecondaryEffect::Boosts([${boostsArray(secondary.boosts).join(', ')}])`;
	}
	if (secondary.self && secondary.self.boosts) {
		return `SecondaryEffect::SelfBoosts([${boostsArray(secondary.self.boosts).join(', ')}])`;
	}
	if (secondary.volatileStatus === 'flinch') {
		return 'SecondaryEffect::Flinch';
	}
	throw new Error(`unhandled secondary shape: ${JSON.stringify(secondary)}`);
}

function emitMove(m) {
	const target = TARGET_VARIANT[m.target];
	if (!target) throw new Error(`unhandled move target "${m.target}" for ${m.id}`);

	const accuracy = m.accuracy === true ? 'Accuracy::AlwaysHits' : `Accuracy::Percent(${m.accuracy})`;






	let selfBoosts = 'None';
	const rawSelfBoosts = m.self?.boosts || m.selfBoost?.boosts;


	const selfChance = m.self?.chance !== undefined;
	if (rawSelfBoosts && !selfChance) selfBoosts = `Some([${boostsArray(rawSelfBoosts).join(', ')}])`;

	let boosts = 'None';
	const rawBoosts = BOOSTS_OVERRIDE[m.id] || m.boosts;
	if (rawBoosts) boosts = `Some([${boostsArray(rawBoosts).join(', ')}])`;

	let status = 'None';
	if (m.status) {
		const variant = STATUS_VARIANT[m.status];
		if (!variant) throw new Error(`unhandled status "${m.status}" for ${m.id}`);
		status = `Some(Status::${variant})`;
	}



	let secondary = 'None';
	let secondary2 = 'None';
	const secs = m.secondaries || (m.secondary ? [m.secondary] : []);
	if (secs.length > 2) throw new Error(`${m.id}: ${secs.length} secondaries, MoveData holds two`);
	if (secs.length && !SECONDARY_HANDLED_BY_MOVE_ID.has(m.id) && !selfChance) {
		const emit = sec => `Some(Secondary { chance: ${sec.chance}, effect: ${secondaryEffect(sec, m.id)} })`;
		secondary = emit(secs[0]);
		if (secs[1]) secondary2 = emit(secs[1]);
	}

	let recoil = 'None';
	if (m.recoil) recoil = `Some((${m.recoil[0]}, ${m.recoil[1]}))`;



	let drain = 'None';
	if (m.drain) drain = `Some((${m.drain[0]}, ${m.drain[1]}))`;




	let heal = 'None';
	if (m.heal) heal = `Some((${m.heal[0]}, ${m.heal[1]}))`;

	const blockedByProtect = !!(m.flags && m.flags.protect);
	const thawsUser = !!(m.flags && m.flags.defrost);
	const sleepUsable = !!m.sleepUsable;

	const CALL_FLAG_BITS = ['nosleeptalk', 'failcopycat', 'noassist', 'failinstruct', 'failmimic', 'failmefirst', 'metronome', 'nosketch', 'snatch', 'failencore', 'mirror'];
	const callFlags = CALL_FLAG_BITS.reduce((acc, f, i) => acc | ((m.flags && m.flags[f]) ? 1 << i : 0), 0);
	const contact = !!(m.flags && m.flags.contact);


	const sound = !!(m.flags && m.flags.sound);
	const reflectable = !!(m.flags && m.flags.reflectable);
	const willCrit = !!m.willCrit;
	const breaksProtect = !!m.breaksProtect;
  const charge = !!(m.flags && m.flags.charge);
  const recharge = !!(m.flags && m.flags.recharge);
  const punch = !!(m.flags && m.flags.punch);
  const minimize = !!(m.flags && m.flags.minimize);
	const slicing = !!(m.flags && m.flags.slicing);
	const multihitRange = Array.isArray(m.multihit) ? m.multihit : (m.multihit ? [m.multihit, m.multihit] : [0, 0]);
	const multiaccuracy = !!m.multiaccuracy;
	const pulse = !!(m.flags && m.flags.pulse);
	const bullet = !!(m.flags && m.flags.bullet);
	const healFlag = !!(m.flags && m.flags.heal);
	const gravityFlag = !!(m.flags && m.flags.gravity);
	const powderFlag = !!(m.flags && m.flags.powder);
	const bypassSub = !!(m.flags && m.flags.bypasssub);
	const biteFlag = !!(m.flags && m.flags.bite);
	const fieldEffect = FIELD_EFFECTS[m.id] ? `Some(FieldEffect::${FIELD_EFFECTS[m.id]})` : 'None';







	if (typeof m.selfSwitch === 'string' && !['copyvolatile', 'shedtail'].includes(m.selfSwitch)) throw new Error(`${m.id}: selfSwitch "${m.selfSwitch}" isn't a shape this file supports`);
	const selfSwitch = !!m.selfSwitch;

	return `    MoveData {
        move_type: Type::${typeVariant(m.type)},
        category: Category::${m.category},
        base_power: ${m.basePower},
        accuracy: ${accuracy},
        pp: ${m.pp},
        priority: ${m.priority},
        target: MoveTarget::${target},
        choice_target: ChoiceTarget::${m.id === 'struggle' ? 'None' : (CHOICE_TARGET_VARIANT[m.target] || 'None')},
        crit_ratio: ${m.critRatio},
        blocked_by_protect: ${blockedByProtect},
        thaws_user: ${thawsUser},
        sleep_usable: ${sleepUsable},
        call_flags: ${callFlags},
        contact: ${contact},
        sound: ${sound},
        reflectable: ${reflectable},
        will_crit: ${willCrit},
        breaks_protect: ${breaksProtect},
        charge: ${charge},
        recharge: ${recharge},
        punch: ${punch},
        minimize: ${minimize},
        slicing: ${slicing},
        multihit_min: ${multihitRange[0]},
        multihit_max: ${multihitRange[1]},
        multiaccuracy: ${multiaccuracy},
        pulse: ${pulse},
        bullet: ${bullet},
        heal_flag: ${healFlag},
        gravity_flag: ${gravityFlag},
        powder: ${powderFlag},
        bypass_sub: ${bypassSub},
        bite: ${biteFlag},
        self_boosts: ${selfBoosts},
        boosts: ${boosts},
        status: ${status},
        secondary: ${secondary},
        secondary2: ${secondary2},
        recoil: ${recoil},
        drain: ${drain},
        heal: ${heal},
        field_effect: ${fieldEffect},
        self_switch: ${selfSwitch},
    }, // ${m.id}`;
}


const STRUGGLE_SHAPE = { secondary: null, secondaries: null, boosts: null, status: null, volatileStatus: null, drain: null, recoil: null,
	multihit: null, multiaccuracy: null, self: null, selfBoost: null, heal: null, ignoreImmunity: false, selfSwitch: null, willCrit: null,
	breaksProtect: null };

function main() {
	const moves = require(path.join(OUT_DIR, 'moves.json'));


	moves.push({ ...STRUGGLE_SHAPE, id: 'struggle', name: 'Struggle', type: 'Normal', category: 'Physical', basePower: 50, accuracy: true, pp: 1, priority: 0, target: 'normal', critRatio: 1, flags: { contact: 1, protect: 1,
		failencore: 1, failmefirst: 1, nosleeptalk: 1, noassist: 1, failcopycat: 1, failmimic: 1, failinstruct: 1, nosketch: 1 } });

	const catalogFile = path.join(OUT_DIR, 'catalog-moves.json');
	const catalog = fs.existsSync(catalogFile) ? require(catalogFile) : [];
	const byId = new Map([...moves, ...catalog].map(m => [m.id, m]));

	const missing = MOVE_IDS.filter(id => !byId.has(id));
	if (missing.length) throw new Error(`moves not found in the legal pool or the catalog: ${missing.join(', ')}`);



	const ported = new Set(MOVE_IDS);
	const header = m => ({ ...STRUGGLE_SHAPE, id: m.id, name: m.name, type: m.type, category: m.category, basePower: m.basePower,
		accuracy: m.accuracy, pp: m.pp, priority: m.priority, target: m.target, critRatio: m.critRatio, flags: m.flags });
	const unported = [...moves, ...catalog].filter(m => !ported.has(m.id)).map(header);
	for (const m of unported) byId.set(m.id, m);

	const order = ordered('moves', [...MOVE_IDS.map(id => byId.get(id)), ...unported]).map(m => m.id);
	const rows = order.map(id => emitMove(byId.get(id)));


	const gen5ById = new Map(require(path.join(OUT_DIR, 'gen5-moves.json')).map(m => [m.id, m]));
	const gen5Rows = order.map(id => {
		const g = gen5ById.get(id);
		return emitMove(!g ? byId.get(id) : ported.has(id) ? g : header(g));
	});

	const gen6ById = new Map(require(path.join(OUT_DIR, 'gen6-moves.json')).map(m => [m.id, m]));
	const gen6Rows = order.map(id => {
		const g = gen6ById.get(id);
		return emitMove(!g ? byId.get(id) : ported.has(id) ? g : header(g));
	});

	const gen7ById = new Map(require(path.join(OUT_DIR, 'gen7-moves.json')).map(m => [m.id, m]));
	const gen7Rows = order.map(id => {
		const g = gen7ById.get(id);
		return emitMove(!g ? byId.get(id) : ported.has(id) ? g : header(g));
	});

	const svRows = file => {
		const svById = new Map(require(path.join(OUT_DIR, file)).map(m => [m.id, m]));
		return order.map(id => {
			const g = svById.get(id);
			return emitMove(!g ? byId.get(id) : ported.has(id) ? g : header(g));
		});
	};
	const gen9Rows = svRows('gen9-moves.json');

	const gen8Rows = svRows('gen8-moves.json');
	const gen9PredlcRows = svRows('gen9predlc-moves.json');

	const idConsts = order.map((id, i) => `    pub const ${/^[0-9]/.test(id) ? '_' : ''}${id.toUpperCase()}: MoveId = ${i + 1};`);
	const names = order.map(id => `    "${byId.get(id).name}",`);
	const portedRows = order.map(id => `    ${ported.has(id)}, // ${id}`);

	const metronomePools = require(path.join(OUT_DIR, 'metronome-pools.json'));
	const poolIds = key => metronomePools[key].map(id => {
		const i = order.indexOf(id);
		if (i < 0) throw new Error(`metronome pool ${key}: ${id} has no MoveId`);
		return i + 1;
	});
	const metronomeRow = key => { const ids = poolIds(key); return `[MoveId; ${ids.length}] = [${ids.join(', ')}]`; };

	const rust = `//! Generated by tools/gen-data/codegen-moves.js from tools/gen-data/out/moves.json.
//! DO NOT EDIT BY HAND. Hand-picked move subset (see that script's header comment for why);
//! regenerate after any Showdown pin bump (SHOWDOWN_PIN.md) or list change.

use crate::type_chart::Type;

pub type MoveId = u16;

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Category {
    Physical,
    Special,
    Status,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum MoveTarget {
    /// A single chosen target (the common case).
    Normal,
    /// The user itself - no target selection needed.
    Self_,
    /// Both foes *and* the user's partner (e.g. Earthquake in doubles) - everyone adjacent
    /// except the user.
    AllAdjacent,
    /// Both foes, not the user's partner (e.g. Rock Slide, Icy Wind in doubles).
    AllAdjacentFoes,
    /// Field-wide, no target selection (weather, Trick Room).
    All,
    /// The user's own side, no target selection (Tailwind).
    AllySide,
    /// The *opposing* side, no target selection (entry hazards).
    FoeSide,
    /// The user's own partner specifically (Helping Hand) - in this 2-active-per-side doubles
    /// format, always exactly the other slot on the user's own side, no \`chosen\`/fallback
    /// ambiguity the way \`Normal\`'s 2 foe slots have.
    AdjacentAlly,
}

/// Which target a player names when choosing the move (Showdown's choosable target types, \`validTargetLoc\`). Distinct from
/// [\`MoveTarget\`], which is how the move resolves: \`any\` resolves like \`normal\`, and \`adjacentAllyOrSelf\` defaults to the user.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum ChoiceTarget {
    /// No target is named (self, spread, field and side moves, and Struggle).
    None,
    /// Either foe or the partner (\`normal\`, \`any\`).
    Adjacent,
    /// Either foe only (\`adjacentFoe\`).
    AdjacentFoe,
    /// The partner only (\`adjacentAlly\`).
    AdjacentAlly,
    /// The partner or the user itself (\`adjacentAllyOrSelf\`: Acupressure, Milk Drink).
    AllyOrSelf,
}

/// A move's field-wide or side-wide effect (weather, Tailwind, Trick Room). Mirrors
/// \`engine_core::field::Weather\`'s Rain/Sun/Sand/Snow shape for the weather variants - same
/// "duplicated, not imported" reasoning as \`Status\` above. Applied directly in \`execute_action\`
/// (turn.rs), bypassing the generic target-resolution/hit pipeline entirely (none of these moves
/// have a \`protect\` flag - they can't be Protected against, same as real Showdown).
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum FieldEffect {
    /// Wide Guard (\`sideCondition\`, data/moves.ts): chains the user's own stall streak and sets
    /// its side's flag, which blocks spread moves into that side for the rest of the turn.
    WideGuard,
    /// Quick Guard (\`sideCondition\`, data/moves.ts): Wide Guard's shape, but its side flag blocks
    /// moves with positive priority instead of spread moves.
    QuickGuard,
    /// Crafty Shield (\`sideCondition\`, duration 1): the side's flag blocks Status moves for the rest of the turn.
    CraftyShield,
    /// Mat Block (\`sideCondition\`, duration 1; first turn out only): the side's flag blocks damaging moves that Protect blocks.
    MatBlock,
    /// Ion Deluge (\`pseudoWeather\`, duration 1): Normal-type moves are Electric for the rest of the turn.
    IonDeluge,
    Rain,
    Sun,
    Sand,
    Snow,
    Hail,
    Tailwind,
    TrickRoom,
    Reflect,
    LightScreen,
    /// Requires Hail/Snow active to succeed (\`onTry\`, data/moves.ts) - fails (no effect, still
    /// consumes the turn) otherwise. Covers both categories; doesn't stack with Reflect/Light
    /// Screen for whichever category those already cover (data/moves.ts's auroraveil handler).
    AuroraVeil,
    /// Sets on the *foe's* side (unlike every variant above, which is ally/field) - applied on
    /// that side's switch-ins, not immediately. Damage scales with Rock-type effectiveness
    /// against the switching-in mon (data/moves.ts's stealthrock handler) - no grounded check,
    /// unlike the other 3 hazards below.
    StealthRock,
    /// 1-3 layers (re-using this move adds a layer, up to the cap, rather than refreshing a
    /// duration - unlike every timed effect above). Damage scales with layer count; grounded
    /// mons only.
    Spikes,
    /// 1-2 layers. Poisons (1 layer) or badly poisons (2 layers) a grounded, non-Steel mon on
    /// switch-in; a grounded *Poison*-type mon absorbs and removes the hazard entirely instead.
    ToxicSpikes,
    /// -1 Speed on switch-in for a grounded mon. No layers, no damage.
    StickyWeb,
    /// Field-wide (target: \`all\`, like weather), 5 turns (no Terrain Extender - items aren't
    /// modeled). Boosts grounded attackers' Electric-type moves (5325/4096, applied to the
    /// move's *base power* before the damage formula runs - a different, earlier hook than
    /// weather's damage modifier, data/moves.ts's \`onBasePower\` vs \`onWeatherModifyDamage\`) and
    /// blocks grounded targets from falling asleep.
    ElectricTerrain,
    /// Boosts grounded attackers' Grass-type moves (5325/4096, same early \`onBasePower\` hook as
    /// Electric Terrain) and halves Earthquake's power against a grounded defender (Bulldoze/
    /// Magnitude too in real Showdown - not in this table yet). Heals grounded mons 1/16 max HP
    /// at end of turn (a *heal*, not the weather/status residual *damage* this engine already
    /// has - a new code path, not reusing \`weather_residual_damage\`).
    GrassyTerrain,
    /// Halves Dragon-type move power against a grounded defender (same early \`onBasePower\` hook)
    /// and blocks grounded targets from getting *any* major status (broader than Electric
    /// Terrain's Sleep-only block).
    MistyTerrain,
    /// Boosts grounded attackers' Psychic-type moves (5325/4096). **Known gap:** doesn't block
    /// priority moves against grounded targets (data/moves.ts's \`onTryHit\`) - unreachable by the
    /// current move pool (every move here is priority 0 except Protect, which targets the user
    /// itself and so is exempt from that check anyway) - revisit if a priority move that hits a
    /// foe is ever added.
    PsychicTerrain,
    /// Gravity (\`pseudoWeather\`): 5 turns; every active mon is grounded, accuracy is x5/3, and moves flagged \`gravity\` cannot be used.
    Gravity,
    /// Fairy Lock (\`pseudoWeather\`, 2 turns): nobody can switch out during the next turn.
    FairyLock,
    /// Magic Room (\`pseudoWeather\`, 5 turns; using it again ends it): every held item is ignored.
    MagicRoom,
    /// Wonder Room (\`pseudoWeather\`, 5 turns; using it again ends it): every mon's raw Defense and Sp. Def trade places.
    WonderRoom,
    /// Safeguard (\`sideCondition\`, 5 turns): the user's side is protected from statuses, confusion and Yawn from anyone else.
    Safeguard,
    /// Mist (\`sideCondition\`, 5 turns): another mon's stat drops on the user's side are stopped.
    Mist,
    /// Lucky Chant (\`sideCondition\`, 5 turns): no critical hits on the user's side.
    LuckyChant,
    /// Mud Sport / Water Sport (\`pseudoWeather\`, 5 turns): Electric / Fire moves have 1352/4096 power.
    MudSport,
    WaterSport,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Accuracy {
    /// Never misses (Showdown's \`accuracy: true\`) - still subject to evasion/on-hit checks
    /// once those exist, just no base accuracy roll.
    AlwaysHits,
    Percent(u8),
}

/// A move's secondary chance effect (design.md §7: "simple secondary effect, simple stat/status
/// changes"). \`Status\` from this hand-picked list reuses \`engine_core::status::Status\`, so this
/// type lives in... wait, no: \`engine-data\` doesn't depend on \`engine-core\` (dependency points
/// the other way). See \`Status\` below - it's redefined here as the same shape, not imported.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SecondaryEffect {
    Status(Status),
    /// \`[atk, def, spa, spd, spe]\` deltas, applied to the move's target.
    Boosts([i8; 7]),
    Flinch,
    /// Deltas applied to the move's *user* (Ancient Power's \`secondary.self.boosts\`), under the same chance roll.
    SelfBoosts([i8; 7]),
    /// Uniformly-random choice among exactly 3 statuses (Dire Claw's own real \`onHit\`: \`this.
    /// sample(['psn', 'par', 'slp'])\`) - a fixed-size array rather than a \`Vec\` since every move
    /// needing this shape so far samples from exactly 3 options; widen if a future move needs a
    /// different count.
    RandomStatus([Status; 3]),
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Secondary {
    pub chance: u8,
    pub effect: SecondaryEffect,
}

/// Mirrors \`engine_core::status::Status\`'s discriminants exactly (tests in both crates check
/// this) - duplicated rather than imported because \`engine-core\` depends on \`engine-data\`, not
/// the other way around, and this enum needs to live in the generated move data.
#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Status {
    Burn = 1,
    Freeze = 2,
    Paralysis = 3,
    Poison = 4,
    Toxic = 5,
    Sleep = 6,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct MoveData {
    pub move_type: Type,
    pub category: Category,
    pub base_power: u16,
    pub accuracy: Accuracy,
    pub pp: u8,
    pub priority: i8,
    pub target: MoveTarget,
    pub choice_target: ChoiceTarget,
    /// \`move.critRatio\` (Showdown fills this in to 1 for every move that doesn't specify one
    /// itself - *not* 0 - so every damaging move in this table has an inherent ~1/24 base crit
    /// chance regardless of ability/item; \`0\` would mean "can never crit", which no move in the
    /// current table actually is). Indexes the gen7+ \`critMult\` table \`[0, 24, 8, 2, 1]\`
    /// (\`BattleActions#getDamage\`) - \`turn.rs\`'s \`roll_crit\`.
    pub crit_ratio: u8,
    pub blocked_by_protect: bool,
    /// \`move.flags.defrost\` - using this move while Frozen thaws the user unconditionally,
    /// bypassing the normal 1/5 thaw roll (e.g. Flare Blitz). Only matters if the user is Frozen.
    pub thaws_user: bool,
    /// \`move.sleepUsable\` (Snore, Sleep Talk): a sleeping user still uses it - the sleep turn ticks and logs \`cant\`, but the move goes on.
    pub sleep_usable: bool,
    /// The move callers' flags (\`move.flags\`): \`CALL_NO_SLEEP_TALK\` (\`nosleeptalk\`), \`CALL_FAIL_COPYCAT\`, \`CALL_NO_ASSIST\`,
    /// \`CALL_FAIL_INSTRUCT\`, \`CALL_FAIL_MIMIC\`, \`CALL_FAIL_ME_FIRST\`, \`CALL_METRONOME\` (Metronome may call it), \`CALL_NO_SKETCH\` and
    /// \`CALL_SNATCH\` (Snatch steals it) and \`CALL_FAIL_ENCORE\` (Encore fails on it as the last move).
    pub call_flags: u16,
    /// \`move.flags.contact\` - needed by contact-punishing abilities/items (Rough Skin, Rocky
    /// Helmet, ...; \`checkMoveMakesContact\` in the real sim also factors in the attacker's own
    /// Long Reach-style immunity, not in this format's ability pool, so this flag alone suffices
    /// here).
    pub contact: bool,
    /// \`move.flags.sound\` - Soundproof's immunity (\`onTryHit\`/\`onAllyTryHitSide\`).
    pub sound: bool,
    /// \`move.flags.reflectable\` - Magic Bounce's gate (\`onTryHit\`, data/abilities.ts): a move with
    /// this bounces off a Magic Bounce holder back at its user.
    pub reflectable: bool,
    /// \`move.willCrit\` - always a critical hit, with no crit roll drawn (sim/battle-actions.ts).
    pub will_crit: bool,
    /// \`move.breaksProtect\` - removes the target's Protect-family volatiles and guard side flags before its own checks (Feint, Phantom Force).
    pub breaks_protect: bool,
    /// \`move.flags.charge\` - a two-turn move: turn one only charges (\`turn::execute_action\`), turn two attacks.
    pub charge: bool,
    /// \`move.flags.recharge\` - the user must skip its next turn after this move connects (Hyper Beam).
    pub recharge: bool,
    /// \`move.flags.punch\` - Iron Fist's 20% base-power boost (\`onBasePower\`).
    pub punch: bool,
    /// \`move.flags.minimize\` - always hits a Minimized target and deals it double damage (the \`minimize\` volatile's
    /// \`onSourceModifyDamage\` / \`onAccuracy\`).
    pub minimize: bool,
    /// \`move.flags.slicing\` - Sharpness's 1.5x base-power boost (\`onBasePower\`).
    pub slicing: bool,
    /// \`move.multihit\`: the min and max hit count (equal for a fixed count, 0, 0 for a single-hit move).
    pub multihit_min: u8,
    pub multihit_max: u8,
    /// \`move.multiaccuracy\`: every hit after the first re-rolls accuracy (Triple Axel, Population Bomb).
    pub multiaccuracy: bool,
    /// \`move.flags.pulse\` - Mega Launcher's 1.5x.
    pub pulse: bool,
    /// \`move.flags.bullet\` - Bulletproof's immunity.
    pub bullet: bool,
    /// \`move.flags.heal\` - blocked by Heal Block (healing moves and drain moves).
    pub heal_flag: bool,
    /// \`move.flags.gravity\` - can't be used while Gravity is up (High Jump Kick, Fly, Bounce, ...).
    pub gravity_flag: bool,
    /// \`move.flags.powder\` - Grass-types and Overcoat are immune.
    pub powder: bool,
    /// \`move.flags.bypasssub\` - ignores Substitute (sound moves, Psych Up, Roar, ...).
    pub bypass_sub: bool,
    /// \`move.flags.bite\` - Strong Jaw's 1.5x.
    pub bite: bool,
    /// \`move.self.boosts\` - applied to the user after a successful hit, unconditionally (not a
    /// chance effect). \`[atk, def, spa, spd, spe]\` deltas.
    pub self_boosts: Option<[i8; 7]>,
    /// \`move.boosts\` - a Status-category move's direct boost (e.g. Swords Dance), applied to
    /// whatever the move's target resolves to.
    pub boosts: Option<[i8; 7]>,
    /// A Status-category move's direct status application (e.g. Thunder Wave).
    pub status: Option<Status>,
    pub secondary: Option<Secondary>,
    /// A second, independently rolled secondary (\`secondaries[1]\`: the fangs' flinch, Triple Arrows' flinch), applied right after
    /// \`secondary\`.
    pub secondary2: Option<Secondary>,
    /// \`(numerator, denominator)\` of the damage just dealt, as recoil after a successful hit
    /// (NOT the user's max HP, despite this field's name reading that way at a glance - verified
    /// directly against \`turn.rs\`'s own application, which scales off \`last_damage_dealt\`).
    pub recoil: Option<(u32, u32)>,
    /// \`move.drain\` - \`(numerator, denominator)\` of the damage just dealt, healed back to the
    /// user (Leech Life). Same shape and damage-dealt basis as \`recoil\` above, opposite sign -
    /// \`sim/battle.ts\`'s own gen>4 drain branch uses plain \`Math.round\`, with no \`.max(1)\` floor
    /// (unlike recoil's clamped minimum of 1).
    pub drain: Option<(u32, u32)>,
    /// \`move.heal\` - \`(numerator, denominator)\` of the user's own max HP, healed after a
    /// successful use (Recover, Slack Off). Same shape as \`recoil\`/\`drain\` above, but scaled off
    /// max HP rather than damage dealt.
    pub heal: Option<(u32, u32)>,
    pub field_effect: Option<FieldEffect>,
    /// \`move.selfSwitch\` - true for every self-switch move ported so far (U-turn-family: a
    /// plain boolean). Real Showdown's own type also allows the string \`'copyvolatile'\` (Baton
    /// Pass) - not a shape this field (or \`turn.rs\`'s own application of it) supports; porting
    /// Baton Pass would need widening this, not just flipping a bool.
    pub self_switch: bool,
}

/// [\`MoveData::call_flags\`] bits.
pub const CALL_NO_SLEEP_TALK: u16 = 1 << 0;
pub const CALL_FAIL_COPYCAT: u16 = 1 << 1;
pub const CALL_NO_ASSIST: u16 = 1 << 2;
pub const CALL_FAIL_INSTRUCT: u16 = 1 << 3;
pub const CALL_FAIL_MIMIC: u16 = 1 << 4;
pub const CALL_FAIL_ME_FIRST: u16 = 1 << 5;
pub const CALL_METRONOME: u16 = 1 << 6;
pub const CALL_NO_SKETCH: u16 = 1 << 7;
pub const CALL_SNATCH: u16 = 1 << 8;
pub const CALL_FAIL_ENCORE: u16 = 1 << 9;
/// \`flags.mirror\`: Mirror Move copies it.
pub const CALL_MIRROR: u16 = 1 << 10;

pub const MOVE_COUNT: usize = ${order.length};

/// Fixed ids for this hand-picked M1 subset (index + 1 into \`MOVES\"; 0 is NONE_ID).
pub mod move_ids {
    use super::MoveId;
${idConsts.join('\n')}
}

pub const MOVES: [MoveData; MOVE_COUNT] = [
${rows.join('\n')}
];

/// Gen 5's move data (the gen5 mod), indexed like [\`MOVES\`]: a Gen 5 battle reads these (\`Rules::moves\`). A move Gen 5 doesn't
/// have keeps its default row.
pub const MOVES_GEN5: [MoveData; MOVE_COUNT] = [
${gen5Rows.join('\n')}
];

/// Gen 6's move data (the gen6 mod: VGC 2014 / 2015 / 2016), indexed like [\`MOVES\`]. A move Gen 6 doesn't have keeps its
/// default row.
pub const MOVES_GEN6: [MoveData; MOVE_COUNT] = [
${gen6Rows.join('\n')}
];

/// Gen 7's move data (the gen7 mod: VGC 2017 / 2018 / 2019), indexed like [\`MOVES\`]. A move Gen 7 doesn't have keeps its
/// default row.
pub const MOVES_GEN7: [MoveData; MOVE_COUNT] = [
${gen7Rows.join('\n')}
];

/// Scarlet / Violet's move data as base Gen 9 has it (the gen9 mod: VGC 2024 Reg G, VGC 2025 Reg I), indexed like [\`MOVES\`]: the
/// champions mod's changes undone (its PP table, powers, secondaries, flags). A Past move keeps its default row.
pub const MOVES_GEN9: [MoveData; MOVE_COUNT] = [
${gen9Rows.join('\n')}
];

/// The same for gen9predlc (VGC 2023 Reg C / D): Grassy Glide 60, a few moves' flags.
pub const MOVES_GEN9_PREDLC: [MoveData; MOVE_COUNT] = [
${gen9PredlcRows.join('\n')}
];

/// Sword / Shield's move data as the gen8 mod has it (VGC 2020 / 2021 / 2022), indexed like [\`MOVES\`]. A Past move keeps its
/// default row.
pub const MOVES_GEN8: [MoveData; MOVE_COUNT] = [
${gen8Rows.join('\n')}
];

pub fn get(id: MoveId) -> &'static MoveData {
    &MOVES[(id - 1) as usize]
}

/// Showdown display names, indexed like [\`MOVES\`] (id - 1).
pub const MOVE_NAMES: [&str; MOVE_COUNT] = [
${names.join('\n')}
];

pub fn name(id: MoveId) -> &'static str {
    MOVE_NAMES[(id - 1) as usize]
}

/// Whether the move's effect is ported, indexed like [\`MOVES\`] (id - 1). A registered move without its effect (the wider
/// catalog's ids) has a data row but must never be battled: \`team::unsupported\` refuses it, the fuzzer
/// skips it, and the Python \`lookup\` reports it as unknown.
pub const MOVE_PORTED: [bool; MOVE_COUNT] = [
${portedRows.join('\n')}
];

pub fn ported(id: MoveId) -> bool {
    MOVE_PORTED[(id - 1) as usize]
}

/// Metronome's pool (\`metronome.onHit\`): the format dex's \`flags.metronome\` moves that are standard or Unobtainable, by \`num\`.
/// The champions dex's (\`[Gen 9 Champions] VGC 2026 Reg M-C\`).
pub const METRONOME_POOL_CHAMPIONS_MC: ${metronomeRow('championsmc')};
/// The gen5 dex's (\`[Gen 5] VGC 2013\`).
pub const METRONOME_POOL_GEN5_VGC13: ${metronomeRow('gen5vgc13')};
/// The gen6 dex's (\`[Gen 6] VGC 2014 / 2015 / 2016\`).
pub const METRONOME_POOL_GEN6_VGC: ${metronomeRow('gen6vgc')};
/// The gen7 dex's (\`[Gen 7] VGC 2017 / 2018 / 2019\`: gen7sm's pool is the same).
pub const METRONOME_POOL_GEN7_VGC: ${metronomeRow('gen7vgc')};
/// The gen9 dex's (\`[Gen 9] VGC 2024 Reg G\`, \`VGC 2025 Reg I\`).
pub const METRONOME_POOL_GEN9_SV: ${metronomeRow('gen9sv')};
/// The gen9predlc dex's (\`[Gen 9] VGC 2023 Reg C / D\`).
pub const METRONOME_POOL_GEN9_SV_PREDLC: ${metronomeRow('gen9svpredlc')};
/// The gen8 dex's (\`[Gen 8] VGC 2020 / 2021 / 2022\`).
pub const METRONOME_POOL_GEN8_VGC: ${metronomeRow('gen8vgc')};
`;

	fs.mkdirSync(ENGINE_DATA_SRC, { recursive: true });
	fs.writeFileSync(path.join(ENGINE_DATA_SRC, 'moves_table.rs'), rust);
	console.log(`wrote ${ENGINE_DATA_SRC}\\moves_table.rs (${order.length} moves)`);

	fs.writeFileSync(path.join(OUT_DIR, 'ported-moves.json'), JSON.stringify([...MOVE_IDS].sort(), null, '\t') + '\n');
}

main();
