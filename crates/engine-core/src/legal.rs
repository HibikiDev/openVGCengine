




















use crate::action::{Action, Actor};
use crate::battle::Battle;
use crate::mon::volatile_flags;
use crate::pending::Pending;
use engine_data::moves_table::{self, ChoiceTarget};

pub const TARGET_FOE_A: usize = 0;
pub const TARGET_FOE_B: usize = 1;
pub const TARGET_ALLY: usize = 2;
pub const TARGET_SELF: usize = 3;

pub const MOVE_ACTIONS: usize = 16;
pub const SWITCH_BASE: usize = 16;
pub const PASS_ACTION: usize = 20;
pub const SLOT_ACTIONS: usize = 21;

pub const fn move_action(move_slot: usize, target: usize) -> usize {
    move_slot * 4 + target
}

pub const fn switch_action(mon: usize) -> usize {
    SWITCH_BASE + mon
}

pub const fn is_move_action(action: usize) -> bool {
    action < MOVE_ACTIONS
}


#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SlotMask {
    pub actions: u32,

    pub mega: bool,

    pub ultra: bool,

    pub tera: bool,


    pub dynamax: bool,



    pub max_actions: u32,

    pub max_only: u32,


    pub z_moves: u8,


    pub z_untargeted: u8,



    pub z_only: u8,


    pub struggle: bool,
}

impl SlotMask {
    pub fn allows(&self, action: usize) -> bool {
        action < SLOT_ACTIONS && self.actions & (1 << action) != 0
    }


    pub fn allows_gimmick(&self, action: usize) -> bool {
        if self.dynamax {
            return self.max_actions & (1 << action) != 0;
        }
        let bit = 1 << (action / 4);
        is_move_action(action)
            && (self.mega || (self.z_moves & bit != 0 && (self.z_untargeted & bit == 0 || action % 4 == TARGET_FOE_A)))
    }


    pub fn z_only_action(&self, action: usize) -> bool {
        if self.dynamax {
            return self.max_only & (1 << action) != 0;
        }
        is_move_action(action) && self.z_only & (1 << (action / 4)) != 0
    }


    pub fn plain_actions(&self) -> u32 {
        (0..MOVE_ACTIONS).filter(|&a| self.z_only_action(a)).fold(self.actions, |acc, a| acc & !(1 << a))
    }





    pub fn gimmick_masks(&self) -> (u32, u32, u8) {
        let (gimmick, forced) = (0..SLOT_ACTIONS).filter(|&a| self.allows(a)).fold((0u32, 0u32), |(g, f), a| {
            let ok = self.allows_gimmick(a);
            (g | ((ok as u32) << a), f | (((ok && self.z_only_action(a)) as u32) << a))
        });
        let kind = match (self.mega, self.ultra) {
            (true, false) if self.dynamax => 5,
            (true, false) if self.tera => 4,
            (true, false) => 1,
            (true, true) => 3,
            _ if self.z_moves != 0 => 2,
            _ => 0,
        };
        (gimmick, forced, kind)
    }

    fn allow(&mut self, action: usize) {
        self.actions |= 1 << action;
    }
}


#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SideMask {


    pub to_move: bool,
    pub slots: [SlotMask; 2],

    pub min_switches: u8,
}


pub fn side_mask(battle: &Battle, side: u8) -> SideMask {
    match battle.pending {
        Pending::Over { .. } => SideMask::default(),
        Pending::Turn => SideMask {
            to_move: true,
            slots: [turn_slot_mask(battle, Actor { side, slot: 0 }), turn_slot_mask(battle, Actor { side, slot: 1 })],
            min_switches: 0,
        },
        Pending::ForcedSwitch { side0, side1 } => {
            if !(if side == 0 { side0 } else { side1 }) {
                return SideMask::default();
            }
            let owed = crate::turn::owed_replacements(battle, side);
            let required = crate::turn::forced_switch_count(battle, side);
            let asked = owed.iter().filter(|&&o| o).count() as u8;
            let slot_mask = |slot: usize| {
                let mut mask = SlotMask::default();
                if !owed[slot] || asked > required {
                    mask.allow(PASS_ACTION);
                }
                if owed[slot] {
                    let s = &battle.sides[side as usize];
                    let reviving = s.active_mon(slot).volatiles.has(volatile_flags::REVIVAL);
                    for (k, m) in s.mons.iter().enumerate() {
                        let candidate = if reviving { m.is_fainted() } else { !m.is_fainted() && !s.active[..2].contains(&(k as u8)) };
                        if candidate {
                            mask.allow(switch_action(k));
                        }
                    }
                }
                mask
            };
            SideMask { to_move: true, slots: [slot_mask(0), slot_mask(1)], min_switches: required }
        }
    }
}


