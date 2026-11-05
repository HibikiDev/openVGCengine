

















use std::path::Path;

use engine_core::action::JointAction;
use engine_core::battle::Battle;
use engine_core::event::EventRing;
use engine_core::field::Field;
use engine_core::pending::Pending;
use engine_core::rng::Rng;
use engine_core::turn::step_with_hits;
use serde_json::Value;

use crate::compare::{status_to_id, terrain_to_id, weather_to_id};
use crate::fixture_io::{
    build_side, field_has_pseudo_weather, field_terrain, field_weather, mon_boosts, mon_hp, mon_pp, mon_status, parse_choice,
    parse_rng_trace, run_oracle, side_condition_layers, side_has_condition, Scenario,
};





fn compare_exact(battle: &Battle, snapshot: &Value, turn_label: &str, messages: &mut Vec<String>) {
    for (side_i, side) in battle.sides.iter().enumerate() {
        for (slot_i, mon) in side.mons.iter().enumerate() {
            let our_hp = mon.hp as i64;
            let oracle_hp = mon_hp(snapshot, side_i, slot_i);
            if our_hp != oracle_hp {
                messages.push(format!("{turn_label} FAIL hp p{} slot{}: ours={our_hp} oracle={oracle_hp}", side_i + 1, slot_i));
            }

            let our_boosts = [mon.boosts[0] as i64, mon.boosts[1] as i64, mon.boosts[2] as i64, mon.boosts[3] as i64, mon.boosts[4] as i64];
            let oracle_boosts = mon_boosts(snapshot, side_i, slot_i);
            if our_boosts != oracle_boosts {
                messages.push(format!("{turn_label} FAIL boosts p{} slot{}: ours={our_boosts:?} oracle={oracle_boosts:?}", side_i + 1, slot_i));
            }

            if let Some(oracle_pp) = mon_pp(snapshot, side_i, slot_i) {
                let ours: Vec<i64> = mon.moves.iter().zip(mon.pp.iter()).filter(|(&m, _)| m != 0).map(|(_, &pp)| pp as i64).collect();
                if ours != oracle_pp {
                    messages.push(format!("{turn_label} FAIL pp p{} slot{}: ours={ours:?} oracle={oracle_pp:?}", side_i + 1, slot_i));
                }
            }


            let pokemon = &snapshot["sides"][side_i]["pokemon"][slot_i];
            let to_id = |s: &str| s.chars().filter(|c| c.is_ascii_alphanumeric()).map(|c| c.to_ascii_lowercase()).collect::<String>();
            if let Some(oracle_item) = pokemon["item"].as_str() {
                let ours = if mon.item == 0 { String::new() } else { to_id(engine_data::items_table::name(mon.item)) };
                if ours != oracle_item {
                    messages.push(format!("{turn_label} FAIL item p{} slot{}: ours={ours:?} oracle={oracle_item:?}", side_i + 1, slot_i));
                }
            }
            if let Some(oracle_ability) = pokemon["ability"].as_str() {

                let real = if mon.volatiles.has(engine_core::mon::volatile_flags::GASTRO_ACID)
                    || mon.flags.has(engine_core::mon::mon_flags::NGAS_SUPPRESSED)
                {
                    mon.suppressed_ability
                } else {
                    mon.ability
                };
                let ours = if real == 0 { String::new() } else { to_id(engine_data::abilities_table::name(real)) };
                if ours != oracle_ability {
                    messages.push(format!("{turn_label} FAIL ability p{} slot{}: ours={ours:?} oracle={oracle_ability:?}", side_i + 1, slot_i));
                }
            }
            if let Some(oracle_species) = pokemon["species"].as_str() {
                let ours = to_id(engine_data::species_table::get(mon.species).name);
                if ours != to_id(oracle_species) {
                    messages.push(format!("{turn_label} FAIL species p{} slot{}: ours={ours:?} oracle={oracle_species:?}", side_i + 1, slot_i));
                }
            }




            let oracle_status = mon_status(snapshot, side_i, slot_i);
            let our_status = status_to_id(mon.status);
            if oracle_status != "fnt" && mon.hp != 0 && our_status != oracle_status {
                messages.push(format!("{turn_label} FAIL status p{} slot{}: ours={our_status:?} oracle={oracle_status:?}", side_i + 1, slot_i));
            }
        }
    }

    let our_weather = weather_to_id(battle.field.weather);
    let oracle_weather = field_weather(snapshot);
    if our_weather != oracle_weather {
        messages.push(format!("{turn_label} FAIL weather: ours={our_weather:?} oracle={oracle_weather:?}"));
    }
    let our_terrain = terrain_to_id(battle.field.terrain);
    let oracle_terrain = field_terrain(snapshot);
    if our_terrain != oracle_terrain {
        messages.push(format!("{turn_label} FAIL terrain: ours={our_terrain:?} oracle={oracle_terrain:?}"));
    }
    let our_trick_room = battle.field.trick_room_turns > 0;
    let oracle_trick_room = field_has_pseudo_weather(snapshot, "trickroom");
    if our_trick_room != oracle_trick_room {
        messages.push(format!("{turn_label} FAIL trick room: ours={our_trick_room} oracle={oracle_trick_room}"));
    }

    for side_i in 0..2usize {
        let conds = &battle.sides[side_i].side_conditions;
        let bool_checks: [(&str, bool); 6] = [
            ("reflect", conds.reflect_turns > 0),
            ("lightscreen", conds.light_screen_turns > 0),
            ("auroraveil", conds.aurora_veil_turns > 0),
            ("tailwind", conds.tailwind_turns > 0),
            ("stealthrock", conds.stealth_rock),
            ("stickyweb", conds.sticky_web),
        ];
        for (id, ours) in bool_checks {
            let theirs = side_has_condition(snapshot, side_i, id);
            if ours != theirs {
                messages.push(format!("{turn_label} FAIL side{} condition {id}: ours={ours} oracle={theirs}", side_i + 1));
            }
        }
        for (id, ours) in [("spikes", conds.spikes), ("toxicspikes", conds.toxic_spikes)] {
            let theirs = side_condition_layers(snapshot, side_i, id);
            if ours as i64 != theirs {
                messages.push(format!("{turn_label} FAIL side{} layers {id}: ours={ours} oracle={theirs}", side_i + 1));
            }
        }
    }
}



