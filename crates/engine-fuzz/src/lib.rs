





use engine_core::action::{Action, JointAction};
use engine_core::battle::Battle;
use engine_core::event::EventRing;
use engine_core::field::Field;
use engine_core::ids::NONE_ID;
use engine_core::mon::{MegaState, Mon, MonFlags, Volatiles};
use engine_core::pending::Pending;
use engine_core::rng::Rng;
use engine_core::side::{Side, SideConds};
use engine_data::moves_table::{self, MOVE_COUNT};
use engine_data::type_chart::Type;







fn random_non_stellar_type(rng: &mut Rng) -> Type {
    let stellar = Type::Stellar as u32;
    let r = rng.random(engine_data::type_chart::TYPE_COUNT as u32 - 1);
    Type::from_index((if r < stellar { r } else { r + 1 }) as u8)
}




pub fn random_mon(rng: &mut Rng) -> Mon {
    let type1 = random_non_stellar_type(rng);
    let type2 = if rng.chance(1, 2) { Some(random_non_stellar_type(rng)) } else { None };
    let stat = |rng: &mut Rng| 80 + rng.random(71) as u16;
    let stats = [stat(rng), stat(rng), stat(rng), stat(rng), stat(rng)];
    let hp = 150 + rng.random(101) as u16;

    let mut moves = [0u16; 4];
    for m in moves.iter_mut() {


        *m = loop {
            let id = 1 + rng.random(MOVE_COUNT as u32) as u16;
            if moves_table::ported(id) {
                break id;
            }
        };
    }

    Mon {
        species: 1,
        ability: NONE_ID,
        base_ability: NONE_ID,
        suppressed_ability: NONE_ID,
        base_moves: [NONE_ID; 4],
        base_pp: [0; 4],
        pre_transform_species: NONE_ID,
        item: NONE_ID,
        moves,
        pp: engine_core::mon::full_pp(moves),
        hp,
        max_hp: hp,
        base_max_hp: hp,
        dynamax_level: 10,
        dynamax_turns: 0,
        regen_hidden: 0,
        stats,


        stat_points: [0; 6],
        ivs: [31; 6],
        nature: engine_core::stats::Nature::neutral(),
        boosts: [0; 7],
        mirror_herb: [0; 7],
        status: engine_core::status::Status::None,
        status_counter: 0,
        sleep_start: 0,
        volatiles: Volatiles::default(),
        happiness: 255,
        types: [Some(type1), type2, None],
        mega: MegaState::default(),
        tera: Default::default(),
        flags: MonFlags::default(),
        turns_active: 0,
        move_actions_since_switch_in: 0,
        protect_counter: 0,
        throat_chop_turns: 0,
        last_move: 0,
        last_move_target: 0,
        last_move_used_type: None,
        bide_damage: 0,
        disable_move: 0,
        disable_turns: 0,
        trap_turns: 0,
        trapped_by: 0,
        confusion_turns: 0,
        charge_target: 0,
        charge_move: 0,
        encore_move: 0,
        encore_target: None,
        ally_switch_counter: 0,
        choice_move: 0,
        speed_cache: 0,
        ally_switch_turn: 0,
        encore_turns: 0,
        perish_turns: 0,
        taunt_turns: 0,
        yawn_turns: 0,
        heal_block_turns: 0,
        times_attacked: 0,
        stockpile_layers: 0,
        stockpile_def: 0,
        stockpile_spd: 0,
        magnet_rise_turns: 0,
        leech_seeder: 0,
        syrup_turns: 0,
        syrup_source: 0,
        locked_by: 0,
        moves_used: 0,
        moves_revealed: 0,
        transform_known: 0,
        lock_on_target: 0,
        lock_on_turns: 0,
        hit_by_this_turn: 0,
        last_hit_slot: 0,
        last_hit_damage: 0,
        last_hit_this_turn: false,
        counter_slot: 0,
        counter_damage: 0,
        mirror_slot: 0,
        mirror_damage: 0,
        octolock_source: 0,
        last_item: 0,
        cud_berry: 0,
        cud_counter: 0,
        hurt_hp: 0,
        lock_move: 0,
        lock_turns: 0,
        lock_true: 0,
        sub_hp: 0,
        roost_types: [None, None, None],
        move_result_this_turn: 0,
        move_result_last_turn: 0,
        faint_seq: 0,
        ability_order: 0,
        illusion: None,
    }
}

