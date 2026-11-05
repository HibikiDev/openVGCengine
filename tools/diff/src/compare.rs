




















use engine_core::action::JointAction;
use engine_core::battle::Battle;
use engine_core::damage::possible_damages;
use engine_core::event::EventRing;
use engine_core::field::{Field, Terrain, Weather};
use engine_core::pending::Pending;
use engine_core::rng::Rng;
use engine_core::status::Status;
use engine_core::turn::{step_with_hits, HitRecord};
use engine_data::moves_table;
use serde_json::Value;

use crate::fixture_io::{
    build_side, field_has_pseudo_weather, field_terrain, field_weather, mon_boosts, mon_hp, mon_status, parse_choice,
    side_condition_layers, side_has_condition, Scenario,
};

pub struct ComparisonReport {
    pub stat_failures: usize,
    pub damage_failures: usize,
    pub exact_failures: usize,
    pub messages: Vec<String>,
}

impl ComparisonReport {
    pub fn total_failures(&self) -> usize {
        self.stat_failures + self.damage_failures + self.exact_failures
    }
}




pub(crate) fn status_to_id(status: Status) -> &'static str {
    match status {
        Status::None => "",
        Status::Burn => "brn",
        Status::Freeze => "frz",
        Status::Paralysis => "par",
        Status::Poison => "psn",
        Status::Toxic => "tox",
        Status::Sleep => "slp",
    }
}

pub(crate) fn weather_to_id(weather: Weather) -> &'static str {
    match weather {
        Weather::None => "",
        Weather::Sun => "sunnyday",
        Weather::Rain => "raindance",
        Weather::Sand => "sandstorm",
        Weather::Snow => "snowscape",
        Weather::Hail => "hail",
        Weather::DesolateLand => "desolateland",
        Weather::PrimordialSea => "primordialsea",
        Weather::DeltaStream => "deltastream",
    }
}

pub(crate) fn terrain_to_id(terrain: Terrain) -> &'static str {
    match terrain {
        Terrain::None => "",
        Terrain::Electric => "electricterrain",
        Terrain::Grassy => "grassyterrain",
        Terrain::Misty => "mistyterrain",
        Terrain::Psychic => "psychicterrain",
    }
}





























fn combined_possible_damage(hits: &[&HitRecord]) -> Vec<i64> {
    let mut sums = vec![0i64];
    for hit in hits {

        let range = if let Some(fixed) = hit.fixed_damage {
            vec![fixed]
        } else {
            let mut range = possible_damages(&hit.inputs).to_vec();
            let mut flipped = hit.inputs;
            flipped.is_crit = !hit.inputs.is_crit;
            flipped.attack = hit.inputs.attack_other_crit;
            flipped.defense = hit.inputs.defense_other_crit;
            range.extend(possible_damages(&flipped));
            range
        };
        sums = sums.iter().flat_map(|&s| range.iter().map(move |&r| s + r)).collect();
    }
    sums
}
















fn combined_possible_recoil(hits: &[&HitRecord]) -> Vec<i64> {
    let mut sums = vec![0i64];
    for hit in hits {
        let Some((num, den)) = moves_table::get(hit.move_id).recoil else { continue };
        let recoil_range: Vec<i64> = combined_possible_damage(std::slice::from_ref(hit))
            .iter()
            .map(|&d| engine_core::damage::round_frac(d, num as i64, den as i64).max(1))
            .collect();
        sums = sums.iter().flat_map(|&s| recoil_range.iter().map(move |&r| s + r)).collect();
    }
    sums
}





fn combined_possible_drain(hits: &[&HitRecord]) -> Vec<i64> {
    let mut sums = vec![0i64];
    for hit in hits {
        let Some((num, den)) = moves_table::get(hit.move_id).drain else { continue };
        let drain_range: Vec<i64> = combined_possible_damage(std::slice::from_ref(hit))
            .iter()
            .map(|&d| engine_core::damage::round_frac(d, num as i64, den as i64))
            .collect();
        sums = sums.iter().flat_map(|&s| drain_range.iter().map(move |&r| s + r)).collect();
    }
    sums
}


