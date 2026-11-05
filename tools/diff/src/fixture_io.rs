






use std::io::{BufRead, BufReader, Write};
use std::path::Path;
use std::process::{Child, ChildStdin, ChildStdout, Command, Stdio};
use std::sync::Mutex;

use engine_core::action::{Action, JointAction};
use engine_core::ids::NONE_ID;
use engine_core::side::{Side, SideConds};
use serde::Deserialize;
use serde_json::Value;

use crate::fixtures::build_mon;

#[derive(Deserialize)]
pub(crate) struct FixtureSet {

    #[serde(default)]
    pub(crate) gender: String,
    pub(crate) species: String,
    pub(crate) moves: Vec<String>,
    pub(crate) nature: String,
    pub(crate) evs: FixtureEvs,

    #[serde(default)]
    pub(crate) ivs: Option<FixtureEvs>,







    #[serde(default)]
    pub(crate) ability: Option<String>,

    #[serde(default)]
    pub(crate) item: Option<String>,

    #[serde(default)]
    pub(crate) happiness: Option<u8>,

    #[serde(default, rename = "teraType")]
    pub(crate) tera_type: Option<String>,

    #[serde(default)]
    pub(crate) gigantamax: bool,

    #[serde(default, rename = "dynamaxLevel")]
    pub(crate) dynamax_level: Option<u8>,
}

#[derive(Deserialize)]
pub(crate) struct FixtureEvs {
    pub(crate) hp: u32,
    pub(crate) atk: u32,
    pub(crate) def: u32,
    pub(crate) spa: u32,
    pub(crate) spd: u32,
    pub(crate) spe: u32,
}

#[derive(Deserialize)]
pub(crate) struct FixtureTurn {
    pub(crate) p1: String,
    pub(crate) p2: String,
}

#[derive(Deserialize)]
pub(crate) struct Scenario {
    pub(crate) format: String,
    pub(crate) team1: Vec<FixtureSet>,
    pub(crate) team2: Vec<FixtureSet>,
    pub(crate) turns: Vec<FixtureTurn>,
}

impl Scenario {

    pub(crate) fn engine_format(&self) -> engine_core::rules::Format {
        engine_core::rules::Format::from_id(&self.format).unwrap_or_else(|| panic!("scenario format {:?}: not one the engine plays", self.format))
    }

    pub(crate) fn load(path: &Path) -> Scenario {
        serde_json::from_slice(&std::fs::read(path).unwrap_or_else(|e| panic!("reading {}: {e}", path.display())))
            .unwrap_or_else(|e| panic!("parsing {}: {e}", path.display()))
    }
}







pub(crate) fn parse_choice(choice: &str) -> JointAction {
    let parts: Vec<&str> = choice.split(',').map(str::trim).collect();
    assert_eq!(parts.len(), 2, "expected exactly 2 move choices in \"{choice}\"");
    let parse_one = |s: &str| {
        let mut tokens: Vec<&str> = s.split_whitespace().collect();


        if tokens[0] == "switch" {
            return Action::Switch { bench_slot: tokens[1].parse::<u8>().unwrap() - 1 };
        }
        if tokens[0] == "pass" {
            return Action::Pass;
        }
        assert_eq!(tokens[0], "move", "only move/switch/pass choices are supported in fixtures: \"{s}\"");



        let mega = matches!(tokens.last(), Some(&"mega") | Some(&"ultra") | Some(&"terastallize") | Some(&"dynamax"));
        if mega {
            tokens.pop();
        }

        let z = tokens.last() == Some(&"zmove");
        if z {
            tokens.pop();
        }
        let move_slot: u8 = tokens[1].parse::<u8>().unwrap() - 1;


        let target_slot: u8 = tokens.get(2).map(|t| { let v = t.parse::<i8>().unwrap(); if v > 0 { v as u8 - 1 } else { (1 - v) as u8 } }).unwrap_or(0);
        Action::Move { move_slot, target_slot, mega, z }
    };
    [parse_one(parts[0]), parse_one(parts[1])]
}

pub(crate) fn move_name_to_id(name: &str) -> u16 {

    engine_data::lookup::move_id(name).unwrap_or_else(|| panic!("fixture uses a move engine-core doesn't support yet: \"{name}\""))
}