fn compare_legal(battle: &Battle, legal: &Value, step_label: &str, messages: &mut Vec<String>) {
    use engine_core::legal;
    use std::collections::BTreeSet;
    for side in 0..2u8 {
        let oracle = &legal[if side == 0 { "p1" } else { "p2" }];
        let mask = legal::side_mask(battle, side);
        if oracle.is_null() || !mask.to_move {
            if oracle.is_null() != !mask.to_move {
                messages.push(format!("{step_label} legal p{}: oracle has a request: {}, engine to_move: {}", side + 1, !oracle.is_null(), mask.to_move));
            }
            continue;
        }
        let mut showdown = BTreeSet::new();
        for choice in oracle.as_array().expect("legal choices are an array") {
            let mut actions = parse_choice(choice.as_str().unwrap());
            for act in actions.iter_mut() {
                if let engine_core::action::Action::Switch { bench_slot } = act {
                    *bench_slot = battle.sides[side as usize].order[*bench_slot as usize];
                }
            }
            showdown.insert([legal::encode(battle, side, 0, actions[0]), legal::encode(battle, side, 1, actions[1])]);
        }
        let mut engine = BTreeSet::new();
        legal::for_each_legal_joint(&mask, |joint| {
            engine.insert(joint);
        });
        if showdown != engine {
            let show = |set: Vec<&[(usize, bool); 2]>| set.iter().take(8).map(|j| format!("{}", joint_label(j))).collect::<Vec<_>>().join(" | ");
            messages.push(format!(
                "{step_label} legal p{}: engine-only [{}] ({}), showdown-only [{}] ({})",
                side + 1,
                show(engine.difference(&showdown).collect()),
                engine.difference(&showdown).count(),
                show(showdown.difference(&engine).collect()),
                showdown.difference(&engine).count(),
            ));
        }
    }
}


fn joint_label(joint: &[(usize, bool); 2]) -> String {
    use engine_core::legal::*;
    let one = |(a, mega): (usize, bool)| {
        let s = if a == PASS_ACTION {
            "pass".to_string()
        } else if a >= SWITCH_BASE {
            format!("switch mon{}", a - SWITCH_BASE)
        } else {
            format!("move {} {}", a / 4 + 1, ["foeA", "foeB", "ally", "self"][a % 4])
        };
        if mega { format!("{s} +mega") } else { s }
    };
    format!("{}, {}", one(joint[0]), one(joint[1]))
}



