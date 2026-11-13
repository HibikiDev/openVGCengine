






use crate::stack::StackVec;
use crate::action::Actor;
use crate::battle::Battle;
use crate::field::Weather;
use crate::stats::Stat;
use crate::turn::{boost_actor, boost_actor_drawn, mon_at, mon_at_mut};
use engine_data::abilities_table::{ability_ids, AbilityId};
use engine_data::items_table::item_ids;
use engine_data::type_chart::Type;



pub fn on_start(battle: &mut Battle, actor: Actor) {
    if mon_at(battle, actor).ability == ability_ids::IMPOSTER {
        return;
    }

    if crate::turn::ngas_active(battle, None) && crate::turn::ngas_suppressible(battle, actor) {
        crate::turn::ngas_suppress(battle, actor);
        return;
    }


    if mon_at(battle, actor).ability == ability_ids::COMMANDER {
        crate::turn::commander_check(battle, actor);
        return;
    }

    if mon_at(battle, actor).ability == ability_ids::COSTAR {
        crate::turn::costar(battle, actor);
        return;
    }
    on_switch_in(battle, actor);
}





pub fn on_switch_in(battle: &mut Battle, actor: Actor) {
    let ability = mon_at(battle, actor).ability;
    match ability {

        ability_ids::IMPOSTER => {
            crate::turn::transform_into(battle, actor, Actor { side: actor.other_side(), slot: 1 - actor.slot });
        }


        ability_ids::FORECAST | ability_ids::FLOWERGIFT => crate::turn::forecast_formes(battle, None),
        ability_ids::CLOUDNINE | ability_ids::AIRLOCK => crate::turn::weather_formes(battle, None),

        ability_ids::GORILLATACTICS => {
            mon_at_mut(battle, actor).volatiles.conds.remove(crate::mon::condition_ids::GORILLATACTICS);
        }

        ability_ids::PASTELVEIL => crate::turn::pastel_veil_cures(battle),


        ability_ids::SHIELDSDOWN => {
            let rules = battle.rules();
            crate::turn::shields_down_forme(rules, crate::turn::mon_at_mut(battle, actor));
        }
        ability_ids::SCHOOLING => {
            let rules = battle.rules();
            crate::turn::schooling_forme(rules, crate::turn::mon_at_mut(battle, actor));
        }
        ability_ids::SCREENCLEANER => {
            for side in battle.sides.iter_mut() {
                let c = &mut side.side_conditions;
                (c.reflect_turns, c.light_screen_turns, c.aurora_veil_turns) = (0, 0, 0);
            }
        }

        ability_ids::SUPREMEOVERLORD => {
            let fallen = battle.sides[actor.side as usize].total_fainted().min(5) as u64;
            let m = crate::turn::mon_at_mut(battle, actor);
            m.flags.0 = (m.flags.0 & !crate::mon::mon_flags::FALLEN_MASK) | fallen << crate::mon::mon_flags::FALLEN_SHIFT;
        }

        ability_ids::DESOLATELAND => set_strong_weather(battle, actor, Weather::DesolateLand),
        ability_ids::PRIMORDIALSEA => set_strong_weather(battle, actor, Weather::PrimordialSea),
        ability_ids::DELTASTREAM => set_strong_weather(battle, actor, Weather::DeltaStream),


        ability_ids::DRIZZLE => {
            let m = mon_at(battle, actor);
            if !(m.species == engine_data::species_table::species_ids::KYOGRE && m.item == item_ids::BLUEORB) {
                set_weather(battle, actor, Weather::Rain, item_ids::DAMPROCK);
            }
        }
        ability_ids::DROUGHT => {
            let m = mon_at(battle, actor);
            if !(m.species == engine_data::species_table::species_ids::GROUDON && m.item == item_ids::REDORB) {
                set_weather(battle, actor, Weather::Sun, item_ids::HEATROCK);
            }
        }
        ability_ids::SANDSTREAM => set_weather(battle, actor, Weather::Sand, item_ids::SMOOTHROCK),

        ability_ids::SNOWWARNING => set_weather(battle, actor, battle.rules().abilities.snow_warning, item_ids::ICYROCK),
        ability_ids::INTIMIDATE => intimidate(battle, actor),



        ability_ids::DOWNLOAD => {
            let (mut def, mut spd) = (0u32, 0u32);
            for slot in 0..2u8 {
                let foe = mon_at(battle, Actor { side: actor.other_side(), slot });
                if foe.is_fainted() {
                    continue;
                }
                let read = |stat: Stat| {
                    crate::boosts::apply_boost(foe.stats[stat as usize] as u32, foe.boosts[crate::turn::room_stat(foe, stat) as usize])
                };
                def += read(Stat::Def);
                spd += read(Stat::SpD);
            }
            if def > 0 && def >= spd {
                boost_here(battle, actor, [0, 0, 1, 0, 0, 0, 0]);
            } else if spd > 0 {
                boost_here(battle, actor, [1, 0, 0, 0, 0, 0, 0]);
            }
        }

        ability_ids::SLOWSTART => mon_at_mut(battle, actor).volatiles.conds.set(crate::mon::condition_ids::SLOWSTART, 5),


        ability_ids::UNNERVE | ability_ids::ASONEGLASTRIER | ability_ids::ASONESPECTRIER => {
            mon_at_mut(battle, actor).flags.set(crate::mon::mon_flags::UNNERVED);
        }


        ability_ids::EMBODYASPECTTEAL | ability_ids::EMBODYASPECTHEARTHFLAME | ability_ids::EMBODYASPECTWELLSPRING | ability_ids::EMBODYASPECTCORNERSTONE => {
            use engine_data::species_table::species_ids::*;
            let m = mon_at(battle, actor);
            let boost = match (ability, crate::items::pre_transform_species(m)) {
                (ability_ids::EMBODYASPECTTEAL, OGERPONTEALTERA) => [0, 0, 0, 0, 1, 0, 0],
                (ability_ids::EMBODYASPECTHEARTHFLAME, OGERPONHEARTHFLAMETERA) => [1, 0, 0, 0, 0, 0, 0],
                (ability_ids::EMBODYASPECTWELLSPRING, OGERPONWELLSPRINGTERA) => [0, 0, 0, 1, 0, 0, 0],
                (ability_ids::EMBODYASPECTCORNERSTONE, OGERPONCORNERSTONETERA) => [0, 1, 0, 0, 0, 0, 0],
                _ => [0; 7],
            };
            if m.tera.active && boost != [0; 7] {
                boost_here(battle, actor, boost);
            }
        }

        ability_ids::INTREPIDSWORD
            if battle.rules().abilities.sword_shield_every_switch_in || !mon_at(battle, actor).flags.has(crate::mon::mon_flags::SWORD_BOOST) =>
        {
            mon_at_mut(battle, actor).flags.set(crate::mon::mon_flags::SWORD_BOOST);
            boost_here(battle, actor, [1, 0, 0, 0, 0, 0, 0]);
        }
        ability_ids::DAUNTLESSSHIELD
            if battle.rules().abilities.sword_shield_every_switch_in || !mon_at(battle, actor).flags.has(crate::mon::mon_flags::SHIELD_BOOST) =>
        {
            mon_at_mut(battle, actor).flags.set(crate::mon::mon_flags::SHIELD_BOOST);
            boost_here(battle, actor, [0, 1, 0, 0, 0, 0, 0]);
        }


        ability_ids::TRUANT => {
            let m = mon_at_mut(battle, actor);
            m.volatiles.conds.remove(crate::mon::condition_ids::TRUANT);
            if m.turns_active > 0
                && (m.move_result_this_turn != crate::mon::move_result::NONE || m.volatiles.has(crate::mon::volatile_flags::ACTED_THIS_TURN))
            {
                m.volatiles.conds.add(crate::mon::condition_ids::TRUANT, 0);
            }
        }
        ability_ids::ELECTRICSURGE => set_terrain_here(battle, actor, crate::field::Terrain::Electric),

        ability_ids::HADRONENGINE => set_terrain_here(battle, actor, crate::field::Terrain::Electric),
        ability_ids::ORICHALCUMPULSE => set_weather(battle, actor, Weather::Sun, item_ids::HEATROCK),
        ability_ids::GRASSYSURGE => set_terrain_here(battle, actor, crate::field::Terrain::Grassy),
        ability_ids::PSYCHICSURGE => set_terrain_here(battle, actor, crate::field::Terrain::Psychic),
        ability_ids::MISTYSURGE => set_terrain_here(battle, actor, crate::field::Terrain::Misty),
        ability_ids::HOSPITALITY => heal_ally_on_switch_in(battle, actor),


        ability_ids::TRACE if crate::turn::has_ability_shield(mon_at(battle, actor)) => {
            mon_at_mut(battle, actor).flags.clear(crate::mon::mon_flags::TRACE_SEEK);
        }
        ability_ids::TRACE => {
            mon_at_mut(battle, actor).flags.set(crate::mon::mon_flags::TRACE_SEEK);
            trace_ability(battle, actor)
        }


        ability_ids::SUPERSWEETSYRUP => {
            if mon_at(battle, actor).flags.has(crate::mon::mon_flags::SYRUP_TRIGGERED) {
                return;
            }
            mon_at_mut(battle, actor).flags.set(crate::mon::mon_flags::SYRUP_TRIGGERED);
            for slot in 0..2u8 {
                let foe = Actor { side: actor.other_side(), slot };
                if mon_at(battle, foe).is_fainted() || mon_at(battle, foe).sub_hp > 0 {
                    continue;
                }

                let mut rng = battle.rng;
                let deltas = block_external_boosts(battle, actor, foe, [0, 0, 0, 0, 0, 0, -1], &mut rng);
                let before = mon_at(battle, foe).boosts;
                boost_actor_drawn(battle, foe, deltas, &mut rng);
                react_to_lowered_since(battle, actor, foe, before, &mut rng);
                battle.rng = rng;
            }
        }

        ability_ids::CURIOUSMEDICINE => {
            let ally = Actor { side: actor.side, slot: 1 - actor.slot };
            if !mon_at(battle, ally).is_fainted() {
                mon_at_mut(battle, ally).boosts = [0; 7];
            }
        }
        ability_ids::FOREWARN => forewarn(battle, actor),


        ability_ids::FRISK if battle.rules().abilities.frisk_one_random_foe => {
            let mut rng = battle.rng;
            let _ = crate::turn::random_living_foe(battle, actor, &mut rng);
            battle.rng = rng;
        }

        ability_ids::MIMICRY => crate::turn::mimicry(battle, actor),
        _ => {}
    }
}