fn turn_slot_mask(battle: &Battle, actor: Actor) -> SlotMask {
    let side = &battle.sides[actor.side as usize];
    let mon = side.active_mon(actor.slot as usize);
    let mut mask = SlotMask::default();

    if mon.is_fainted() || mon.flags.has(crate::mon::mon_flags::COMMANDING) {
        mask.allow(PASS_ACTION);
        return mask;
    }


    if mon.volatiles.has(volatile_flags::CHARGING) || mon.volatiles.has(volatile_flags::MUSTRECHARGE) || mon.lock_move != 0 {
        mask.allow(move_action(0, TARGET_SELF));
        return mask;
    }


    if mon.flags.has(crate::mon::mon_flags::DYNAMAXED) {
        if crate::turn::max_request_enabled(battle, actor).iter().any(|&u| u) {
            for i in 0..4 {
                if mon.moves[i] != 0 && !crate::turn::max_move_disabled(battle, mon, i) {
                    for &target in choosable_targets(max_choice_target(battle.rules(), mon.moves[i])) {
                        mask.allow(move_action(i, target));
                    }
                }
            }
        } else {
            mask.allow(move_action(0, TARGET_SELF));
            mask.struggle = true;
        }
        if !crate::turn::is_trapped(battle, actor) {
            for (k, m) in side.mons.iter().enumerate() {
                if !m.is_fainted() && !side.active[..2].contains(&(k as u8)) {
                    mask.allow(switch_action(k));
                }
            }
        }
        return mask;
    }
    let usable = crate::turn::usable_moves(battle, actor);
    if usable.iter().any(|&u| u) {
        for (i, &ok) in usable.iter().enumerate() {
            if !ok {
                continue;
            }
            for &target in choosable_targets(request_target(battle.rules(), mon, mon.moves[i])) {
                mask.allow(move_action(i, target));
            }
        }

        if can_dynamax(battle, actor) {
            mask.mega = true;
            mask.dynamax = true;
            for i in 0..4 {
                if mon.moves[i] != 0 && !crate::turn::max_move_disabled(battle, mon, i) {
                    for &target in choosable_targets(max_choice_target(battle.rules(), mon.moves[i])) {
                        mask.max_actions |= 1 << move_action(i, target);
                    }
                }
            }
            mask.max_only = mask.max_actions & !mask.actions;
            mask.actions |= mask.max_actions;
            if !crate::turn::is_trapped(battle, actor) {
                for (k, m) in side.mons.iter().enumerate() {
                    if !m.is_fainted() && !side.active[..2].contains(&(k as u8)) {
                        mask.allow(switch_action(k));
                    }
                }
            }
            return mask;
        }
        mask.tera = can_terastallize(battle, actor);
        mask.mega = can_mega_evolve(battle, actor) || mask.tera;
        mask.ultra = mask.mega && crate::items::is_ultra_burst(mon.item, crate::items::pre_transform_species(mon));
        mask.z_moves = if mask.mega { 0 } else { crate::turn::z_move_slots(battle, actor) };
        for k in 0..4 {
            if mask.z_moves & (1 << k) != 0 {
                let z = crate::turn::z_move_for(battle.rules(), mon, mon.moves[k]).unwrap_or(mon.moves[k]);
                if battle.move_data(z).choice_target == ChoiceTarget::None
                    && request_target(battle.rules(), mon, mon.moves[k]) != ChoiceTarget::None
                {
                    mask.z_untargeted |= 1 << k;
                }

                if !usable[k] {
                    mask.z_only |= 1 << k;
                    for &target in choosable_targets(request_target(battle.rules(), mon, mon.moves[k])) {
                        if mask.z_untargeted & (1 << k) == 0 || target == TARGET_FOE_A {
                            mask.allow(move_action(k, target));
                        }
                    }
                }
            }
        }
    } else {



        mask.allow(move_action(0, TARGET_SELF));
        let last_active = actor.slot == 1 || crate::turn::mon_at(battle, Actor { side: actor.side, slot: 1 }).is_fainted();
        if last_active && crate::turn::usable_moves_with(battle, actor, false).iter().any(|&u| u) {
            mask.tera = can_terastallize(battle, actor);
            mask.mega = can_mega_evolve(battle, actor) || mask.tera;
        }
        mask.struggle = true;
    }
    if !crate::turn::is_trapped(battle, actor) {
        for (k, m) in side.mons.iter().enumerate() {
            if !m.is_fainted() && !side.active[..2].contains(&(k as u8)) {
                mask.allow(switch_action(k));
            }
        }
    }
    mask
}


