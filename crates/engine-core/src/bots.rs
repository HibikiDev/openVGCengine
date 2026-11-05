








use crate::action::{Action, JointAction};
use crate::battle::Battle;
use crate::legal::{self, SideMask, PASS_ACTION, SLOT_ACTIONS, SWITCH_BASE};
use crate::pending::Pending;
use crate::rng::Rng;


const ROLLS: u64 = 2;

const KO_BONUS: f32 = 1.0;

const ALLY_PENALTY: f32 = 1.5;



pub fn greedy_damage(battle: &Battle, side: u8, seed: u64) -> JointAction {
    let mask = legal::side_mask(battle, side);
    if !mask.to_move {
        return [Action::Pass; 2];
    }
    if matches!(battle.pending, Pending::ForcedSwitch { .. }) {
        return forced_switch(battle, side, &mask);
    }
    let mut chosen = [(PASS_ACTION, false); 2];
    for slot in 0..2u8 {
        let m = mask.slots[slot as usize];



        let plain = m.plain_actions();
        let moves: Vec<usize> = (0..SWITCH_BASE).filter(|&a| plain & (1 << a) != 0).collect();
        if moves.is_empty() {


            chosen[slot as usize] = match (0..SLOT_ACTIONS).find(|&a| plain & (1 << a) != 0) {
                Some(a) => (a, false),
                None => (0..SWITCH_BASE).find(|&a| m.z_only_action(a) && m.allows_gimmick(a)).map_or((PASS_ACTION, false), |a| (a, true)),
            };
            continue;
        }
        let mut best = (moves[0], f32::MIN);
        for &a in &moves {
            let score = simulate(battle, side, slot, a, seed);
            if score > best.1 {
                best = (a, score);
            }
        }



        let mega = m.mega && m.allows_gimmick(best.0) && !(slot == 1 && chosen[0].1);
        chosen[slot as usize] = (best.0, mega);
    }
    if !legal::joint_is_legal(&mask, chosen) {
        chosen[1].1 = false;
    }
    [legal::decode(battle, side, 0, chosen[0].0, chosen[0].1), legal::decode(battle, side, 1, chosen[1].0, chosen[1].1)]
}


fn simulate(battle: &Battle, side: u8, slot: u8, a: usize, seed: u64) -> f32 {
    let foe = 1 - side as usize;
    let hp = |b: &Battle, s: usize, i: usize| b.sides[s].active_mon(i).hp as f32 / b.sides[s].active_mon(i).max_hp.max(1) as f32;
    let ally = 1 - slot as usize;
    let mut total = 0.0;
    for r in 0..ROLLS {
        let mut b = *battle;
        b.rng = Rng::new(seed.wrapping_mul(0x9E37_79B9_7F4A_7C15).wrapping_add(r * 7919 + a as u64));
        let before_foe = [hp(&b, foe, 0), hp(&b, foe, 1)];
        let before_ally = hp(&b, side as usize, ally);
        let mut actions = [[Action::Pass; 2]; 2];
        actions[side as usize][slot as usize] = legal::decode(battle, side, slot, a, false);
        crate::turn::step(&mut b, actions);
        let mut score = 0.0;
        for i in 0..2 {
            let after = hp(&b, foe, i);
            score += before_foe[i] - after;
            if before_foe[i] > 0.0 && after == 0.0 {
                score += KO_BONUS;
            }
        }
        score -= ALLY_PENALTY * (before_ally - hp(&b, side as usize, ally)).max(0.0);
        total += score;
    }
    total / ROLLS as f32
}


fn forced_switch(battle: &Battle, side: u8, mask: &SideMask) -> JointAction {
    let s = &battle.sides[side as usize];
    let mut taken = [false; 4];
    let mut out = [Action::Pass; 2];
    for slot in 0..2usize {
        let m = mask.slots[slot];
        let best = (0..4usize)
            .filter(|&k| m.allows(crate::legal::switch_action(k)) && !taken[k])
            .max_by_key(|&k| (s.mons[k].hp as u32 * 1000) / s.mons[k].max_hp.max(1) as u32);
        match best {
            Some(k) => {
                taken[k] = true;
                out[slot] = Action::Switch { bench_slot: k as u8 };
            }
            None => out[slot] = Action::Pass,
        }
    }

    out
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mon::mon_flags;
    use crate::turn::tests::{test_battle, test_mon};
    use engine_data::moves_table::move_ids;
    use engine_data::type_chart::Type;

    #[test]
    fn greedy_dynamaxes_only_with_a_move_whose_max_move_is_legal() {

        let mut battle = test_battle([test_mon([Some(Type::Normal), None], [100; 5], [move_ids::HELPINGHAND, 0, 0, 0]),
                                      test_mon([Some(Type::Normal), None], [100; 5], [move_ids::TACKLE, 0, 0, 0])],
                                     [test_mon([Some(Type::Normal), None], [100; 5], [move_ids::TACKLE, 0, 0, 0]),
                                      test_mon([Some(Type::Normal), None], [100; 5], [move_ids::TACKLE, 0, 0, 0])], 1);
        battle.format = crate::rules::Format::Gen8Vgc;
        assert!(legal::can_dynamax(&battle, crate::action::Actor { side: 0, slot: 0 }), "the slot can Dynamax");
        let joint = greedy_damage(&battle, 0, 5);
        assert!(matches!(joint[0], Action::Move { move_slot: 0, mega: false, .. }), "slot a: Helping Hand without Dynamax, got {:?}", joint[0]);
        assert!(matches!(joint[1], Action::Move { mega: true, .. }), "slot b Dynamaxes with Tackle, got {:?}", joint[1]);
    }

    #[test]
    fn greedy_attacks_rather_than_protects() {
        let me = test_mon([Some(Type::Normal), None], [100; 5], [move_ids::PROTECT, move_ids::TACKLE, 0, 0]);
        let foe = test_mon([Some(Type::Normal), None], [100; 5], [move_ids::TACKLE, 0, 0, 0]);
        let battle = test_battle([me, me], [foe, foe], 1);
        let joint = greedy_damage(&battle, 0, 3);
        for a in joint {
            assert!(matches!(a, Action::Move { move_slot: 1, .. }), "{a:?}");
        }
    }

    #[test]
    fn greedy_refills_with_the_healthiest_bench_mon() {
        let me = test_mon([Some(Type::Normal), None], [100; 5], [move_ids::TACKLE, 0, 0, 0]);
        let mut battle = test_battle([me, me], [me, me], 1);
        let mut hurt = me;
        hurt.hp = 20;
        battle.sides[0].mons[2] = hurt;
        battle.sides[0].mons[3] = me;
        let m = &mut battle.sides[0].mons[0];
        m.hp = 0;
        m.flags.set(mon_flags::FAINTED);
        battle.pending = Pending::ForcedSwitch { side0: true, side1: false };
        assert_eq!(greedy_damage(&battle, 0, 1), [Action::Switch { bench_slot: 3 }, Action::Pass]);
    }
}