fn forewarn(battle: &mut Battle, actor: Actor) {
    use engine_data::moves_table::{move_ids, Category};
    let (mut best, mut count) = (1u16, 0u32);
    for slot in 0..2u8 {
        let foe = mon_at(battle, Actor { side: actor.other_side(), slot });
        if foe.is_fainted() {
            continue;
        }
        for &id in foe.moves.iter().filter(|&&id| id != crate::ids::NONE_ID) {
            let data = battle.move_data(id);
            let bp = if matches!(id, move_ids::FISSURE | move_ids::SHEERCOLD | move_ids::GUILLOTINE | move_ids::HORNDRILL) {
                150
            } else if matches!(id, move_ids::COUNTER | move_ids::MIRRORCOAT | move_ids::METALBURST) {
                120
            } else if data.base_power == 1 || (data.base_power == 0 && data.category != Category::Status) {
                80
            } else {
                data.base_power
            };
            if bp > best {
                (best, count) = (bp, 1);
            } else if bp == best {
                count += 1;
            }
        }
    }
    if count > 0 {
        let mut rng = battle.rng;
        rng.random(count);
        battle.rng = rng;
    }
}











fn trace_has_target(battle: &Battle, actor: Actor) -> bool {
    (0..2u8).map(|slot| mon_at(battle, Actor { side: actor.other_side(), slot })).any(|m| {
        !m.is_fainted() && !untraceable(battle.rules(), crate::turn::real_ability(m))
    })
}

fn trace_ability(battle: &mut Battle, actor: Actor) {
    let foe0 = Actor { side: actor.other_side(), slot: 0 };
    let foe1 = Actor { side: actor.other_side(), slot: 1 };


    let candidates: StackVec<AbilityId, 16> = [foe0, foe1]
        .into_iter()
        .map(|a| *mon_at(battle, a))
        .filter(|m| !m.is_fainted() && !untraceable(battle.rules(), crate::turn::real_ability(m)))
        .map(|m| crate::turn::real_ability(&m))
        .collect();
    if candidates.is_empty() {
        return;
    }
    let mut rng = battle.rng;
    let traced = candidates[rng.random(candidates.len() as u32) as usize];
    battle.rng = rng;


    if battle.rules().ability_has_flag(traced, engine_data::abilities_table::ability_flags::CANTSUPPRESS) {
        return;
    }

    if crate::turn::has_ability_shield(mon_at(battle, actor)) {
        return;
    }


    mon_at_mut(battle, actor).flags.clear(crate::mon::mon_flags::TRACE_SEEK);
    mon_at_mut(battle, actor).ability = traced;
    crate::turn::stamp_ability_order(battle, actor);

    on_switch_in(battle, actor);
}







pub fn trace_seek(battle: &mut Battle) {
    let seeking = |battle: &Battle, a: Actor| {
        !mon_at(battle, a).is_fainted() && mon_at(battle, a).ability == ability_ids::TRACE && mon_at(battle, a).flags.has(crate::mon::mon_flags::TRACE_SEEK)
    };
    let mut seekers: StackVec<(Actor, i64), 32> = [(0, 0), (0, 1), (1, 0), (1, 1)]
        .into_iter()
        .map(|(side, slot)| Actor { side, slot })
        .filter(|&a| seeking(battle, a))
        .map(|a| (a, mon_at(battle, a).speed_cache))
        .collect();
    if seekers.len() > 1 && seekers.iter().any(|&(a, _)| trace_has_target(battle, a)) {
        let mut order: StackVec<(Actor, crate::action::Action, i8, i64), 32> = crate::turn::all_actors()
            .into_iter()
            .filter(|&a| !mon_at(battle, a).is_fainted())
            .map(|a| (a, crate::action::Action::Pass, 0, mon_at(battle, a).speed_cache))
            .collect();
        let mut rng = battle.rng;
        crate::turn::speed_sort(&mut order, &mut rng);
        battle.rng = rng;
        seekers = order.iter().filter(|e| seeking(battle, e.0)).map(|e| (e.0, e.3)).collect();
    } else {
        seekers.sort_by_key(|&(_, speed)| std::cmp::Reverse(speed));
    }
    for (actor, _) in seekers {
        if !mon_at(battle, actor).is_fainted() && mon_at(battle, actor).ability == ability_ids::TRACE {
            trace_ability(battle, actor);
        }
    }
}