fn request_target(rules: &crate::rules::Rules, mon: &crate::mon::Mon, move_id: u16) -> ChoiceTarget {
    if move_id == moves_table::move_ids::CURSE && !mon.types.contains(&Some(engine_data::type_chart::Type::Ghost)) {
        return ChoiceTarget::None;
    }

    if move_id == moves_table::move_ids::TERASTARSTORM && mon.species == engine_data::species_table::species_ids::TERAPAGOSSTELLAR {
        return ChoiceTarget::None;
    }

    if move_id == moves_table::move_ids::POLLENPUFF && mon.heal_block_turns > 0 {
        return ChoiceTarget::AdjacentFoe;
    }
    rules.move_data(move_id).choice_target
}


fn max_choice_target(rules: &crate::rules::Rules, base: u16) -> ChoiceTarget {
    if rules.move_data(base).category == moves_table::Category::Status {
        ChoiceTarget::None
    } else {
        ChoiceTarget::AdjacentFoe
    }
}




pub fn can_dynamax(battle: &Battle, actor: Actor) -> bool {
    let side = &battle.sides[actor.side as usize];
    let mon = side.active_mon(actor.slot as usize);
    let disguise_cannot = mon.illusion.is_some_and(|i| engine_data::max_table::CANNOT_DYNAMAX.contains(&side.mons[i as usize].species));
    battle.rules().dynamax
        && !side.dynamax_used
        && !mon.flags.has(crate::mon::mon_flags::DYNAMAXED)
        && !engine_data::max_table::CANNOT_DYNAMAX.contains(&mon.species)
        && !disguise_cannot
        && engine_data::z_table::crystal(mon.item).is_none()
        && crate::items::mega_target(battle.rules(), mon).is_none()
        && (0..4).any(|i| mon.moves[i] != 0 && !crate::turn::max_move_disabled(battle, mon, i))
}


fn choosable_targets(choice: ChoiceTarget) -> &'static [usize] {
    match choice {
        ChoiceTarget::None => &[TARGET_SELF],
        ChoiceTarget::Adjacent => &[TARGET_FOE_A, TARGET_FOE_B, TARGET_ALLY],
        ChoiceTarget::AdjacentFoe => &[TARGET_FOE_A, TARGET_FOE_B],
        ChoiceTarget::AdjacentAlly => &[TARGET_ALLY],
        ChoiceTarget::AllyOrSelf => &[TARGET_ALLY, TARGET_SELF],
    }
}



pub fn can_mega_evolve(battle: &Battle, actor: Actor) -> bool {
    let side = &battle.sides[actor.side as usize];
    let mon = side.active_mon(actor.slot as usize);
    let ultra = crate::items::is_ultra_burst(mon.item, crate::items::pre_transform_species(mon));
    !side.forme_change_used(ultra) && !mon.mega.active && crate::items::mega_target(battle.rules(), mon).is_some()
}