pub(crate) fn to_id(s: &str) -> String {
    s.chars().filter(|c| c.is_ascii_alphanumeric()).map(|c| c.to_ascii_lowercase()).collect()
}








pub(crate) fn ability_name_to_id(name: &str) -> engine_data::abilities_table::AbilityId {
    use engine_data::abilities_table::ABILITY_NAMES;
    let target = to_id(name);
    (1..=ABILITY_NAMES.len())
        .find(|&id| to_id(ABILITY_NAMES[id - 1]) == target)
        .unwrap_or_else(|| panic!("fixture uses an ability not in the legal pool: \"{name}\"")) as engine_data::abilities_table::AbilityId
}



pub(crate) fn item_name_to_id(name: &str) -> engine_data::items_table::ItemId {
    use engine_data::items_table::ITEM_NAMES;
    let target = to_id(name);
    (1..=ITEM_NAMES.len())
        .find(|&id| to_id(ITEM_NAMES[id - 1]) == target)
        .unwrap_or_else(|| panic!("fixture uses an item not in the legal pool: \"{name}\"")) as engine_data::items_table::ItemId
}


pub(crate) fn set_gender(g: &str) -> engine_core::team::SetGender {
    use engine_core::team::SetGender;
    match g {
        "M" => SetGender::Male,
        "F" => SetGender::Female,
        "N" => SetGender::Genderless,
        "" => SetGender::Unspecified,
        _ => panic!("fixture gender {g:?}"),
    }
}

pub(crate) fn build_side(rules: &engine_core::rules::Rules, sets: &[FixtureSet]) -> Side {
    assert_eq!(sets.len(), 4, "fixtures must bring exactly 4 (M1 has no bench/switching)");
    let mon = |s: &FixtureSet| {
        let mut moves = [0u16; 4];
        for (i, m) in s.moves.iter().enumerate() {
            moves[i] = move_name_to_id(m);
        }
        let pts = [s.evs.hp, s.evs.atk, s.evs.def, s.evs.spa, s.evs.spd, s.evs.spe];
        let ivs = s.ivs.as_ref().map_or([31; 6], |v| [v.hp, v.atk, v.def, v.spa, v.spd, v.spe]);
        let ability = s.ability.as_deref().map_or(NONE_ID, ability_name_to_id);
        let item = s.item.as_deref().filter(|i| !i.is_empty()).map_or(NONE_ID, item_name_to_id);
        let mut m = build_mon(rules, &s.species, &s.nature, pts, ivs, moves, ability, item, set_gender(&s.gender));
        m.happiness = s.happiness.unwrap_or(255);
        if s.gigantamax {
            m.flags.set(engine_core::mon::mon_flags::GIGANTAMAX);
        }
        m.dynamax_level = s.dynamax_level.unwrap_or(10);
        if let (Some(t), true) = (s.tera_type.as_deref().filter(|t| !t.is_empty()), rules.terastallization) {
            m.tera.tera_type = Some(engine_data::type_chart::Type::from_name(t).unwrap_or_else(|| panic!("unknown teraType \"{t}\"")));
        }
        m
    };
    Side {
        mons: [mon(&sets[0]), mon(&sets[1]), mon(&sets[2]), mon(&sets[3])],
        active: [0, 1, engine_core::side::NO_PHANTOM],
        side_conditions: SideConds::default(),
        mega_used: false,
        z_used: false, ultra_used: false, tera_used: false, dynamax_used: false,
        revivals: 0,
        order: [0, 1, 2, 3],
    }
}

struct OracleServer {
    _child: Child,
    stdin: ChildStdin,
    stdout: BufReader<ChildStdout>,
}

static ORACLE_SERVER: Mutex<Option<OracleServer>> = Mutex::new(None);



pub(crate) fn start_oracle_server() {
    let script = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().join("showdown-oracle").join("scripted.js");
    let mut child = Command::new("node")
        .arg(&script)
        .arg("--serve")
        .stdin(Stdio::piped())
        .stdout(Stdio::piped())
        .spawn()
        .unwrap_or_else(|e| panic!("failed to spawn node on {}: {e}", script.display()));
    let stdin = child.stdin.take().unwrap();
    let stdout = BufReader::new(child.stdout.take().unwrap());
    *ORACLE_SERVER.lock().unwrap_or_else(|e| e.into_inner()) = Some(OracleServer { _child: child, stdin, stdout });
}




