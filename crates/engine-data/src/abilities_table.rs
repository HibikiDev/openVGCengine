





pub type AbilityId = u16;

pub const ABILITY_COUNT: usize = 318;


pub mod ability_ids {
    use super::AbilityId;
    pub const ADAPTABILITY: AbilityId = 1;
    pub const AERILATE: AbilityId = 2;
    pub const AFTERMATH: AbilityId = 3;
    pub const ANALYTIC: AbilityId = 4;
    pub const ANGERPOINT: AbilityId = 5;
    pub const ANTICIPATION: AbilityId = 6;
    pub const ARMORTAIL: AbilityId = 7;
    pub const AROMAVEIL: AbilityId = 8;
    pub const AURAGUARD: AbilityId = 9;
    pub const BATTLEARMOR: AbilityId = 10;
    pub const BATTLEBOND: AbilityId = 11;
    pub const BERSERK: AbilityId = 12;
    pub const BIGPECKS: AbilityId = 13;
    pub const BLAZE: AbilityId = 14;
    pub const BULLETPROOF: AbilityId = 15;
    pub const CHEEKPOUCH: AbilityId = 16;
    pub const CHLOROPHYLL: AbilityId = 17;
    pub const CLEARBODY: AbilityId = 18;
    pub const CLOUDNINE: AbilityId = 19;
    pub const COMPETITIVE: AbilityId = 20;
    pub const COMPOUNDEYES: AbilityId = 21;
    pub const CONTRARY: AbilityId = 22;
    pub const CORROSION: AbilityId = 23;
    pub const CUDCHEW: AbilityId = 24;
    pub const CURIOUSMEDICINE: AbilityId = 25;
    pub const CURSEDBODY: AbilityId = 26;
    pub const CUTECHARM: AbilityId = 27;
    pub const DAMP: AbilityId = 28;
    pub const DEFIANT: AbilityId = 29;
    pub const DISGUISE: AbilityId = 30;
    pub const DRAGONIZE: AbilityId = 31;
    pub const DRIZZLE: AbilityId = 32;
    pub const DROUGHT: AbilityId = 33;
    pub const DRYSKIN: AbilityId = 34;
    pub const EARLYBIRD: AbilityId = 35;
    pub const EARTHEATER: AbilityId = 36;
    pub const EELEVATE: AbilityId = 37;
    pub const EFFECTSPORE: AbilityId = 38;
    pub const ELECTRICSURGE: AbilityId = 39;
    pub const ELECTROMORPHOSIS: AbilityId = 40;
    pub const EMBODYASPECTCORNERSTONE: AbilityId = 41;
    pub const EMBODYASPECTHEARTHFLAME: AbilityId = 42;
    pub const EMBODYASPECTTEAL: AbilityId = 43;
    pub const EMBODYASPECTWELLSPRING: AbilityId = 44;
    pub const EMERGENCYEXIT: AbilityId = 45;
    pub const FAIRYAURA: AbilityId = 46;
    pub const FILTER: AbilityId = 47;
    pub const FIREMANE: AbilityId = 48;
    pub const FLAMEBODY: AbilityId = 49;
    pub const FLASHFIRE: AbilityId = 50;
    pub const FLOWERVEIL: AbilityId = 51;
    pub const FLUFFY: AbilityId = 52;
    pub const FORECAST: AbilityId = 53;
    pub const FOREWARN: AbilityId = 54;
    pub const FRIENDGUARD: AbilityId = 55;
    pub const FRISK: AbilityId = 56;
    pub const FURCOAT: AbilityId = 57;
    pub const GALEWINGS: AbilityId = 58;
    pub const GLUTTONY: AbilityId = 59;
    pub const GOODASGOLD: AbilityId = 60;
    pub const GOOEY: AbilityId = 61;
    pub const GRASSPELT: AbilityId = 62;
    pub const GRASSYSURGE: AbilityId = 63;
    pub const GUARDDOG: AbilityId = 64;
    pub const GULPMISSILE: AbilityId = 65;
    pub const GUTS: AbilityId = 66;
    pub const HARVEST: AbilityId = 67;
    pub const HEALER: AbilityId = 68;
    pub const HEATPROOF: AbilityId = 69;
    pub const HEAVYMETAL: AbilityId = 70;
    pub const HOSPITALITY: AbilityId = 71;
    pub const HUGEPOWER: AbilityId = 72;
    pub const HUNGERSWITCH: AbilityId = 73;
    pub const HUSTLE: AbilityId = 74;
    pub const HYDRATION: AbilityId = 75;
    pub const HYPERCUTTER: AbilityId = 76;
    pub const ICEBODY: AbilityId = 77;
    pub const ICEFACE: AbilityId = 78;
    pub const ILLUMINATE: AbilityId = 79;
    pub const ILLUSION: AbilityId = 80;
    pub const IMMUNITY: AbilityId = 81;
    pub const IMPOSTER: AbilityId = 82;
    pub const INFILTRATOR: AbilityId = 83;
    pub const INNARDSOUT: AbilityId = 84;
    pub const INNERFOCUS: AbilityId = 85;
    pub const INSOMNIA: AbilityId = 86;
    pub const INTIMIDATE: AbilityId = 87;
    pub const IRONFIST: AbilityId = 88;
    pub const JUSTIFIED: AbilityId = 89;
    pub const KEENEYE: AbilityId = 90;
    pub const KLUTZ: AbilityId = 91;
    pub const LEAFGUARD: AbilityId = 92;
    pub const LEVITATE: AbilityId = 93;
    pub const LIBERO: AbilityId = 94;
    pub const LIGHTMETAL: AbilityId = 95;
    pub const LIGHTNINGROD: AbilityId = 96;
    pub const LIMBER: AbilityId = 97;
    pub const LIQUIDOOZE: AbilityId = 98;
    pub const LIQUIDVOICE: AbilityId = 99;
    pub const LONGREACH: AbilityId = 100;
    pub const MAGICBOUNCE: AbilityId = 101;
    pub const MAGICGUARD: AbilityId = 102;
    pub const MAGICIAN: AbilityId = 103;
    pub const MAGMAARMOR: AbilityId = 104;
    pub const MARVELSCALE: AbilityId = 105;
    pub const MEGALAUNCHER: AbilityId = 106;
    pub const MEGASOL: AbilityId = 107;
    pub const MERCILESS: AbilityId = 108;
    pub const MIMICRY: AbilityId = 109;
    pub const MINUS: AbilityId = 110;
    pub const MIRRORARMOR: AbilityId = 111;
    pub const MOLDBREAKER: AbilityId = 112;
    pub const MOODY: AbilityId = 113;
    pub const MOTORDRIVE: AbilityId = 114;
    pub const MOXIE: AbilityId = 115;
    pub const MULTISCALE: AbilityId = 116;
    pub const MUMMY: AbilityId = 117;
    pub const NATURALCURE: AbilityId = 118;
    pub const NOGUARD: AbilityId = 119;
    pub const OBLIVIOUS: AbilityId = 120;
    pub const OPPORTUNIST: AbilityId = 121;
    pub const OVERCOAT: AbilityId = 122;
    pub const OVERGROW: AbilityId = 123;
    pub const OWNTEMPO: AbilityId = 124;
    pub const PARENTALBOND: AbilityId = 125;
    pub const PICKPOCKET: AbilityId = 126;
    pub const PICKUP: AbilityId = 127;
    pub const PIERCINGDRILL: AbilityId = 128;
    pub const PIXILATE: AbilityId = 129;
    pub const PLUS: AbilityId = 130;
    pub const POISONHEAL: AbilityId = 131;
    pub const POISONPOINT: AbilityId = 132;
    pub const POISONTOUCH: AbilityId = 133;
    pub const PRANKSTER: AbilityId = 134;
    pub const PRESSURE: AbilityId = 135;
    pub const PROTEAN: AbilityId = 136;
    pub const PSYCHICSURGE: AbilityId = 137;
    pub const PUNKROCK: AbilityId = 138;
    pub const PUREPOWER: AbilityId = 139;
    pub const PURIFYINGSALT: AbilityId = 140;
    pub const QUEENLYMAJESTY: AbilityId = 141;
    pub const QUICKDRAW: AbilityId = 142;
    pub const QUICKFEET: AbilityId = 143;
    pub const RAINDISH: AbilityId = 144;
    pub const RATTLED: AbilityId = 145;
    pub const RECEIVER: AbilityId = 146;
    pub const RECKLESS: AbilityId = 147;
    pub const REFRIGERATE: AbilityId = 148;
    pub const REGENERATOR: AbilityId = 149;
    pub const RIPEN: AbilityId = 150;
    pub const RIVALRY: AbilityId = 151;
    pub const ROCKHEAD: AbilityId = 152;
    pub const ROUGHSKIN: AbilityId = 153;
    pub const RUNAWAY: AbilityId = 154;
    pub const SANDFORCE: AbilityId = 155;
    pub const SANDRUSH: AbilityId = 156;
    pub const SANDSPIT: AbilityId = 157;
    pub const SANDSTREAM: AbilityId = 158;
    pub const SANDVEIL: AbilityId = 159;
    pub const SAPSIPPER: AbilityId = 160;
    pub const SCRAPPY: AbilityId = 161;
    pub const SCREENCLEANER: AbilityId = 162;
    pub const SEEDSOWER: AbilityId = 163;
    pub const SHADOWTAG: AbilityId = 164;
    pub const SHARPNESS: AbilityId = 165;
    pub const SHEDSKIN: AbilityId = 166;
    pub const SHEERFORCE: AbilityId = 167;
    pub const SHELLARMOR: AbilityId = 168;
    pub const SHIELDDUST: AbilityId = 169;
    pub const SHIELDSDOWN: AbilityId = 170;
    pub const SKILLLINK: AbilityId = 171;
    pub const SLUSHRUSH: AbilityId = 172;
    pub const SNIPER: AbilityId = 173;
    pub const SNOWCLOAK: AbilityId = 174;
    pub const SNOWWARNING: AbilityId = 175;
    pub const SOLARPOWER: AbilityId = 176;
    pub const SOLIDROCK: AbilityId = 177;
    pub const SOUNDPROOF: AbilityId = 178;
    pub const SPEEDBOOST: AbilityId = 179;
    pub const SPICYSPRAY: AbilityId = 180;
    pub const STAKEOUT: AbilityId = 181;
    pub const STALL: AbilityId = 182;
    pub const STALWART: AbilityId = 183;
    pub const STAMINA: AbilityId = 184;
    pub const STANCECHANGE: AbilityId = 185;
    pub const STATIC: AbilityId = 186;
    pub const STEADFAST: AbilityId = 187;
    pub const STEELYSPIRIT: AbilityId = 188;
    pub const STENCH: AbilityId = 189;
    pub const STICKYHOLD: AbilityId = 190;
    pub const STRONGJAW: AbilityId = 191;
    pub const STURDY: AbilityId = 192;
    pub const SUCTIONCUPS: AbilityId = 193;
    pub const SUPERLUCK: AbilityId = 194;
    pub const SUPERSWEETSYRUP: AbilityId = 195;
    pub const SUPREMEOVERLORD: AbilityId = 196;
    pub const SURGESURFER: AbilityId = 197;
    pub const SWARM: AbilityId = 198;
    pub const SWEETVEIL: AbilityId = 199;
    pub const SWIFTSWIM: AbilityId = 200;
    pub const SYMBIOSIS: AbilityId = 201;
    pub const SYNCHRONIZE: AbilityId = 202;
    pub const TANGLEDFEET: AbilityId = 203;
    pub const TECHNICIAN: AbilityId = 204;
    pub const TELEPATHY: AbilityId = 205;
    pub const THERMALEXCHANGE: AbilityId = 206;
    pub const THICKFAT: AbilityId = 207;
    pub const TORRENT: AbilityId = 208;
    pub const TOUGHCLAWS: AbilityId = 209;
    pub const TOXICDEBRIS: AbilityId = 210;
    pub const TRACE: AbilityId = 211;
    pub const UNAWARE: AbilityId = 212;
    pub const UNBURDEN: AbilityId = 213;
    pub const UNNERVE: AbilityId = 214;
    pub const UNSEENFIST: AbilityId = 215;
    pub const VITALSPIRIT: AbilityId = 216;
    pub const VOLTABSORB: AbilityId = 217;
    pub const WANDERINGSPIRIT: AbilityId = 218;
    pub const WATERABSORB: AbilityId = 219;
    pub const WATERBUBBLE: AbilityId = 220;
    pub const WEAKARMOR: AbilityId = 221;
    pub const WHITESMOKE: AbilityId = 222;
    pub const ZEROTOHERO: AbilityId = 223;
    pub const AIRLOCK: AbilityId = 224;
    pub const ANGERSHELL: AbilityId = 225;
    pub const ARENATRAP: AbilityId = 226;
    pub const ASONEGLASTRIER: AbilityId = 227;
    pub const ASONESPECTRIER: AbilityId = 228;
    pub const AURABREAK: AbilityId = 229;
    pub const BADDREAMS: AbilityId = 230;
    pub const BALLFETCH: AbilityId = 231;
    pub const BATTERY: AbilityId = 232;
    pub const BEADSOFRUIN: AbilityId = 233;
    pub const BEASTBOOST: AbilityId = 234;
    pub const CHILLINGNEIGH: AbilityId = 235;
    pub const COLORCHANGE: AbilityId = 236;
    pub const COMATOSE: AbilityId = 237;
    pub const COMMANDER: AbilityId = 238;
    pub const COSTAR: AbilityId = 239;
    pub const COTTONDOWN: AbilityId = 240;
    pub const DANCER: AbilityId = 241;
    pub const DARKAURA: AbilityId = 242;
    pub const DAUNTLESSSHIELD: AbilityId = 243;
    pub const DAZZLING: AbilityId = 244;
    pub const DEFEATIST: AbilityId = 245;
    pub const DELTASTREAM: AbilityId = 246;
    pub const DESOLATELAND: AbilityId = 247;
    pub const DOWNLOAD: AbilityId = 248;
    pub const DRAGONSMAW: AbilityId = 249;
    pub const FLAREBOOST: AbilityId = 250;
    pub const FLOWERGIFT: AbilityId = 251;
    pub const FULLMETALBODY: AbilityId = 252;
    pub const GALVANIZE: AbilityId = 253;
    pub const GORILLATACTICS: AbilityId = 254;
    pub const GRIMNEIGH: AbilityId = 255;
    pub const HADRONENGINE: AbilityId = 256;
    pub const HONEYGATHER: AbilityId = 257;
    pub const ICESCALES: AbilityId = 258;
    pub const INTREPIDSWORD: AbilityId = 259;
    pub const IRONBARBS: AbilityId = 260;
    pub const LINGERINGAROMA: AbilityId = 261;
    pub const MAGNETPULL: AbilityId = 262;
    pub const MINDSEYE: AbilityId = 263;
    pub const MISTYSURGE: AbilityId = 264;
    pub const MULTITYPE: AbilityId = 265;
    pub const MYCELIUMMIGHT: AbilityId = 266;
    pub const NEUROFORCE: AbilityId = 267;
    pub const NEUTRALIZINGGAS: AbilityId = 268;
    pub const NOABILITY: AbilityId = 269;
    pub const NORMALIZE: AbilityId = 270;
    pub const ORICHALCUMPULSE: AbilityId = 271;
    pub const PASTELVEIL: AbilityId = 272;
    pub const PERISHBODY: AbilityId = 273;
    pub const POISONPUPPETEER: AbilityId = 274;
    pub const POWERCONSTRUCT: AbilityId = 275;
    pub const POWEROFALCHEMY: AbilityId = 276;
    pub const POWERSPOT: AbilityId = 277;
    pub const PRIMORDIALSEA: AbilityId = 278;
    pub const PRISMARMOR: AbilityId = 279;
    pub const PROPELLERTAIL: AbilityId = 280;
    pub const PROTOSYNTHESIS: AbilityId = 281;
    pub const QUARKDRIVE: AbilityId = 282;
    pub const RKSSYSTEM: AbilityId = 283;
    pub const ROCKYPAYLOAD: AbilityId = 284;
    pub const SCHOOLING: AbilityId = 285;
    pub const SERENEGRACE: AbilityId = 286;
    pub const SHADOWSHIELD: AbilityId = 287;
    pub const SIMPLE: AbilityId = 288;
    pub const SLOWSTART: AbilityId = 289;
    pub const SOULHEART: AbilityId = 290;
    pub const STEAMENGINE: AbilityId = 291;
    pub const STEELWORKER: AbilityId = 292;
    pub const STORMDRAIN: AbilityId = 293;
    pub const SWORDOFRUIN: AbilityId = 294;
    pub const TABLETSOFRUIN: AbilityId = 295;
    pub const TANGLINGHAIR: AbilityId = 296;
    pub const TERAFORMZERO: AbilityId = 297;
    pub const TERASHELL: AbilityId = 298;
    pub const TERASHIFT: AbilityId = 299;
    pub const TERAVOLT: AbilityId = 300;
    pub const TINTEDLENS: AbilityId = 301;
    pub const TOXICBOOST: AbilityId = 302;
    pub const TOXICCHAIN: AbilityId = 303;
    pub const TRANSISTOR: AbilityId = 304;
    pub const TRIAGE: AbilityId = 305;
    pub const TRUANT: AbilityId = 306;
    pub const TURBOBLAZE: AbilityId = 307;
    pub const VESSELOFRUIN: AbilityId = 308;
    pub const VICTORYSTAR: AbilityId = 309;
    pub const WATERCOMPACTION: AbilityId = 310;
    pub const WATERVEIL: AbilityId = 311;
    pub const WELLBAKEDBODY: AbilityId = 312;
    pub const WIMPOUT: AbilityId = 313;
    pub const WINDPOWER: AbilityId = 314;
    pub const WINDRIDER: AbilityId = 315;
    pub const WONDERGUARD: AbilityId = 316;
    pub const WONDERSKIN: AbilityId = 317;
    pub const ZENMODE: AbilityId = 318;
}