pub fn can_terastallize(battle: &Battle, actor: Actor) -> bool {
    let side = &battle.sides[actor.side as usize];
    mon_can_terastallize(battle.rules(), side, side.active_mon(actor.slot as usize))
}


pub fn mon_can_terastallize(rules: &crate::rules::Rules, side: &crate::side::Side, mon: &crate::mon::Mon) -> bool {
    rules.terastallization
        && !side.tera_used
        && !mon.tera.active
        && mon.tera.tera_type.is_some()

        && !(mon.flags.has(crate::mon::mon_flags::TRANSFORMED) && crate::turn::ogerpon_or_terapagos(mon.species))
        && engine_data::z_table::crystal(mon.item).is_none()
        && crate::items::mega_target(rules, mon).is_none()
}


pub fn joint_is_legal(mask: &SideMask, actions: [(usize, bool); 2]) -> bool {
    if !mask.to_move {
        return false;
    }
    for (slot, &(action, mega)) in actions.iter().enumerate() {
        let m = &mask.slots[slot];
        if !m.allows(action) || (mega && !m.allows_gimmick(action)) || (!mega && m.z_only_action(action)) {
            return false;
        }
    }



    let [(a0, mega0), (a1, mega1)] = actions;
    let kind = |m: &SlotMask| (m.mega, m.ultra);
    if mega0 && mega1 && !mask.slots[0].struggle && !mask.slots[1].struggle && kind(&mask.slots[0]) == kind(&mask.slots[1]) {
        return false;
    }
    let is_switch = |a: usize| (SWITCH_BASE..PASS_ACTION).contains(&a);
    if is_switch(a0) && a0 == a1 {
        return false;
    }
    (is_switch(a0) as u8 + is_switch(a1) as u8) >= mask.min_switches
}



pub fn for_each_legal_joint(mask: &SideMask, mut f: impl FnMut([(usize, bool); 2])) {
    if !mask.to_move {
        return;
    }
    let options = |m: &SlotMask, a: usize| -> &'static [bool] {
        if m.z_only_action(a) { &[true] } else if m.allows_gimmick(a) { &[false, true] } else { &[false] }
    };
    for a0 in (0..SLOT_ACTIONS).filter(|&a| mask.slots[0].allows(a)) {
        for &mega0 in options(&mask.slots[0], a0) {
            for a1 in (0..SLOT_ACTIONS).filter(|&a| mask.slots[1].allows(a)) {
                for &mega1 in options(&mask.slots[1], a1) {
                    let joint = [(a0, mega0), (a1, mega1)];
                    if joint_is_legal(mask, joint) {
                        f(joint);
                    }
                }
            }
        }
    }
}


pub fn decode(battle: &Battle, side: u8, slot: u8, action: usize, mega: bool) -> Action {
    if action == PASS_ACTION {
        return Action::Pass;
    }
    if action >= SWITCH_BASE {
        return Action::Switch { bench_slot: (action - SWITCH_BASE) as u8 };
    }
    let move_slot = (action / 4) as u8;
    let target_slot = match action % 4 {
        TARGET_FOE_A => 0,
        TARGET_FOE_B => 1,
        TARGET_ALLY => 2 + (1 - slot),

        _ => {
            let mon = battle.sides[side as usize].active_mon(slot as usize);
            let named = mon.moves.get(move_slot as usize).map_or(false, |&m| m != 0 && battle.move_data(m).choice_target == ChoiceTarget::AllyOrSelf);
            if named { 2 + slot } else { 0 }
        }
    };


    let can_mega = mega
        && (can_mega_evolve(battle, Actor { side, slot }) || can_terastallize(battle, Actor { side, slot }) || can_dynamax(battle, Actor { side, slot }));
    Action::Move { move_slot, target_slot, mega: can_mega, z: mega && !can_mega }
}