pub fn status_ability_cures(battle: &mut Battle) {
    use crate::status::Status;
    for a in crate::turn::all_actors() {
        let m = mon_at_mut(battle, a);
        if m.is_fainted() {
            continue;
        }
        let cures = match m.ability {
            ability_ids::LIMBER => m.status == Status::Paralysis,
            ability_ids::INSOMNIA | ability_ids::VITALSPIRIT => m.status == Status::Sleep,
            ability_ids::WATERVEIL | ability_ids::WATERBUBBLE | ability_ids::THERMALEXCHANGE => m.status == Status::Burn,
            ability_ids::IMMUNITY => matches!(m.status, Status::Poison | Status::Toxic),
            ability_ids::MAGMAARMOR => m.status == Status::Freeze,
            _ => false,
        };
        if cures {
            m.status = Status::None;
            m.status_counter = 0;
        }
    }
}


fn untraceable(rules: &crate::rules::Rules, ability: AbilityId) -> bool {
    rules.ability_has_flag(ability, engine_data::abilities_table::ability_flags::NOTRACE)
}





fn heal_ally_on_switch_in(battle: &mut Battle, actor: Actor) {
    let ally = Actor { side: actor.side, slot: 1 - actor.slot };
    if mon_at(battle, ally).is_fainted() {
        return;
    }
    let ally_max_hp = mon_at(battle, ally).base_max_hp;
    crate::turn::apply_heal(mon_at_mut(battle, ally), (ally_max_hp / 4).max(1));
}











pub fn on_damaging_hit(battle: &mut Battle, target: Actor, attacker: Actor, move_type: Type, category: engine_data::moves_table::Category, struggle: bool, attacker_down: bool, rng: &mut crate::rng::Rng) {





    if mon_at(battle, target).ability == ability_ids::CURSEDBODY && mon_at(battle, attacker).disable_turns == 0 && !struggle && rng.chance(3, 10) {


        if !aroma_veil_blocks(battle, target, attacker) && !attacker_down {
            crate::turn::apply_disable(battle, attacker, true);
        }
    }


    let alive = !mon_at(battle, target).is_fainted();

    if mon_at(battle, target).ability == ability_ids::SANDSPIT {
        set_weather(battle, target, Weather::Sand, item_ids::SMOOTHROCK);
    }
    if alive
        && mon_at(battle, target).ability == ability_ids::RATTLED
        && matches!(move_type, Type::Dark | Type::Bug | Type::Ghost)
    {
        boost_actor_drawn(battle, target, [0, 0, 0, 0, 1, 0, 0], rng);
    }




    if alive && mon_at(battle, target).ability == ability_ids::STAMINA {
        boost_actor_drawn(battle, target, [0, 1, 0, 0, 0, 0, 0], rng);
    }

    if alive && mon_at(battle, target).ability == ability_ids::WATERCOMPACTION && move_type == Type::Water {
        boost_actor_drawn(battle, target, [0, 2, 0, 0, 0, 0, 0], rng);
    }

    if alive && mon_at(battle, target).ability == ability_ids::STEAMENGINE && matches!(move_type, Type::Water | Type::Fire) {
        boost_actor_drawn(battle, target, [0, 0, 0, 0, 6, 0, 0], rng);
    }





    if alive && mon_at(battle, target).ability == ability_ids::THERMALEXCHANGE && move_type == Type::Fire && !crate::turn::breaks_molds_vs(battle, attacker, target) {
        boost_actor_drawn(battle, target, [1, 0, 0, 0, 0, 0, 0], rng);
    }


    if alive && mon_at(battle, target).ability == ability_ids::JUSTIFIED && move_type == Type::Dark {
        boost_actor_drawn(battle, target, [1, 0, 0, 0, 0, 0, 0], rng);
    }








    if alive && mon_at(battle, target).ability == ability_ids::WEAKARMOR && category == engine_data::moves_table::Category::Physical {
        boost_actor_drawn(battle, target, [0, -1, 0, 0, battle.rules().abilities.weak_armor_speed, 0, 0], rng);
    }

    if mon_at(battle, target).ability == ability_ids::SEEDSOWER {
        set_terrain(battle, target, crate::field::Terrain::Grassy, rng);
    }

    if alive && mon_at(battle, target).ability == ability_ids::ELECTROMORPHOSIS && !mon_at(battle, target).volatiles.has(crate::mon::volatile_flags::CHARGE) {
        mon_at_mut(battle, target).volatiles.set(crate::mon::volatile_flags::CHARGE);
    }
}









pub fn synchronize_reaction(battle: &mut Battle, actor: Actor, target: Actor, attempted: crate::status::Status, rng: &mut crate::rng::Rng) {
    use crate::status::Status;
    if target == actor || mon_at(battle, target).status != attempted {
        return;
    }
    if matches!(attempted, Status::Sleep | Status::Freeze) {
        return;
    }
    if mon_at(battle, target).ability != ability_ids::SYNCHRONIZE {
        return;
    }




    crate::turn::try_set_status(battle, target, actor, attempted, rng);
}










pub fn contact_status_proc(battle: &mut Battle, attacker: Actor, defender: Actor, contact: bool, rng: &mut crate::rng::Rng) {



    if mon_at(battle, defender).ability == ability_ids::EFFECTSPORE {
        let a = mon_at(battle, attacker);


        let powder_immune = (battle.rules().modern_type_immunities && (a.types.contains(&Some(Type::Grass)) || a.ability == ability_ids::OVERCOAT))
            || a.effective_item() == engine_data::items_table::item_ids::SAFETYGOGGLES;



        let down = battle.rules().instafaint_punish && a.is_fainted();
        if contact && !powder_immune && !down {
            let status = match rng.random(100) {
                0..11 => crate::status::Status::Sleep,
                11..21 => crate::status::Status::Paralysis,
                21..30 => crate::status::Status::Poison,
                _ => return,
            };
            let before = mon_at(battle, attacker).status;
            crate::turn::try_set_status_drawn(battle, defender, attacker, status, rng);
            synchronize_new_status(battle, defender, attacker, before, status, rng);
        }
        return;
    }


    if mon_at(battle, defender).ability == ability_ids::CUTECHARM {
        if contact && rng.chance(3, 10) {
            crate::turn::try_attract(battle, attacker, defender);
        }
        return;
    }
    let status = match mon_at(battle, defender).ability {
        ability_ids::FLAMEBODY => crate::status::Status::Burn,
        ability_ids::STATIC => crate::status::Status::Paralysis,
        ability_ids::POISONPOINT => crate::status::Status::Poison,
        _ => return,
    };
    if contact && rng.chance(3, 10) {
        let before = mon_at(battle, attacker).status;
        crate::turn::try_set_status(battle, defender, attacker, status, rng);
        synchronize_new_status(battle, defender, attacker, before, status, rng);
    }
}