pub const ABILITY_NAMES: [&str; ABILITY_COUNT] = [
    "Adaptability",
    "Aerilate",
    "Aftermath",
    "Analytic",
    "Anger Point",
    "Anticipation",
    "Armor Tail",
    "Aroma Veil",
    "Aura Guard",
    "Battle Armor",
    "Battle Bond",
    "Berserk",
    "Big Pecks",
    "Blaze",
    "Bulletproof",
    "Cheek Pouch",
    "Chlorophyll",
    "Clear Body",
    "Cloud Nine",
    "Competitive",
    "Compound Eyes",
    "Contrary",
    "Corrosion",
    "Cud Chew",
    "Curious Medicine",
    "Cursed Body",
    "Cute Charm",
    "Damp",
    "Defiant",
    "Disguise",
    "Dragonize",
    "Drizzle",
    "Drought",
    "Dry Skin",
    "Early Bird",
    "Earth Eater",
    "Eelevate",
    "Effect Spore",
    "Electric Surge",
    "Electromorphosis",
    "Embody Aspect (Cornerstone)",
    "Embody Aspect (Hearthflame)",
    "Embody Aspect (Teal)",
    "Embody Aspect (Wellspring)",
    "Emergency Exit",
    "Fairy Aura",
    "Filter",
    "Fire Mane",
    "Flame Body",
    "Flash Fire",
    "Flower Veil",
    "Fluffy",
    "Forecast",
    "Forewarn",
    "Friend Guard",
    "Frisk",
    "Fur Coat",
    "Gale Wings",
    "Gluttony",
    "Good as Gold",
    "Gooey",
    "Grass Pelt",
    "Grassy Surge",
    "Guard Dog",
    "Gulp Missile",
    "Guts",
    "Harvest",
    "Healer",
    "Heatproof",
    "Heavy Metal",
    "Hospitality",
    "Huge Power",
    "Hunger Switch",
    "Hustle",
    "Hydration",
    "Hyper Cutter",
    "Ice Body",
    "Ice Face",
    "Illuminate",
    "Illusion",
    "Immunity",
    "Imposter",
    "Infiltrator",
    "Innards Out",
    "Inner Focus",
    "Insomnia",
    "Intimidate",
    "Iron Fist",
    "Justified",
    "Keen Eye",
    "Klutz",
    "Leaf Guard",
    "Levitate",
    "Libero",
    "Light Metal",
    "Lightning Rod",
    "Limber",
    "Liquid Ooze",
    "Liquid Voice",
    "Long Reach",
    "Magic Bounce",
    "Magic Guard",
    "Magician",
    "Magma Armor",
    "Marvel Scale",
    "Mega Launcher",
    "Mega Sol",
    "Merciless",
    "Mimicry",
    "Minus",
    "Mirror Armor",
    "Mold Breaker",
    "Moody",
    "Motor Drive",
    "Moxie",
    "Multiscale",
    "Mummy",
    "Natural Cure",
    "No Guard",
    "Oblivious",
    "Opportunist",
    "Overcoat",
    "Overgrow",
    "Own Tempo",
    "Parental Bond",
    "Pickpocket",
    "Pickup",
    "Piercing Drill",
    "Pixilate",
    "Plus",
    "Poison Heal",
    "Poison Point",
    "Poison Touch",
    "Prankster",
    "Pressure",
    "Protean",
    "Psychic Surge",
    "Punk Rock",
    "Pure Power",
    "Purifying Salt",
    "Queenly Majesty",
    "Quick Draw",
    "Quick Feet",
    "Rain Dish",
    "Rattled",
    "Receiver",
    "Reckless",
    "Refrigerate",
    "Regenerator",
    "Ripen",
    "Rivalry",
    "Rock Head",
    "Rough Skin",
    "Run Away",
    "Sand Force",
    "Sand Rush",
    "Sand Spit",
    "Sand Stream",
    "Sand Veil",
    "Sap Sipper",
    "Scrappy",
    "Screen Cleaner",
    "Seed Sower",
    "Shadow Tag",
    "Sharpness",
    "Shed Skin",
    "Sheer Force",
    "Shell Armor",
    "Shield Dust",
    "Shields Down",
    "Skill Link",
    "Slush Rush",
    "Sniper",
    "Snow Cloak",
    "Snow Warning",
    "Solar Power",
    "Solid Rock",
    "Soundproof",
    "Speed Boost",
    "Spicy Spray",
    "Stakeout",
    "Stall",
    "Stalwart",
    "Stamina",
    "Stance Change",
    "Static",
    "Steadfast",
    "Steely Spirit",
    "Stench",
    "Sticky Hold",
    "Strong Jaw",
    "Sturdy",
    "Suction Cups",
    "Super Luck",
    "Supersweet Syrup",
    "Supreme Overlord",
    "Surge Surfer",
    "Swarm",
    "Sweet Veil",
    "Swift Swim",
    "Symbiosis",
    "Synchronize",
    "Tangled Feet",
    "Technician",
    "Telepathy",
    "Thermal Exchange",
    "Thick Fat",
    "Torrent",
    "Tough Claws",
    "Toxic Debris",
    "Trace",
    "Unaware",
    "Unburden",
    "Unnerve",
    "Unseen Fist",
    "Vital Spirit",
    "Volt Absorb",
    "Wandering Spirit",
    "Water Absorb",
    "Water Bubble",
    "Weak Armor",
    "White Smoke",
    "Zero to Hero",
    "Air Lock",
    "Anger Shell",
    "Arena Trap",
    "As One (Glastrier)",
    "As One (Spectrier)",
    "Aura Break",
    "Bad Dreams",
    "Ball Fetch",
    "Battery",
    "Beads of Ruin",
    "Beast Boost",
    "Chilling Neigh",
    "Color Change",
    "Comatose",
    "Commander",
    "Costar",
    "Cotton Down",
    "Dancer",
    "Dark Aura",
    "Dauntless Shield",
    "Dazzling",
    "Defeatist",
    "Delta Stream",
    "Desolate Land",
    "Download",
    "Dragon's Maw",
    "Flare Boost",
    "Flower Gift",
    "Full Metal Body",
    "Galvanize",
    "Gorilla Tactics",
    "Grim Neigh",
    "Hadron Engine",
    "Honey Gather",
    "Ice Scales",
    "Intrepid Sword",
    "Iron Barbs",
    "Lingering Aroma",
    "Magnet Pull",
    "Mind's Eye",
    "Misty Surge",
    "Multitype",
    "Mycelium Might",
    "Neuroforce",
    "Neutralizing Gas",
    "No Ability",
    "Normalize",
    "Orichalcum Pulse",
    "Pastel Veil",
    "Perish Body",
    "Poison Puppeteer",
    "Power Construct",
    "Power of Alchemy",
    "Power Spot",
    "Primordial Sea",
    "Prism Armor",
    "Propeller Tail",
    "Protosynthesis",
    "Quark Drive",
    "RKS System",
    "Rocky Payload",
    "Schooling",
    "Serene Grace",
    "Shadow Shield",
    "Simple",
    "Slow Start",
    "Soul-Heart",
    "Steam Engine",
    "Steelworker",
    "Storm Drain",
    "Sword of Ruin",
    "Tablets of Ruin",
    "Tangling Hair",
    "Teraform Zero",
    "Tera Shell",
    "Tera Shift",
    "Teravolt",
    "Tinted Lens",
    "Toxic Boost",
    "Toxic Chain",
    "Transistor",
    "Triage",
    "Truant",
    "Turboblaze",
    "Vessel of Ruin",
    "Victory Star",
    "Water Compaction",
    "Water Veil",
    "Well-Baked Body",
    "Wimp Out",
    "Wind Power",
    "Wind Rider",
    "Wonder Guard",
    "Wonder Skin",
    "Zen Mode",
];