fn random_side(rng: &mut Rng) -> Side {
    Side {
        mons: [random_mon(rng), random_mon(rng), random_mon(rng), random_mon(rng)],
        active: [0, 1, engine_core::side::NO_PHANTOM],
        side_conditions: SideConds::default(),
        mega_used: false,
        z_used: false, ultra_used: false, tera_used: false, dynamax_used: false,
        revivals: 0,
        order: [0, 1, 2, 3],
    }
}

pub fn random_battle(seed: u64) -> Battle {
    let mut rng = Rng::new(seed);
    let mut battle = Battle {
        sides: [random_side(&mut rng), random_side(&mut rng)],
        field: Field::default(),
        turn: 0,
        rng,
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
    engine_core::turn::start_battle(&mut battle);
    battle
}

fn random_move_action(rng: &mut Rng) -> Action {


    Action::Move { move_slot: rng.random(4) as u8, target_slot: rng.random(2) as u8, mega: false, z: false }
}

pub fn random_joint_action(rng: &mut Rng) -> JointAction {
    [random_move_action(rng), random_move_action(rng)]
}



pub fn random_legal_actions(battle: &Battle, rng: &mut Rng) -> [JointAction; 2] {
    use engine_core::legal;
    let mut actions = [[Action::Pass; 2]; 2];
    for side in 0..2u8 {
        let mask = legal::side_mask(battle, side);
        if !mask.to_move {
            continue;
        }
        let pick = |slot: usize, rng: &mut Rng| {
            let m = mask.slots[slot];
            let mut k = rng.random(m.actions.count_ones());
            let a = (0..legal::SLOT_ACTIONS).filter(|&a| m.allows(a)).find(|_| { let hit = k == 0; k = k.wrapping_sub(1); hit }).unwrap();
            (a, m.mega && legal::is_move_action(a) && rng.random(2) == 0)
        };
        let joint = loop {
            let joint = [pick(0, rng), pick(1, rng)];
            if legal::joint_is_legal(&mask, joint) {
                break joint;
            }
        };
        for slot in 0..2u8 {
            let (a, mega) = joint[slot as usize];
            actions[side as usize][slot as usize] = legal::decode(battle, side, slot, a, mega);
        }
    }
    actions
}

fn side_is_wiped(side: &Side) -> bool {
    side.mons.iter().all(|m| m.is_fainted())
}

pub fn battle_is_over(battle: &Battle) -> bool {
    side_is_wiped(&battle.sides[0]) || side_is_wiped(&battle.sides[1])
}




pub fn run_random_battle(battle: &mut Battle, max_turns: u32) -> u32 {
    let mut steps = 0;
    while steps < max_turns && !battle_is_over(battle) {
        if let Pending::Over { .. } = battle.pending {
            break;
        }
        let mut rng = battle.rng;
        let actions = random_legal_actions(battle, &mut rng);
        battle.rng = rng;
        engine_core::turn::step(battle, actions);
        steps += 1;
    }
    steps
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn random_battles_run_to_completion_without_panicking() {







        let mut stalled = 0;
        for seed in 0..500 {
            let mut battle = random_battle(seed);
            let turns = run_random_battle(&mut battle, 200);
            if turns >= 200 {
                stalled += 1;
            }
        }
        assert!(stalled < 500, "every single seed stalled - that would suggest a real bug, not bad luck");
    }

    #[test]
    fn determinism_holds_across_many_random_battles() {
        for seed in 0..100 {
            let mut a = random_battle(seed);
            let mut b = random_battle(seed);
            run_random_battle(&mut a, 200);
            run_random_battle(&mut b, 200);
            for side in 0..2 {
                for slot in 0..4 {
                    assert_eq!(a.sides[side].mons[slot].hp, b.sides[side].mons[slot].hp, "seed {seed}");
                }
            }
        }
    }
}