pub fn encode(battle: &Battle, side: u8, slot: u8, action: Action) -> (usize, bool) {
    match action {
        Action::Pass => (PASS_ACTION, false),
        Action::Switch { bench_slot } => (switch_action(bench_slot as usize), false),
        Action::Move { move_slot, target_slot, mega, z } => {
            let mega = mega || z;
            let actor = Actor { side, slot };
            let mon = battle.sides[side as usize].active_mon(slot as usize);
            let locked = mon.volatiles.has(volatile_flags::CHARGING) || mon.volatiles.has(volatile_flags::MUSTRECHARGE) || mon.lock_move != 0;
            let dynamaxed = mon.flags.has(crate::mon::mon_flags::DYNAMAXED);
            let struggling = if dynamaxed {
                !crate::turn::max_request_enabled(battle, actor).iter().any(|&u| u)
            } else {
                !crate::turn::usable_moves(battle, actor).iter().any(|&u| u)
            };
            if locked || struggling {
                return (move_action(0, TARGET_SELF), mega);
            }
            let max = dynamaxed || (mega && battle.rules().dynamax);
            let choice = if max {
                max_choice_target(battle.rules(), mon.moves[move_slot as usize])
            } else {
                request_target(battle.rules(), mon, mon.moves[move_slot as usize])
            };
            let target = match (choice, target_slot) {
                (ChoiceTarget::None, _) => TARGET_SELF,
                (_, 0) => TARGET_FOE_A,
                (_, 1) => TARGET_FOE_B,
                (_, t) if t == 2 + slot => TARGET_SELF,
                _ => TARGET_ALLY,
            };
            (move_action(move_slot as usize, target), mega)
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::mon::{mon_flags, Mon};
    use crate::turn::tests::{test_battle, test_mon};
    use engine_data::moves_table::move_ids;
    use engine_data::type_chart::Type;

    fn mon(moves: [u16; 4]) -> Mon {
        test_mon([Some(Type::Normal), None], [100; 5], moves)
    }


    fn battle_with(moves: [u16; 4]) -> Battle {
        let mut battle = test_battle([mon(moves), mon(moves)], [mon(moves), mon(moves)], 1);
        battle.sides[0].mons[2] = mon(moves);
        battle
    }

    fn legal_joints(mask: &SideMask) -> Vec<[(usize, bool); 2]> {
        let mut out = Vec::new();
        for_each_legal_joint(mask, |j| out.push(j));
        out
    }

    #[test]
    fn a_normal_turn_offers_each_move_at_its_choosable_targets_and_a_switch_to_each_living_bench_mon() {
        let battle = battle_with([move_ids::TACKLE, move_ids::ROCKSLIDE, move_ids::HELPINGHAND, move_ids::ACUPRESSURE]);
        let slot = side_mask(&battle, 0).slots[0];
        let expected = [
            move_action(0, TARGET_FOE_A),
            move_action(0, TARGET_FOE_B),
            move_action(0, TARGET_ALLY),
            move_action(1, TARGET_SELF),
            move_action(2, TARGET_ALLY),
            move_action(3, TARGET_ALLY),
            move_action(3, TARGET_SELF),
            switch_action(2),
        ];
        for a in 0..SLOT_ACTIONS {
            assert_eq!(slot.allows(a), expected.contains(&a), "action {a}");
        }
        assert!(!slot.mega, "no Mega Stone");

        assert!((SWITCH_BASE..PASS_ACTION).all(|a| !side_mask(&battle, 1).slots[0].allows(a)));
    }

    #[test]
    fn both_slots_cannot_switch_to_the_same_mon() {
        let battle = battle_with([move_ids::TACKLE, 0, 0, 0]);
        let mask = side_mask(&battle, 0);
        assert!(!joint_is_legal(&mask, [(switch_action(2), false), (switch_action(2), false)]));
        assert!(joint_is_legal(&mask, [(switch_action(2), false), (move_action(0, TARGET_FOE_A), false)]));
    }

    #[test]
    fn a_fainted_slot_can_only_pass() {
        let mut battle = battle_with([move_ids::TACKLE, 0, 0, 0]);
        let m = &mut battle.sides[0].mons[1];
        m.hp = 0;
        m.flags.set(mon_flags::FAINTED);
        assert_eq!(side_mask(&battle, 0).slots[1].actions, 1 << PASS_ACTION);
    }

    #[test]
    fn a_charging_or_recharging_mon_has_one_action_and_no_switch() {
        for flag in [volatile_flags::CHARGING, volatile_flags::MUSTRECHARGE] {
            let mut battle = battle_with([move_ids::TACKLE, move_ids::SOLARBEAM, 0, 0]);
            battle.sides[0].mons[0].volatiles.set(flag);
            let slot = side_mask(&battle, 0).slots[0];
            assert_eq!(slot.actions, 1 << move_action(0, TARGET_SELF));
            assert!(!slot.mega);
        }
    }

    #[test]
    fn a_mon_with_no_pp_left_can_only_struggle_but_can_still_switch() {
        let mut battle = battle_with([move_ids::TACKLE, move_ids::PROTECT, 0, 0]);
        battle.sides[0].mons[0].pp = [0; 4];
        let slot = side_mask(&battle, 0).slots[0];
        assert_eq!(slot.actions, (1 << move_action(0, TARGET_SELF)) | (1 << switch_action(2)));
    }

    #[test]
    fn mega_evolution_is_offered_once_per_side() {
        let mut battle = battle_with([move_ids::TACKLE, 0, 0, 0]);
        for slot in 0..2 {
            let m = &mut battle.sides[0].mons[slot];
            m.species = engine_data::species_table::species_ids::SALAMENCE;
            m.item = engine_data::items_table::item_ids::SALAMENCITE;
        }
        let mask = side_mask(&battle, 0);
        assert!(mask.slots[0].mega && mask.slots[1].mega);
        let tackle = move_action(0, TARGET_FOE_A);
        assert!(joint_is_legal(&mask, [(tackle, true), (tackle, false)]));
        assert!(!joint_is_legal(&mask, [(tackle, true), (tackle, true)]), "only one Mega Evolution per side");
        assert!(!joint_is_legal(&mask, [(switch_action(2), true), (tackle, false)]), "Mega Evolution rides on a move");
        battle.sides[0].mega_used = true;
        assert!(!side_mask(&battle, 0).slots[0].mega);
    }

    #[test]
    fn two_empty_slots_and_one_bench_mon_lets_the_player_pick_which_slot_to_refill() {
        let mut battle = battle_with([move_ids::TACKLE, 0, 0, 0]);
        for slot in 0..2 {
            let m = &mut battle.sides[0].mons[slot];
            m.hp = 0;
            m.flags.set(mon_flags::FAINTED);
        }
        battle.pending = Pending::ForcedSwitch { side0: true, side1: false };
        let mask = side_mask(&battle, 0);
        assert_eq!(mask.min_switches, 1);
        let joints = legal_joints(&mask);
        let pass = (PASS_ACTION, false);
        let switch = (switch_action(2), false);
        assert_eq!(joints, vec![[switch, pass], [pass, switch]]);
        assert!(!side_mask(&battle, 1).to_move, "side 1 isn't asked anything");
    }

    #[test]
    fn decode_then_encode_is_the_identity_on_every_legal_action() {
        let battle = battle_with([move_ids::TACKLE, move_ids::ROCKSLIDE, move_ids::HELPINGHAND, move_ids::ACUPRESSURE]);
        for side in 0..2u8 {
            let mask = side_mask(&battle, side);
            for slot in 0..2u8 {
                for a in (0..SLOT_ACTIONS).filter(|&a| mask.slots[slot as usize].allows(a)) {
                    let action = decode(&battle, side, slot, a, false);
                    assert_eq!(encode(&battle, side, slot, action), (a, false), "side {side} slot {slot} action {a} -> {action:?}");
                }
            }
        }
    }
}