fn seat_switch_parts(parts: JointAction, owed: [bool; 2]) -> JointAction {
    use engine_core::action::Action;
    let mut seated = [Action::Pass; 2];
    let mut index = 0;
    for part in parts {
        if part != Action::Pass {
            while index < 2 && !owed[index] {
                index += 1;
            }
        }
        if index >= 2 {
            break;
        }
        seated[index] = part;
        index += 1;
    }
    seated
}



fn obs_json(battle: &Battle) -> Value {
    let ctx = engine_obs::ObsContext::from_battle(battle);
    let mut sides = Vec::new();
    for side in 0..2u8 {
        let [fs, is, ms, hs] = engine_obs::BUFFER_SIZES;
        let (mut f, mut i, mut m, mut h) = (vec![0f32; fs], vec![0i32; is], vec![0f32; ms], vec![0i32; hs]);
        engine_obs::encode(battle, &ctx, side, engine_obs::ObsBuffers { field: &mut f, mon_ids: &mut i, mon_features: &mut m, history: &mut h });
        let mask = engine_core::legal::side_mask(battle, side);
        let masks = serde_json::json!({
            "to_move": mask.to_move,
            "min_switches": mask.min_switches,

            "actions": mask.slots.map(|sl| sl.plain_actions()),
            "mega": mask.slots.map(|sl| sl.mega || sl.z_moves != 0),
            "gimmick": mask.slots.map(|sl| sl.gimmick_masks().0),
            "forced": mask.slots.map(|sl| sl.gimmick_masks().1),
            "kind": mask.slots.map(|sl| sl.gimmick_masks().2),
        });
        sides.push(serde_json::json!({ "field": f, "mon_ids": i, "mon_features": m, "history": h, "masks": masks }));
    }
    Value::Array(sides)
}