fn realized_drain(hits: &[&HitRecord]) -> i64 {
    hits.iter()
        .filter_map(|hit| moves_table::get(hit.move_id).drain.map(|(num, den)| engine_core::damage::round_frac(hit.damage_dealt, num as i64, den as i64)))
        .sum()
}





fn realized_recoil(hits: &[&HitRecord]) -> i64 {
    hits.iter()
        .filter_map(|hit| {
            moves_table::get(hit.move_id).recoil.map(|(num, den)| engine_core::damage::round_frac(hit.damage_dealt, num as i64, den as i64).max(1))
        })
        .sum()
}







fn realized_contact_punish(hits: &[&HitRecord]) -> i64 {
    hits.iter().map(|hit| hit.contact_punish_damage).sum()
}



pub fn compare_one_turn(scenario: &Scenario, oracle_result: &Value) -> ComparisonReport {
    assert_eq!(scenario.format, "gen9championsvgc2026regmc", "fixtures must use the pinned target format");
    assert!(!scenario.turns.is_empty(), "scenario has no turns");

    let mut battle = Battle {
        sides: {
            let rules = engine_core::rules::Rules::of(engine_core::rules::Format::ChampionsMC);
            [build_side(rules, &scenario.team1), build_side(rules, &scenario.team2)]
        },
        field: Field::default(),
        turn: 0,
        rng: Rng::new(1),
        pending: Pending::Turn,
        history: EventRing::default(),
        resume: None,
        end_turn_pending: false,
        started: false,
        opportunist: [[0; 7]; 4],
        opportunist_bank: 0,
        format: engine_core::rules::Format::ChampionsMC,
        speed_order: [0, 1, 2, 3],
        ability_seq: 0,
        dance_move: 0,
        active_target: 0,
    };

    let before = &oracle_result["snapshots"][0];
    let after = &oracle_result["snapshots"][1];

    let mut messages = Vec::new();
    let mut stat_failures = 0;


    for (side_i, side) in battle.sides.iter().enumerate() {
        for (slot_i, mon) in side.mons.iter().enumerate() {
            let oracle_stats = &before["sides"][side_i]["pokemon"][slot_i]["stats"];
            let ours = [mon.stats[0] as i64, mon.stats[1] as i64, mon.stats[2] as i64, mon.stats[3] as i64, mon.stats[4] as i64];
            let theirs = [
                oracle_stats["atk"].as_i64().unwrap(),
                oracle_stats["def"].as_i64().unwrap(),
                oracle_stats["spa"].as_i64().unwrap(),
                oracle_stats["spd"].as_i64().unwrap(),
                oracle_stats["spe"].as_i64().unwrap(),
            ];
            let hp_ok = mon.hp as i64 == mon_hp(before, side_i, slot_i);
            if ours != theirs || !hp_ok {
                stat_failures += 1;
                messages.push(format!(
                    "FAIL stats p{} slot{}: ours hp={} stats={:?} vs oracle hp={} stats={:?}",
                    side_i + 1, slot_i, mon.hp, ours, mon_hp(before, side_i, slot_i), theirs
                ));
            }
        }
    }

    let hp_before: [[u16; 4]; 2] =
        core::array::from_fn(|side| core::array::from_fn(|slot| battle.sides[side].mons[slot].hp));



    let item_before: [[engine_data::items_table::ItemId; 4]; 2] =
        core::array::from_fn(|side| core::array::from_fn(|slot| battle.sides[side].mons[slot].item));

    let actions: [JointAction; 2] = [parse_choice(&scenario.turns[0].p1), parse_choice(&scenario.turns[0].p2)];
    let hits = step_with_hits(&mut battle, actions);
    let hits: Vec<&HitRecord> = hits.iter().flatten().collect();








    let speed_tied = |side: usize, slot: usize| -> bool {
        let spe = |s: usize, sl: usize| battle.sides[s].mons[battle.sides[s].active[sl] as usize].stats[4];
        let me = spe(side, slot);
        (0..2usize).any(|s| (0..2usize).any(|sl| (s, sl) != (side, slot) && spe(s, sl) == me))
    };






    let ko_disagreement = (0..2usize).any(|s| {
        (0..4usize).any(|sl| {
            let engine_fainted = battle.sides[s].mons[sl].is_fainted();
            let oracle_fainted = mon_hp(after, s, sl) == 0;
            let direct: i64 = hits.iter().filter(|h| h.target.side as usize == s && h.target.slot as usize == sl).map(|h| h.damage_dealt).sum();
            let survived_its_hits = direct > 0 && direct < hp_before[s][sl] as i64;
            engine_fainted != oracle_fainted || (oracle_fainted && survived_its_hits)
        })
    });
    let mut damage_failures = 0;
    for side_i in 0..2usize {
        for slot_i in 0..4usize {
            let target_hits: Vec<&HitRecord> = hits
                .iter()
                .filter(|h| h.target.side as usize == side_i && h.target.slot as usize == slot_i)
                .copied()
                .collect();



            let recoil_hits: Vec<&HitRecord> = hits
                .iter()
                .filter(|h| h.attacker.side as usize == side_i && h.attacker.slot as usize == slot_i)
                .copied()
                .collect();
            let engine_before = hp_before[side_i][slot_i] as i64;
            if ko_disagreement {
                continue;
            }
            let in_tie = |side: usize, slot: usize| battle.sides[side].active[..2].iter().position(|&a| a as usize == slot).is_some_and(|s| speed_tied(side, s));
            if in_tie(side_i, slot_i)
                || target_hits.iter().any(|h| in_tie(h.attacker.side as usize, h.attacker.slot as usize))
                || recoil_hits.iter().any(|h| in_tie(h.target.side as usize, h.target.slot as usize))
            {
                continue;
            }



            if target_hits.iter().any(|h| {
                let (s, sl) = (h.attacker.side as usize, h.attacker.slot as usize);
                battle.sides[s].mons[sl].is_fainted() != (mon_hp(after, s, sl) == 0)
            }) {
                continue;
            }




            let sash_consumed = item_before[side_i][slot_i] == engine_data::items_table::item_ids::FOCUSSASH
                && battle.sides[side_i].mons[slot_i].item != engine_data::items_table::item_ids::FOCUSSASH


                && battle.sides[side_i].mons[slot_i].hp == 1;






            let direct_dmg_engine: i64 = if sash_consumed {
                engine_before - 1
            } else {
                (target_hits.iter().map(|h| h.damage_dealt).sum::<i64>() + realized_recoil(&recoil_hits) + realized_contact_punish(&recoil_hits)
                    - realized_drain(&recoil_hits))
                .min(engine_before)
            };
            let engine_after = battle.sides[side_i].mons[slot_i].hp as i64;
            let oracle_before = mon_hp(before, side_i, slot_i);
            let oracle_after = mon_hp(after, side_i, slot_i);














            if !sash_consumed && battle.sides[side_i].mons[slot_i].is_fainted() != (oracle_after == 0) {
                continue;
            }








            if item_before[side_i][slot_i] == engine_data::items_table::item_ids::SITRUSBERRY && target_hits.len() >= 2 {
                continue;
            }
            if item_before[side_i][slot_i] == engine_data::items_table::item_ids::SITRUSBERRY && !target_hits.is_empty() {
                let half = battle.sides[side_i].mons[slot_i].max_hp as i64 / 2;
                let dmg = combined_possible_damage(&target_hits);
                if let (Some(&least), Some(&most)) = (dmg.iter().min(), dmg.iter().max()) {
                    let (highest_hp, lowest_hp) = (engine_before - least, engine_before - most);
                    if highest_hp > half && lowest_hp <= half {
                        continue;
                    }
                }
            }



            if recoil_hits.iter().any(|h| (moves_table::get(h.move_id).recoil.is_some() || moves_table::get(h.move_id).drain.is_some()) && battle.sides[h.target.side as usize].mons[h.target.slot as usize].is_fainted()) {
                continue;
            }


            if engine_after == 0 && oracle_after == 0 {
                continue;
            }
            let residual_engine = engine_before - direct_dmg_engine - engine_after;
            let oracle_delta = oracle_before - oracle_after;
            let adjusted = oracle_delta - residual_engine;





            let possible: Vec<i64> = if sash_consumed {
                vec![engine_before - 1]
            } else {
                let hit_range = combined_possible_damage(&target_hits);
                let recoil_range = combined_possible_recoil(&recoil_hits);
                let contact_punish = realized_contact_punish(&recoil_hits);


                let drain_range = combined_possible_drain(&recoil_hits);
                hit_range
                    .iter()
                    .flat_map(|&h| recoil_range.iter().map(move |&r| (h + r + contact_punish).min(engine_before)))
                    .flat_map(|v| drain_range.iter().map(move |&d| v - d))
                    .collect()
            };
            if !possible.contains(&adjusted) {
                damage_failures += 1;
                messages.push(format!(
                    "FAIL hp p{} slot{}: oracle delta={oracle_delta} (residual {residual_engine} + \
                     adjusted {adjusted}) not in combined range {possible:?} ({} direct hit(s))",
                    side_i + 1, slot_i, target_hits.len()
                ));
            }
        }
    }





    let mut exact_failures = 0;
    for side_i in 0..2usize {
        for slot_i in 0..4usize {

            if ko_disagreement {
                continue;
            }
            let our_mon = &battle.sides[side_i].mons[slot_i];









            let we_think_fainted = our_mon.is_fainted();
            let oracle_thinks_fainted = mon_hp(after, side_i, slot_i) == 0;
            if we_think_fainted != oracle_thinks_fainted {
                continue;
            }

            let our_boosts = [
                our_mon.boosts[0] as i64, our_mon.boosts[1] as i64, our_mon.boosts[2] as i64,
                our_mon.boosts[3] as i64, our_mon.boosts[4] as i64,
            ];
            let oracle_boosts = mon_boosts(after, side_i, slot_i);
            if our_boosts != oracle_boosts {
                exact_failures += 1;
                messages.push(format!("FAIL boosts p{} slot{}: ours={our_boosts:?} oracle={oracle_boosts:?}", side_i + 1, slot_i));
            }






            let oracle_status = mon_status(after, side_i, slot_i);
            let our_status = status_to_id(our_mon.status);
            if oracle_status != "fnt" && our_status != oracle_status {
                exact_failures += 1;
                messages.push(format!("FAIL status p{} slot{}: ours={our_status:?} oracle={oracle_status:?}", side_i + 1, slot_i));
            }
        }
    }

    let our_weather = weather_to_id(battle.field.weather);
    let oracle_weather = field_weather(after);


    if !ko_disagreement && our_weather != oracle_weather {
        exact_failures += 1;
        messages.push(format!("FAIL weather: ours={our_weather:?} oracle={oracle_weather:?}"));
    }
    let our_terrain = terrain_to_id(battle.field.terrain);
    let oracle_terrain = field_terrain(after);
    if !ko_disagreement && our_terrain != oracle_terrain {
        exact_failures += 1;
        messages.push(format!("FAIL terrain: ours={our_terrain:?} oracle={oracle_terrain:?}"));
    }
    let our_trick_room = battle.field.trick_room_turns > 0;
    let oracle_trick_room = field_has_pseudo_weather(after, "trickroom");
    if !ko_disagreement && our_trick_room != oracle_trick_room {
        exact_failures += 1;
        messages.push(format!("FAIL trick room: ours={our_trick_room} oracle={oracle_trick_room}"));
    }

    for side_i in 0..2usize {
        if ko_disagreement {
            break;
        }
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
            let theirs = side_has_condition(after, side_i, id);
            if ours != theirs {
                exact_failures += 1;
                messages.push(format!("FAIL side{} condition {id}: ours={ours} oracle={theirs}", side_i + 1));
            }
        }
        for (id, ours) in [("spikes", conds.spikes), ("toxicspikes", conds.toxic_spikes)] {
            let theirs = side_condition_layers(after, side_i, id);
            if ours as i64 != theirs {
                exact_failures += 1;
                messages.push(format!("FAIL side{} layers {id}: ours={ours} oracle={theirs}", side_i + 1));
            }
        }
    }

    ComparisonReport { stat_failures, damage_failures, exact_failures, messages }
}