pub fn name(id: AbilityId) -> &'static str {
    ABILITY_NAMES[(id - 1) as usize]
}


pub mod ability_flags {
    pub const BREAKABLE: u8 = 1 << 0;
    pub const CANTSUPPRESS: u8 = 1 << 1;
    pub const FAILROLEPLAY: u8 = 1 << 2;
    pub const FAILSKILLSWAP: u8 = 1 << 3;
    pub const NOENTRAIN: u8 = 1 << 4;
    pub const NORECEIVER: u8 = 1 << 5;
    pub const NOTRACE: u8 = 1 << 6;
    pub const NOTRANSFORM: u8 = 1 << 7;
}


pub const ABILITY_FLAGS: [u8; ABILITY_COUNT] = [
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000001,
    0b00000001,
    0b01111110,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b11111111,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b11111100,
    0b11111100,
    0b11111100,
    0b11111100,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000001,
    0b01110100,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b10000010,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b11111100,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b11111111,
    0b00000001,
    0b01111100,
    0b00000001,
    0b01110100,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01110100,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b01111110,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01111110,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01110100,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000001,
    0b11111110,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01111110,
    0b01111110,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01111110,
    0b01111100,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01110101,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b01111110,
    0b00000000,
    0b00000000,
    0b11111100,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b01111100,
    0b01111110,
    0b01110100,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b11111100,
    0b11111100,
    0b01111110,
    0b00000000,
    0b01111110,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000000,
    0b01111100,
    0b01111101,
    0b11111110,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00000001,
    0b00000000,
    0b00000000,
    0b00000001,
    0b00111101,
    0b00000001,
    0b01111110,
];