pub fn run(scenario_path: &str, obs_out: Option<&str>) -> bool {
    let path = Path::new(scenario_path);
    let scenario = Scenario::load(path);
    let oracle_result = run_oracle(path);
    let trace = parse_rng_trace(&oracle_result);
    println!("rng_trace: {} recorded draws", trace.len());

    if std::env::var_os("REPLAY_DEBUG").is_some() {
        engine_core::damage::DEBUG_DAMAGE.store(true, std::sync::atomic::Ordering::Relaxed);
        engine_core::rng::TRACE_DRAWS.store(true, std::sync::atomic::Ordering::Relaxed);
    }
    let format = scenario.engine_format();
    let rules = engine_core::rules::Rules::of(format);
    let mut battle = Battle {
        sides: [build_side(rules, &scenario.team1), build_side(rules, &scenario.team2)],
        field: Field::default(),
        turn: 0,
        rng: Rng::new_replay(trace),
        pending: Pending::Turn,
        history: EventRing::default(),
        resume: None,
        end_turn_pending: false,
        started: false,
        opportunist: [[0; 7]; 4],
        opportunist_bank: 0,
        format,
        speed_order: [0, 1, 2, 3],
        ability_seq: 0,
        dance_move: 0,
        active_target: 0,
    };

    engine_core::turn::start_battle(&mut battle);

    let speeds = |battle: &Battle, when: &str| {
        if std::env::var_os("REPLAY_DEBUG").is_some() {
            for s in 0..2 {
                for sl in 0..2 {
                    let m = &battle.sides[s].mons[battle.sides[s].active[sl] as usize];
                    eprintln!("  {when} p{}{}: boosts {:?} speed_cache {} opportunist {:?}", s + 1, ["a", "b"][sl], m.boosts, m.speed_cache, battle.opportunist[s * 2 + sl]);
                }
            }
        }
    };
    speeds(&battle, "start");

    let mut messages = Vec::new();
    let mut observations = Vec::new();


    let mut dumps = Vec::new();
    for (i, turn_choices) in scenario.turns.iter().enumerate() {
        if obs_out.is_some() {
            observations.push(obs_json(&battle));
            dumps.push(Value::String(format!("{:#?}", (&battle.sides, &battle.field, battle.turn, &battle.pending))));
        }
        if let Some(legal) = oracle_result["legal"].get(i) {
            let before = messages.len();
            compare_legal(&battle, legal, &format!("step {}", i + 1), &mut messages);
            for m in &messages[before..] {
                eprintln!("MISMATCH {m}");
            }
        }
        let mut actions: [JointAction; 2] = [parse_choice(&turn_choices.p1), parse_choice(&turn_choices.p2)];
        if let Pending::ForcedSwitch { .. } = battle.pending {
            for side in 0..2 {
                let owed = engine_core::turn::owed_replacements(&battle, side as u8);
                actions[side] = seat_switch_parts(actions[side], owed);
            }
        }

        for side in 0..2 {
            for act in actions[side].iter_mut() {
                if let engine_core::action::Action::Switch { bench_slot } = act {
                    *bench_slot = battle.sides[side].order[*bench_slot as usize];
                }
            }
        }
        eprintln!("STEP {}: p1 \"{}\" p2 \"{}\" (pending {:?})", i + 1, turn_choices.p1, turn_choices.p2, battle.pending);
        step_with_hits(&mut battle, actions);
        speeds(&battle, "after step");
        if std::env::var_os("REPLAY_DEBUG").is_some() {
            eprintln!("  after step: turn={} weather={:?}/{} terrain={:?}/{} trick_room={} tw={:?} pending={:?}", battle.turn, battle.field.weather, battle.field.weather_turns, battle.field.terrain, battle.field.terrain_turns, battle.field.trick_room_turns, [battle.sides[0].side_conditions.tailwind_turns, battle.sides[1].side_conditions.tailwind_turns], battle.pending);
            let fut = |s: usize| (battle.sides[s].side_conditions.future_turns, battle.sides[s].side_conditions.future_source);
            eprintln!("  future (turns, source): {:?} {:?}", fut(0), fut(1));
            eprintln!("  party: {:?}", (0..2).map(|s| (battle.sides[s].order.clone(), battle.sides[s].mons.iter().map(|m| (m.species, m.hp)).collect::<Vec<_>>())).collect::<Vec<_>>());
            eprintln!("  actives: {:?}", (0..2).flat_map(|s| (0..2).map(move |sl| (s, sl))).map(|(s, sl)| { let m = &battle.sides[s].mons[battle.sides[s].active[sl] as usize]; (m.species, m.ability, m.hp, m.item, m.sub_hp, m.perish_turns) }).collect::<Vec<_>>());
        }


        let snapshot = &oracle_result["snapshots"][i + 1];
        let before = messages.len();
        compare_exact(&battle, snapshot, &format!("turn {}", i + 1), &mut messages);


        if snapshot["ended"].as_bool() == Some(true) {
            let theirs = match snapshot["winner"].as_str() {
                Some("p1") => Some(0u8),
                Some("p2") => Some(1),
                _ => None,
            };
            match battle.pending {
                Pending::Over { winner } if winner == theirs => {}
                ref ours => messages.push(format!("turn {} FAIL result: ours={ours:?} oracle winner={theirs:?}", i + 1)),
            }
        }

        for m in &messages[before..] {
            eprintln!("MISMATCH {m}");
        }
    }

    if let Some(path) = obs_out {
        observations.push(obs_json(&battle));
        dumps.push(Value::String(format!("{:#?}", (&battle.sides, &battle.field, battle.turn, &battle.pending))));
        std::fs::write(path, serde_json::to_string(&observations).unwrap()).unwrap_or_else(|e| panic!("writing {path}: {e}"));
        let dump_path = format!("{path}.dumps.json");
        std::fs::write(&dump_path, serde_json::to_string(&dumps).unwrap()).unwrap_or_else(|e| panic!("writing {dump_path}: {e}"));
    }

    if let Some(n) = battle.rng.unconsumed_real_draws().filter(|&n| n > 0) {
        messages.push(format!("end FAIL rng: {n} real oracle draw(s) never consumed"));
        eprintln!("MISMATCH end FAIL rng: {n} real oracle draw(s) never consumed");
    }
    for msg in &messages {
        println!("{msg}");
    }
    println!(
        "\n=== {} ({} turns played, {} exact mismatches) ===",
        if messages.is_empty() { "PASS" } else { "FAIL" },
        scenario.turns.len(),
        messages.len(),
    );
    messages.is_empty()
}