fn synchronize_new_status(battle: &mut Battle, source: Actor, target: Actor, before: crate::status::Status, status: crate::status::Status, rng: &mut crate::rng::Rng) {
    if before == crate::status::Status::None {
        synchronize_reaction(battle, source, target, status, rng);
    }
}





pub const INFORMATION_ONLY_ABILITIES: [AbilityId; 5] =
    [ability_ids::FRISK, ability_ids::ILLUSION, ability_ids::PRESSURE, ability_ids::ANTICIPATION, ability_ids::GLUTTONY];









pub fn poison_touch_proc(battle: &mut Battle, attacker: Actor, defender: Actor, contact: bool, attacker_ability: AbilityId, rng: &mut crate::rng::Rng) {
    if crate::turn::mon_at(battle, defender).ability == ability_ids::SHIELDDUST || mon_at(battle, defender).effective_item() == item_ids::COVERTCLOAK {
        return;
    }
    if contact && attacker_ability == ability_ids::POISONTOUCH && rng.chance(3, 10) {
        let before = mon_at(battle, defender).status;
        crate::turn::try_set_status(battle, attacker, defender, crate::status::Status::Poison, rng);
        synchronize_new_status(battle, attacker, defender, before, crate::status::Status::Poison, rng);
    }

    if attacker_ability == ability_ids::TOXICCHAIN && rng.chance(3, 10) {
        let before = mon_at(battle, defender).status;
        crate::turn::try_set_status(battle, attacker, defender, crate::status::Status::Toxic, rng);
        synchronize_new_status(battle, attacker, defender, before, crate::status::Status::Toxic, rng);
    }
}








pub fn toxic_debris_proc(battle: &mut Battle, target: Actor, category: engine_data::moves_table::Category) {
    if mon_at(battle, target).ability != ability_ids::TOXICDEBRIS || category != engine_data::moves_table::Category::Physical {
        return;
    }
    crate::turn::add_toxic_spikes(battle, target.other_side() as usize);
}









pub fn check_emergency_exit(battle: &mut Battle, target: Actor, hp_before_hit: u16) {
    let m = mon_at(battle, target);
    check_emergency_exit_at(battle, target, hp_before_hit as u32, m.hp as u32, m.max_hp as u32);
}



pub fn check_emergency_exit_residual(battle: &mut Battle, target: Actor, hp_before: u16) {
    let m = mon_at(battle, target);
    let (before, now) = (crate::turn::undynamaxed_hp(m, hp_before), crate::turn::undynamaxed_hp(m, m.hp));
    let max = if crate::turn::is_dynamaxed(m) { m.base_max_hp } else { m.max_hp };


    if check_emergency_exit_at(battle, target, before as u32, now as u32, max as u32) && battle.rules().abilities.emergency_exit_clears_switches {
        battle.field.faint_switches_held = true;
    }
}


fn check_emergency_exit_at(battle: &mut Battle, target: Actor, hp_before_hit: u32, hp_after_hit: u32, max_hp: u32) -> bool {


    if !matches!(mon_at(battle, target).ability, ability_ids::EMERGENCYEXIT | ability_ids::WIMPOUT) || mon_at(battle, target).flags.has(crate::mon::mon_flags::RED_CARD_DRAG) {
        return false;
    }
    if hp_after_hit * 2 <= max_hp && hp_before_hit * 2 > max_hp {



        let goes_off = !mon_at(battle, target).is_fainted()
            && !mon_at(battle, target).volatiles.has(crate::mon::volatile_flags::VOLUNTARY_SWITCH)
            && crate::turn::has_switch_in_available(&battle.sides[target.side as usize]);
        if goes_off && battle.rules().abilities.emergency_exit_clears_switches {
            use crate::mon::volatile_flags::{BATON_PASS, SELF_SWITCH, VOLUNTARY_SWITCH};
            for a in crate::turn::all_actors() {
                mon_at_mut(battle, a).volatiles.clear(VOLUNTARY_SWITCH | SELF_SWITCH | BATON_PASS);
            }
        }
        crate::turn::request_voluntary_switch(battle, target, false);
        return goes_off;
    }
    false
}









pub(crate) fn aroma_veil_blocks(battle: &Battle, source: Actor, target: Actor) -> bool {
    self_or_ally_unbroken(battle, target, ability_ids::AROMAVEIL, source != target && crate::turn::breaks_molds_mon(mon_at(battle, source)))
}



pub(crate) fn self_or_ally_unbroken(battle: &Battle, actor: Actor, ability: AbilityId, breaker: bool) -> bool {
    let ally = mon_at(battle, Actor { side: actor.side, slot: 1 - actor.slot });
    let held = |m: &crate::mon::Mon| m.ability == ability && !(breaker && !crate::turn::has_ability_shield(m));
    held(mon_at(battle, actor)) || (!ally.is_fainted() && held(ally))
}

pub(crate) fn self_or_ally_has_ability(battle: &Battle, actor: Actor, ability: AbilityId) -> bool {

    let ally = mon_at(battle, Actor { side: actor.side, slot: 1 - actor.slot });
    mon_at(battle, actor).ability == ability || (!ally.is_fainted() && ally.ability == ability)
}




















pub fn block_external_boosts(battle: &mut Battle, source: Actor, target: Actor, deltas: [i8; 7], rng: &mut crate::rng::Rng) -> [i8; 7] {

    let raw_breaker = source != target && crate::turn::breaks_molds_mon(mon_at(battle, source));
    let breaker = raw_breaker && !crate::turn::has_ability_shield(mon_at(battle, target));


    let infiltrated = source.side != target.side && mon_at(battle, source).ability == ability_ids::INFILTRATOR;




    let contrary = !breaker && mon_at(battle, target).ability == ability_ids::CONTRARY;
    let deltas = if contrary { deltas.map(|d| -d) } else { deltas };


    let deltas = if source != target && mon_at(battle, target).effective_item() == item_ids::CLEARAMULET {
        deltas.map(|d| d.max(0))
    } else {
        deltas
    };



    let mist = source != target && battle.sides[target.side as usize].side_conditions.mist_turns > 0 && !infiltrated;
    let armor_first = !breaker && mon_at(battle, target).ability == ability_ids::MIRRORARMOR && mon_at(battle, target).speed_cache >= 0;
    let deltas = if mist && !armor_first { deltas.map(|d| d.max(0)) } else { deltas };

    let guard = boost_guard_ability(battle, target);
    let guard_broken = breaker && battle.rules().ability_has_flag(guard, engine_data::abilities_table::ability_flags::BREAKABLE);
    let mut deltas = block_external_negative_boosts(if guard_broken { crate::ids::NONE_ID } else { guard }, deltas);
    if mon_at(battle, target).types.contains(&Some(Type::Grass)) && self_or_ally_unbroken(battle, target, ability_ids::FLOWERVEIL, raw_breaker) {
        deltas = deltas.map(|d| d.max(0));
    }
    if !breaker && mon_at(battle, target).ability == ability_ids::MIRRORARMOR {
        let target_boosts = mon_at(battle, target).boosts;
        let mut redirected = [0i8; 7];
        for i in 0..7 {
            if deltas[i] < 0 && target_boosts[i] != -6 {
                redirected[i] = deltas[i];
                deltas[i] = 0;
            }
        }





        for i in 0..7 {
            if redirected[i] == 0 || mon_at(battle, source).is_fainted() {
                continue;
            }
            let mut single = [0i8; 7];
            single[i] = redirected[i];
            let single = reflected_drop_blocks(battle, source, single);
            let before = mon_at(battle, source).boosts;
            boost_actor_drawn(battle, source, single, rng);
            react_to_lowered_since(battle, target, source, before, rng);
        }
    }

    let mut deltas = if mist && armor_first { deltas.map(|d| d.max(0)) } else { deltas };

    if breaker && mon_at(battle, target).ability == ability_ids::CONTRARY {
        deltas = deltas.map(|d| -d);
    }
    if contrary {
        deltas = deltas.map(|d| -d);
    }
    deltas
}