pub const fn has_flag(id: AbilityId, flag: u8) -> bool {
    id != 0 && ABILITY_FLAGS[(id - 1) as usize] & flag != 0
}


pub const ABILITY_FLAG_OVERRIDES_GEN5: &[(AbilityId, u8)] = &[
    (79, 0b00000000),
    (122, 0b00000000),
    (316, 0b00101101),
    (318, 0b01010100),
];


pub const ABILITY_FLAG_OVERRIDES_GEN6: &[(AbilityId, u8)] = &[
    (79, 0b00000000),
    (316, 0b00101101),
    (318, 0b01010100),
    (242, 0b00000001),
    (46, 0b00000001),
];


pub const ABILITY_FLAG_OVERRIDES_GEN7: &[(AbilityId, u8)] = &[
    (79, 0b00000000),
    (316, 0b00101101),
    (242, 0b00000001),
    (46, 0b00000001),
];


pub const ABILITY_FLAG_OVERRIDES_GEN9_PREDLC: &[(AbilityId, u8)] = &[
    (79, 0b00000000),
    (238, 0b11111110),
    (256, 0b11111110),
    (271, 0b11111110),
    (281, 0b11111110),
    (282, 0b11111110),
];


pub const ABILITY_FLAG_OVERRIDES_GEN8: &[(AbilityId, u8)] = &[
    (65, 0b11111110),
    (79, 0b00000000),
    (316, 0b00101101),
];


pub fn has_flag_in(overrides: &[(AbilityId, u8)], id: AbilityId, flag: u8) -> bool {
    match overrides.iter().find(|&&(o, _)| o == id) {
        Some(&(_, flags)) => flags & flag != 0,
        None => has_flag(id, flag),
    }
}