pub(crate) fn run_oracle(scenario_path: &Path) -> Value {
    let script = Path::new(env!("CARGO_MANIFEST_DIR")).parent().unwrap().join("showdown-oracle").join("scripted.js");


    let mut server = ORACLE_SERVER.lock().unwrap_or_else(|e| e.into_inner());
    if let Some(s) = server.as_mut() {
        writeln!(s.stdin, "{}", scenario_path.display()).expect("writing to the oracle server");
        let mut line = String::new();
        s.stdout.read_line(&mut line).expect("reading from the oracle server");
        let v: Value = serde_json::from_str(&line).unwrap_or_else(|e| panic!("oracle server line isn't JSON ({e}): {line:.200}"));
        if let Some(err) = v.get("error") {
            panic!("scripted.js --serve failed on {}:\n{}", scenario_path.display(), err.as_str().unwrap_or(""));
        }
        return v;
    }
    drop(server);
    let output = Command::new("node")
        .arg(&script)
        .arg(scenario_path)
        .output()
        .unwrap_or_else(|e| panic!("failed to spawn node on {}: {e}", script.display()));
    if !output.status.success() {
        eprintln!("oracle stderr:\n{}", String::from_utf8_lossy(&output.stderr));
        panic!("scripted.js exited with {}", output.status);
    }
    serde_json::from_slice(&output.stdout).expect("scripted.js printed valid JSON")
}

pub(crate) fn mon_hp(snapshot: &Value, side: usize, slot: usize) -> i64 {
    snapshot["sides"][side]["pokemon"][slot]["hp"].as_i64().unwrap()
}


pub(crate) fn mon_pp(snapshot: &Value, side: usize, slot: usize) -> Option<Vec<i64>> {
    snapshot["sides"][side]["pokemon"][slot]["pp"].as_array().map(|a| a.iter().map(|v| v.as_i64().unwrap_or(-1)).collect())
}

pub(crate) fn mon_boosts(snapshot: &Value, side: usize, slot: usize) -> [i64; 5] {
    let b = &snapshot["sides"][side]["pokemon"][slot]["boosts"];
    [
        b["atk"].as_i64().unwrap(),
        b["def"].as_i64().unwrap(),
        b["spa"].as_i64().unwrap(),
        b["spd"].as_i64().unwrap(),
        b["spe"].as_i64().unwrap(),
    ]
}

pub(crate) fn mon_status(snapshot: &Value, side: usize, slot: usize) -> String {
    snapshot["sides"][side]["pokemon"][slot]["status"].as_str().unwrap_or("").to_string()
}

pub(crate) fn field_weather(snapshot: &Value) -> String {
    snapshot["weather"].as_str().unwrap_or("").to_string()
}

pub(crate) fn field_terrain(snapshot: &Value) -> String {
    snapshot["terrain"].as_str().unwrap_or("").to_string()
}

pub(crate) fn field_has_pseudo_weather(snapshot: &Value, id: &str) -> bool {
    snapshot["pseudoWeather"].as_array().is_some_and(|a| a.iter().any(|v| v.as_str() == Some(id)))
}

pub(crate) fn side_has_condition(snapshot: &Value, side: usize, id: &str) -> bool {
    snapshot["sides"][side]["sideConditions"].get(id).is_some()
}

pub(crate) fn side_condition_layers(snapshot: &Value, side: usize, id: &str) -> i64 {
    snapshot["sides"][side]["sideConditions"][id]["layers"].as_i64().unwrap_or(0)
}






pub(crate) fn parse_rng_trace(oracle_result: &Value) -> &'static [engine_core::rng::ReplayDraw] {
    let arr = oracle_result["rng_trace"].as_array().unwrap_or_else(|| {
        panic!("oracle output has no \"rng_trace\" array - is scripted.js's rng-trace.js instrumentation present?")
    });
    let draws: Vec<engine_core::rng::ReplayDraw> = arr
        .iter()
        .map(|v| engine_core::rng::ReplayDraw {
            from: v["from"].as_u64().map(|n| n as u32),
            to: v["to"].as_u64().map(|n| n as u32),
            result: v["result"].as_f64().expect("rng_trace entry missing a numeric \"result\""),
            bookkeeping: v["bookkeeping"].as_bool().unwrap_or(false),
        })
        .collect();
    Box::leak(draws.into_boxed_slice())
}