pub fn contact_punish(battle: &mut Battle, attacker: Actor, defender: Actor, contact: bool, rng: &mut crate::rng::Rng) -> i64 {
    if !contact {
        return 0;
    }

    let ties = |battle: &Battle, rng: &mut crate::rng::Rng| {
        if mon_at(battle, attacker).hp > 0 {
            crate::turn::damage_event_ties(battle, attacker, rng);
        }
    };


    let magic_guard = mon_at(battle, attacker).ability == ability_ids::MAGICGUARD;
    let max_hp = mon_at(battle, attacker).base_max_hp;
    match mon_at(battle, defender).ability {
        ability_ids::ROUGHSKIN | ability_ids::IRONBARBS => {
            ties(battle, rng);
            if magic_guard {
                return 0;
            }
            crate::turn::focus_band_roll_at(battle, attacker, rng);
            let dealt = crate::turn::apply_damage_at(battle, attacker, (max_hp / 8).max(1)) as i64;
            crate::turn::instafaint(battle, attacker);
            dealt
        }



        ability_ids::AFTERMATH if mon_at(battle, defender).hp == 0 => {
            ties(battle, rng);
            let breaker = crate::turn::breaks_molds_mon(mon_at(battle, attacker));
            let damp = crate::turn::all_actors()
                .into_iter()
                .any(|a| !mon_at(battle, a).is_fainted() && mon_at(battle, a).ability == ability_ids::DAMP && !(breaker && a != attacker && !crate::turn::has_ability_shield(mon_at(battle, a))));
            if damp || magic_guard {
                0
            } else {
                crate::turn::focus_band_roll_at(battle, attacker, rng);
                let dealt = crate::turn::apply_damage_at(battle, attacker, (max_hp / 4).max(1)) as i64;
                crate::turn::instafaint(battle, attacker);
                dealt
            }
        }
        _ => 0,
    }
}



















fn reflected_drop_blocks(battle: &Battle, receiver: Actor, deltas: [i8; 7]) -> [i8; 7] {
    let mut deltas = block_external_negative_boosts(boost_guard_ability(battle, receiver), deltas);
    let flower_veil = mon_at(battle, receiver).types.contains(&Some(Type::Grass)) && self_or_ally_has_ability(battle, receiver, ability_ids::FLOWERVEIL);
    if clear_amulet_blocks(battle, receiver) || flower_veil || battle.sides[receiver.side as usize].side_conditions.mist_turns > 0 {
        deltas = deltas.map(|d| d.max(0));
    }
    deltas
}

fn clear_amulet_blocks(battle: &Battle, mon: Actor) -> bool {
    mon_at(battle, mon).effective_item() == item_ids::CLEARAMULET && mon_at(battle, mon).ability != ability_ids::CONTRARY
}

fn boost_guard_ability(battle: &Battle, mon: Actor) -> AbilityId {
    let ability = mon_at(battle, mon).ability;
    if ability == ability_ids::ILLUMINATE && !battle.rules().abilities.illuminate_active { crate::ids::NONE_ID } else { ability }
}

pub fn block_external_negative_boosts(target_ability: AbilityId, deltas: [i8; 7]) -> [i8; 7] {
    match target_ability {

        ability_ids::CLEARBODY | ability_ids::WHITESMOKE | ability_ids::FULLMETALBODY => deltas.map(|d| d.max(0)),
        ability_ids::HYPERCUTTER => {
            let mut deltas = deltas;
            deltas[Stat::Atk as usize] = deltas[Stat::Atk as usize].max(0);
            deltas
        }

        ability_ids::BIGPECKS => {
            let mut deltas = deltas;
            deltas[Stat::Def as usize] = deltas[Stat::Def as usize].max(0);
            deltas
        }




        ability_ids::KEENEYE | ability_ids::ILLUMINATE | ability_ids::MINDSEYE => {
            let mut deltas = deltas;
            deltas[crate::boosts::Boost::Accuracy as usize] = deltas[crate::boosts::Boost::Accuracy as usize].max(0);
            deltas
        }
        _ => deltas,
    }
}








pub(crate) fn set_weather(battle: &mut Battle, actor: Actor, weather: Weather, matching_rock: engine_data::items_table::ItemId) {
    let permanent = battle.rules().permanent_ability_weather;

    if battle.field.weather == weather && (!permanent || battle.field.weather_turns == 0) {
        return;
    }


    let mut rng = battle.rng;
    crate::turn::set_weather_handler_ties(battle, &mut rng);
    battle.rng = rng;
    if battle.field.weather.is_strong() {
        return;
    }
    battle.field.weather = weather;
    battle.field.weather_turns =
        if permanent { 0 } else { crate::turn::weather_duration(mon_at(battle, actor).effective_item(), matching_rock) };
    crate::turn::weather_formes(battle, None);
}




fn set_strong_weather(battle: &mut Battle, actor: Actor, weather: Weather) {
    if battle.field.weather == weather {
        return;
    }
    let mut rng = battle.rng;
    crate::turn::set_weather_handler_ties(battle, &mut rng);
    battle.rng = rng;
    battle.field.weather = weather;
    battle.field.weather_turns = 0;
    battle.field.weather_source = crate::turn::mon_code(battle, actor);
    crate::turn::weather_formes(battle, None);
}
























fn after_boost_ties_here(battle: &mut Battle, who: Actor) {
    let mut rng = battle.rng;
    crate::turn::after_boost_ties(battle, who, &mut rng);
    battle.rng = rng;
}


fn set_terrain_here(battle: &mut Battle, actor: Actor, terrain: crate::field::Terrain) {
    let mut rng = battle.rng;
    set_terrain(battle, actor, terrain, &mut rng);
    battle.rng = rng;
}


fn boost_here(battle: &mut Battle, who: Actor, deltas: [i8; 7]) {
    let mut rng = battle.rng;
    crate::turn::boost_actor_drawn(battle, who, deltas, &mut rng);
    battle.rng = rng;
}




fn intimidate(battle: &mut Battle, actor: Actor) {




    let mut stashed = [crate::ids::NONE_ID; 2];
    if mon_at(battle, actor).flags.has(crate::mon::mon_flags::IGNORES_ABILITIES) {
        for slot in 0..2u8 {
            let foe = Actor { side: actor.other_side(), slot };
            let m = mon_at(battle, foe);
            if !m.is_fainted()
                && !crate::turn::has_ability_shield(m)
                && battle.rules().ability_has_flag(m.ability, engine_data::abilities_table::ability_flags::BREAKABLE)
            {
                stashed[slot as usize] = m.ability;
                mon_at_mut(battle, foe).ability = crate::ids::NONE_ID;
            }
        }
    }
    intimidate_foes(battle, actor);
    for slot in 0..2u8 {
        if stashed[slot as usize] != crate::ids::NONE_ID {
            mon_at_mut(battle, Actor { side: actor.other_side(), slot }).ability = stashed[slot as usize];
        }
    }
}

fn intimidate_foes(battle: &mut Battle, actor: Actor) {
    use ability_ids::{CLEARBODY, COMPETITIVE, DEFIANT, FULLMETALBODY, GUARDDOG, HYPERCUTTER, INNERFOCUS, OBLIVIOUS, OWNTEMPO, RATTLED, SCRAPPY, WHITESMOKE};
    for slot in 0..2u8 {
        let foe = Actor { side: actor.other_side(), slot };

        if mon_at(battle, foe).is_fainted() || mon_at(battle, foe).sub_hp > 0 {
            continue;
        }

        let atk = mon_at(battle, foe).boosts[Stat::Atk as usize];
        let capped = if mon_at(battle, foe).ability == ability_ids::CONTRARY { atk == 6 } else { atk == -6 };


        if clear_amulet_blocks(battle, foe) {
            after_boost_ties_here(battle, foe);
            continue;
        }



        if battle.sides[foe.side as usize].side_conditions.mist_turns > 0 && mon_at(battle, foe).ability != ability_ids::CONTRARY {
            after_boost_ties_here(battle, foe);
            adrenaline_orb(battle, foe, capped);
            continue;
        }









        if mon_at(battle, foe).types.contains(&Some(Type::Grass))
            && self_or_ally_has_ability(battle, foe, ability_ids::FLOWERVEIL)
            && mon_at(battle, foe).ability != ability_ids::CONTRARY
        {
            after_boost_ties_here(battle, foe);
            adrenaline_orb(battle, foe, capped);
            continue;
        }









        if mon_at(battle, foe).ability == ability_ids::MIRRORARMOR {


            if mon_at(battle, foe).boosts[Stat::Atk as usize] != -6 && !mon_at(battle, actor).is_fainted() {
                let before = mon_at(battle, actor).boosts;
                let drop = reflected_drop_blocks(battle, actor, [-1, 0, 0, 0, 0, 0, 0]);
                let mut rng = battle.rng;
                boost_actor_drawn(battle, actor, drop, &mut rng);
                react_to_lowered_since(battle, foe, actor, before, &mut rng);
                battle.rng = rng;
            }

            after_boost_ties_here(battle, foe);
            adrenaline_orb(battle, foe, capped);
            continue;
        }

        let reactions = battle.rules().abilities.intimidate_ability_reactions;
        match mon_at(battle, foe).ability {
            CLEARBODY | WHITESMOKE | FULLMETALBODY | HYPERCUTTER => after_boost_ties_here(battle, foe),
            INNERFOCUS | SCRAPPY | OBLIVIOUS | OWNTEMPO if reactions => after_boost_ties_here(battle, foe),

            GUARDDOG => {
                boost_here(battle, foe, [1, 0, 0, 0, 0, 0, 0]);
                after_boost_ties_here(battle, foe);
            }

            RATTLED if reactions => {
                boost_here(battle, foe, [-1, 0, 0, 0, 0, 0, 0]);
                boost_here(battle, foe, [0, 0, 0, 0, 1, 0, 0]);
            }

            DEFIANT | COMPETITIVE => {
                let before = mon_at(battle, foe).boosts;
                boost_actor(battle, foe, [-1, 0, 0, 0, 0, 0, 0]);

                let mut rng = battle.rng;
                react_to_lowered_since(battle, actor, foe, before, &mut rng);
                battle.rng = rng;
                after_boost_ties_here(battle, foe);
            }
            _ => boost_here(battle, foe, [-1, 0, 0, 0, 0, 0, 0]),
        }
        adrenaline_orb(battle, foe, capped);
    }
}




fn adrenaline_orb(battle: &mut Battle, foe: Actor, capped: bool) {
    let m = mon_at(battle, foe);
    if m.is_fainted() || m.effective_item() != item_ids::ADRENALINEORB || m.boosts[Stat::Spe as usize] == 6 || capped {
        return;
    }

    crate::turn::spend_item(crate::turn::mon_at_mut(battle, foe));
    boost_here(battle, foe, [0, 0, 0, 0, 1, 0, 0]);
}























pub fn react_to_lowered_since(battle: &mut Battle, source: Actor, target: Actor, before: [i8; 7], rng: &mut crate::rng::Rng) {
    let now = mon_at(battle, target).boosts;
    let mut lowered = [0i8; 7];
    for i in 0..7 {
        if now[i] < before[i] {
            lowered[i] = now[i] - before[i];
        }
    }
    react_to_lowered_boost(battle, source, target, lowered, rng);
}

pub fn react_to_lowered_boost(battle: &mut Battle, source: Actor, target: Actor, applied_deltas: [i8; 7], rng: &mut crate::rng::Rng) {
    if source.side == target.side {
        return;
    }
    for _ in 0..applied_deltas.iter().filter(|&&d| d < 0).count() {
        match mon_at(battle, target).ability {
            ability_ids::DEFIANT => boost_actor_drawn(battle, target, [2, 0, 0, 0, 0, 0, 0], rng),
            ability_ids::COMPETITIVE => boost_actor_drawn(battle, target, [0, 0, 2, 0, 0, 0, 0], rng),
            _ => return,
        }
    }
}





pub(crate) fn set_terrain(battle: &mut Battle, actor: Actor, terrain: crate::field::Terrain, rng: &mut crate::rng::Rng) {
    if battle.field.terrain == terrain {
        return;
    }
    battle.field.terrain = terrain;
    battle.field.terrain_turns = crate::turn::terrain_duration(mon_at(battle, actor).effective_item());
    crate::turn::trigger_terrain_seeds(battle, rng);
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::turn::tests::{test_battle, test_mon};
    use engine_data::type_chart::Type;

    fn mon_with_ability(ability: engine_data::abilities_table::AbilityId) -> crate::mon::Mon {
        let mut m = test_mon([Some(Type::Normal), None], [100; 5], [0; 4]);
        m.ability = ability;
        m
    }

    #[test]
    fn drought_sets_sun_on_switch_in() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::DROUGHT), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.weather, Weather::Sun);
        assert_eq!(battle.field.weather_turns, 5);
    }

    #[test]
    fn drought_lasts_eight_turns_with_a_heat_rock() {
        let mut holder = mon_with_ability(ability_ids::DROUGHT);
        holder.item = item_ids::HEATROCK;
        let mut battle = test_battle(
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.weather_turns, 8);
    }

    #[test]
    fn drought_ignores_a_mismatched_rock() {
        let mut holder = mon_with_ability(ability_ids::DROUGHT);
        holder.item = item_ids::DAMPROCK;
        let mut battle = test_battle(
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.weather_turns, 5);
    }

    #[test]
    fn intimidate_lowers_both_adjacent_foes_attack() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [100; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], -1);
        assert_eq!(battle.sides[1].mons[1].boosts[crate::stats::Stat::Atk as usize], -1);
    }

    #[test]
    fn intimidate_skips_a_fainted_foe() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [100; 5], [0; 4])],
            1,
        );
        battle.sides[1].mons[0].hp = 0;
        battle.sides[1].mons[0].flags.set(crate::mon::mon_flags::FAINTED);
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], 0, "fainted foe untouched");
        assert_eq!(battle.sides[1].mons[1].boosts[crate::stats::Stat::Atk as usize], -1);
    }

    #[test]
    fn clear_body_and_hyper_cutter_and_inner_focus_and_scrappy_block_intimidate() {
        for blocker in [ability_ids::CLEARBODY, ability_ids::WHITESMOKE, ability_ids::HYPERCUTTER, ability_ids::INNERFOCUS, ability_ids::SCRAPPY] {
            let mut battle = test_battle(
                [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                [mon_with_ability(blocker), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                1,
            );
            on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
            assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], 0, "ability {blocker} should have blocked Intimidate");
        }
    }

    #[test]
    fn keen_eye_blocks_only_an_accuracy_drop() {
        let acc = crate::boosts::Boost::Accuracy as usize;
        let mut deltas = [0i8; 7];
        deltas[acc] = -1;
        deltas[crate::boosts::Boost::Evasion as usize] = -1;
        deltas[crate::stats::Stat::Atk as usize] = -1;
        let out = block_external_negative_boosts(ability_ids::KEENEYE, deltas);
        assert_eq!(out[acc], 0, "accuracy drop blocked");
        assert_eq!(out[crate::boosts::Boost::Evasion as usize], -1, "evasion drop still lands");
        assert_eq!(out[crate::stats::Stat::Atk as usize], -1, "attack drop still lands");
        let mut up = [0i8; 7];
        up[acc] = 1;
        assert_eq!(block_external_negative_boosts(ability_ids::KEENEYE, up)[acc], 1, "accuracy raise unaffected");
    }

    #[test]
    fn guard_dog_turns_intimidate_into_a_plus_one_atk_boost() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::GUARDDOG), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], 1, "Guard Dog should net +1 Atk, not -1");
    }

    #[test]
    fn rattled_gains_a_speed_boost_on_top_of_the_normal_unboost() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::RATTLED), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], -1, "the Atk drop itself still lands");
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Spe as usize], 1, "but Rattled also gains +1 Spe");
    }

    #[test]
    fn defiant_gains_a_plus_two_atk_boost_from_intimidate() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::DEFIANT), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(
            battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], 1,
            "Defiant nets +1 Atk overall: the -1 drop lands, then its own +2 reaction"
        );
    }

    #[test]
    fn competitive_gains_a_plus_two_spa_boost_from_intimidate() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::COMPETITIVE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        let boosts = battle.sides[1].mons[0].boosts;
        assert_eq!(boosts[crate::stats::Stat::Atk as usize], -1, "the Atk drop itself still lands");
        assert_eq!(boosts[crate::stats::Stat::SpA as usize], 2, "but Competitive gains +2 SpA");
    }

    #[test]
    fn mirror_armor_redirects_intimidates_unboost_back_onto_the_intimidate_holder() {




        let mut battle = test_battle(
            [mon_with_ability(ability_ids::INTIMIDATE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::MIRRORARMOR), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[1].mons[0].boosts[crate::stats::Stat::Atk as usize], 0, "Mirror Armor itself should be untouched");
        assert_eq!(battle.sides[0].mons[0].boosts[crate::stats::Stat::Atk as usize], -1, "and the Intimidate holder should take the redirected -1 Atk instead");
    }

    #[test]
    fn grassy_surge_sets_grassy_terrain_on_switch_in() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::GRASSYSURGE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.terrain, crate::field::Terrain::Grassy);
        assert_eq!(battle.field.terrain_turns, 5);
    }

    #[test]
    fn psychic_surge_lasts_eight_turns_with_a_terrain_extender() {
        let mut holder = mon_with_ability(ability_ids::PSYCHICSURGE);
        holder.item = item_ids::TERRAINEXTENDER;
        let mut battle = test_battle(
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.terrain, crate::field::Terrain::Psychic);
        assert_eq!(battle.field.terrain_turns, 8);
    }

    #[test]
    fn unrelated_ability_does_nothing() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::ADAPTABILITY), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.field.weather, Weather::None);
    }

    #[test]
    fn rough_skin_damages_an_attacker_on_a_contact_hit() {
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [80; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::ROUGHSKIN), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let attacker = Actor { side: 0, slot: 0 };
        let defender = Actor { side: 1, slot: 0 };
        let hp_before = mon_at(&battle, attacker).hp;
        contact_punish(&mut battle, attacker, defender, true, &mut crate::rng::Rng::new(0));
        let max_hp = mon_at(&battle, attacker).max_hp;
        assert_eq!(mon_at(&battle, attacker).hp, hp_before - (max_hp / 8).max(1), "1/8 max HP recoil to the attacker");
    }

    #[test]
    fn rough_skin_does_nothing_on_a_non_contact_hit() {
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [80; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::ROUGHSKIN), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let attacker = Actor { side: 0, slot: 0 };
        let defender = Actor { side: 1, slot: 0 };
        let hp_before = mon_at(&battle, attacker).hp;
        contact_punish(&mut battle, attacker, defender, false, &mut crate::rng::Rng::new(0));
        assert_eq!(mon_at(&battle, attacker).hp, hp_before, "no recoil without contact");
    }

    #[test]
    fn stamina_raises_defense_when_hit_by_any_damaging_move() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::STAMINA), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        super::on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Normal, engine_data::moves_table::Category::Physical, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Def as usize], 1, "Stamina should raise Def on any damaging hit, no type restriction");
    }

    #[test]
    fn flame_body_burns_the_attacker_at_roughly_thirty_percent_rate_on_contact() {
        use crate::rng::Rng;
        use crate::status::Status;

        let mut burned = 0;
        for seed in 0..2000u64 {
            let mut battle = test_battle(
                [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                [mon_with_ability(ability_ids::FLAMEBODY), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                1,
            );
            let attacker = Actor { side: 0, slot: 0 };
            let defender = Actor { side: 1, slot: 0 };
            let mut rng = Rng::new(seed);
            contact_status_proc(&mut battle, attacker, defender, true, &mut rng);
            if mon_at(&battle, attacker).status == Status::Burn {
                burned += 1;
            }
        }
        let rate = burned as f64 / 2000.0;
        assert!((0.25..=0.35).contains(&rate), "Flame Body's burn-the-attacker rate {rate} should be close to 30%");
    }

    #[test]
    fn flame_body_never_procs_without_contact() {
        use crate::rng::Rng;
        use crate::status::Status;

        for seed in 0..200u64 {
            let mut battle = test_battle(
                [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                [mon_with_ability(ability_ids::FLAMEBODY), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
                1,
            );
            let attacker = Actor { side: 0, slot: 0 };
            let defender = Actor { side: 1, slot: 0 };
            let mut rng = Rng::new(seed);
            contact_status_proc(&mut battle, attacker, defender, false, &mut rng);
            assert_eq!(mon_at(&battle, attacker).status, Status::None, "no contact, no proc, regardless of roll");
        }
    }

    #[test]
    fn thermal_exchange_raises_attack_when_hit_by_a_fire_move() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::THERMALEXCHANGE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Fire, engine_data::moves_table::Category::Special, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Atk as usize], 1, "Thermal Exchange should raise Atk on a Fire-type hit");
    }

    #[test]
    fn thermal_exchange_does_not_react_to_a_non_fire_move() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::THERMALEXCHANGE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Water, engine_data::moves_table::Category::Special, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Atk as usize], 0, "no reaction to a non-Fire hit");
    }

    #[test]
    fn hospitality_heals_the_ally_a_quarter_max_hp_on_switch_in() {
        let mut holder = mon_with_ability(ability_ids::HOSPITALITY);
        holder.hp = 1;
        let mut ally = test_mon([Some(Type::Normal), None], [1; 5], [0; 4]);
        ally.hp = 1;
        let mut battle = test_battle(
            [holder, ally],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[0].mons[1].hp, 1 + (200 / 4), "ally should be healed 1/4 its own max HP");
        assert_eq!(battle.sides[0].mons[0].hp, 1, "Hospitality doesn't heal the holder itself");
    }

    #[test]
    fn hospitality_does_nothing_if_the_ally_has_already_fainted() {
        let holder = mon_with_ability(ability_ids::HOSPITALITY);
        let mut fainted_ally = test_mon([Some(Type::Normal), None], [1; 5], [0; 4]);
        fainted_ally.hp = 0;
        fainted_ally.flags.set(crate::mon::mon_flags::FAINTED);
        let mut battle = test_battle(
            [holder, fainted_ally],
            [test_mon([Some(Type::Normal), None], [1; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(battle.sides[0].mons[1].hp, 0, "no heal - the ally already fainted");
    }

    #[test]
    fn justified_raises_attack_on_a_dark_type_hit() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::JUSTIFIED), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Dark, engine_data::moves_table::Category::Physical, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Atk as usize], 1, "Justified should raise Atk on a Dark-type hit");
    }

    #[test]
    fn justified_does_not_react_to_a_non_dark_move() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::JUSTIFIED), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Normal, engine_data::moves_table::Category::Physical, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Atk as usize], 0, "no reaction to a non-Dark hit");
    }

    #[test]
    fn weak_armor_lowers_defense_and_raises_speed_on_a_physical_hit() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::WEAKARMOR), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Normal, engine_data::moves_table::Category::Physical, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Def as usize], -1, "Weak Armor should lower Def on a Physical hit");
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Spe as usize], 2, "and raise Spe by 2");
    }

    #[test]
    fn weak_armor_does_not_react_to_a_special_hit() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::WEAKARMOR), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let defender = Actor { side: 1, slot: 0 };
        on_damaging_hit(&mut battle, defender, crate::action::Actor { side: 0, slot: 0 }, Type::Normal, engine_data::moves_table::Category::Special, false, false, &mut crate::rng::Rng::new(1));
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Def as usize], 0, "no reaction to a Special hit");
        assert_eq!(mon_at(&battle, defender).boosts[Stat::Spe as usize], 0);
    }

    #[test]
    fn trace_copies_the_only_eligible_adjacent_foes_ability() {
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::TRACE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::INTIMIDATE), mon_with_ability(ability_ids::INTIMIDATE)],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(mon_at(&battle, Actor { side: 0, slot: 0 }).ability, ability_ids::INTIMIDATE, "Trace should copy the (only, since both foes match) eligible foe's ability");
    }

    #[test]
    fn trace_falls_back_to_the_only_non_fainted_foe() {
        let mut fainted_foe = mon_with_ability(ability_ids::INTIMIDATE);
        fainted_foe.hp = 0;
        fainted_foe.flags.set(crate::mon::mon_flags::FAINTED);
        let mut battle = test_battle(
            [mon_with_ability(ability_ids::TRACE), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [fainted_foe, mon_with_ability(ability_ids::ROUGHSKIN)],
            1,
        );
        on_switch_in(&mut battle, Actor { side: 0, slot: 0 });
        assert_eq!(mon_at(&battle, Actor { side: 0, slot: 0 }).ability, ability_ids::ROUGHSKIN, "Trace should skip the fainted foe and copy the other one");
    }

    #[test]
    fn mirror_armor_redirects_a_negative_boost_onto_the_source() {
        use crate::stats::Stat;

        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::MIRRORARMOR), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let source = Actor { side: 0, slot: 0 };
        let target = Actor { side: 1, slot: 0 };
        let remaining = block_external_boosts(&mut battle, source, target, [-1, 0, 0, 0, 0, 0, 0], &mut crate::rng::Rng::new(1));
        assert_eq!(remaining, [0, 0, 0, 0, 0, 0, 0], "the negative component should be fully redirected away from the target");
        assert_eq!(mon_at(&battle, source).boosts[Stat::Atk as usize], -1, "and land on the source instead");
        assert_eq!(mon_at(&battle, target).boosts[Stat::Atk as usize], 0, "the target itself is untouched");
    }

    #[test]
    fn mirror_armor_does_not_redirect_a_positive_boost() {
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [mon_with_ability(ability_ids::MIRRORARMOR), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let source = Actor { side: 0, slot: 0 };
        let target = Actor { side: 1, slot: 0 };
        let remaining = block_external_boosts(&mut battle, source, target, [1, 0, 0, 0, 0, 0, 0], &mut crate::rng::Rng::new(1));
        assert_eq!(remaining, [1, 0, 0, 0, 0, 0, 0], "a positive boost should pass through untouched");
    }

    #[test]
    fn mirror_armor_leaves_an_already_minus_six_stat_alone() {
        use crate::stats::Stat;

        let mut holder = mon_with_ability(ability_ids::MIRRORARMOR);
        holder.boosts[Stat::Atk as usize] = -6;
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [100; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let source = Actor { side: 0, slot: 0 };
        let target = Actor { side: 1, slot: 0 };
        let remaining = block_external_boosts(&mut battle, source, target, [-1, 0, 0, 0, 0, 0, 0], &mut crate::rng::Rng::new(1));
        assert_eq!(remaining, [-1, 0, 0, 0, 0, 0, 0], "already at -6 - neither redirected nor deleted, lands on the target normally (a no-op once clamped)");
        assert_eq!(mon_at(&battle, source).boosts[Stat::Atk as usize], 0, "and nothing should land on the source");
    }
}
