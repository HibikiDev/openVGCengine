

use engine_data::type_chart::Type;

use crate::ids::{AbilityId, ItemId, MoveId, SpeciesId};
use crate::stats::{Nature, Stat};
use crate::status::Status;




pub mod volatile_flags {


    pub const FLINCH: u64 = 1 << 0;



    pub const PROTECTED: u64 = 1 << 1;






    pub const FLASHFIRE: u64 = 1 << 2;










    pub const ITEM_CONSUMED: u64 = 1 << 3;














    pub const VOLUNTARY_SWITCH: u64 = 1 << 4;






    pub const HELPINGHAND: u64 = 1 << 5;





    pub const FOLLOWME: u64 = 1 << 6;



    pub const KINGSSHIELD: u64 = 1 << 7;


    pub const SPIKYSHIELD: u64 = 1 << 8;


    pub const BANEFULBUNKER: u64 = 1 << 9;



    pub const CHARGING: u64 = 1 << 10;


    pub const MUSTRECHARGE: u64 = 1 << 11;




    pub const BERRY_CHECK: u64 = 1 << 12;



    pub const ACTED_THIS_TURN: u64 = 1 << 13;



    pub const RAGEPOWDER: u64 = 1 << 14;

    pub const ROOST: u64 = 1 << 15;

    pub const IMPRISON: u64 = 1 << 16;


    pub const GEM: u64 = 1 << 17;

    pub const PROTEAN: u64 = 1 << 18;

    pub const CHARGE: u64 = 1 << 19;


    pub const MOVE_USED: u64 = 1 << 20;

    pub const FOCUSENERGY: u64 = 1 << 21;

    pub const DRAGONCHEER: u64 = 1 << 22;
    pub const DRAGONCHEER_DRAGON: u64 = 1 << 23;

    pub const GLAIVERUSH: u64 = 1 << 24;

    pub const HURT_THIS_TURN: u64 = 1 << 25;

    pub const STATS_RAISED: u64 = 1 << 26;

    pub const QUASHED: u64 = 1 << 27;

    pub const GRAVITY: u64 = 1 << 28;

    pub const ROUND_UP: u64 = 1 << 29;

    pub const INVULNERABLE: u64 = 1 << 30;

    pub const BATON_PASS: u64 = 1 << 31;

    pub const ALLY_SWITCHED: u64 = 1 << 32;

    pub const DRAGGED_IN: u64 = 1 << 33;

    pub const MINIMIZED: u64 = 1 << 34;

    pub const ENDURING: u64 = 1 << 35;

    pub const SMACKED_DOWN: u64 = 1 << 36;

    pub const DRAG_PENDING: u64 = 1 << 37;

    pub const SUB_HIT: u64 = 1 << 38;

    pub const REVIVAL: u64 = 1 << 39;

    pub const DISGUISE_BUSTED: u64 = 1 << 40;

    pub const ITEM_USED: u64 = 1 << 41;

    pub const CHOICE_LOCKED: u64 = 1 << 42;

    pub const ENCORE_REQUEUED: u64 = 1 << 43;


    pub const SELF_SWITCH: u64 = 1 << 45;


    pub const MOVE_CANCELLED: u64 = 1 << 46;

    pub const STATS_LOWERED: u64 = 1 << 47;

    pub const AFTER_YOU: u64 = 1 << 48;

    pub const SPARKLING_ARIA: u64 = 1 << 49;

    pub const AQUA_RING: u64 = 1 << 50;


    pub const INGRAIN: u64 = 1 << 51;

    pub const SALT_CURE: u64 = 1 << 52;

    pub const CURSED: u64 = 1 << 53;


    pub const DESTINY_BOND: u64 = 1 << 54;


    pub const UNBURDEN_LATE: u64 = 1 << 55;

    pub const NO_RETREAT: u64 = 1 << 56;

    pub const TORMENT: u64 = 1 << 57;

    pub const SHED_TAIL: u64 = 1 << 58;


    pub const FOCUSING: u64 = 1 << 59;

    pub const FOCUS_LOST: u64 = 1 << 60;

    pub const BEAK_BLAST: u64 = 1 << 61;

    pub const ELECTRIFIED: u64 = 1 << 62;


    pub const GASTRO_ACID: u64 = 1 << 63;
}


pub mod condition_ids {

    pub const SLOWSTART: u8 = 1;

    pub const TRUANT: u8 = 2;

    pub const ATTRACT: u8 = 3;

    pub const FORESIGHT: u8 = 4;

    pub const MIRACLEEYE: u8 = 5;

    pub const DEFENSECURL: u8 = 6;

    pub const EMBARGO: u8 = 7;

    pub const NIGHTMARE: u8 = 8;

    pub const MAGNITUDE: u8 = 9;

    pub const AUTOTOMIZE: u8 = 10;

    pub const FURYCUTTER: u8 = 11;

    pub const MICLE: u8 = 12;

    pub const TELEKINESIS: u8 = 13;

    pub const RAGE: u8 = 14;

    pub const GRUDGE: u8 = 15;

    pub const NATURALGIFT: u8 = 16;

    pub const FLING: u8 = 17;

    pub const MAGICCOAT: u8 = 18;

    pub const PRESENT: u8 = 19;


    pub const ROLLOUT: u8 = 20;



    pub const FOCUSBAND_DRAW: u8 = 21;

    pub const METRONOME_MOVE: u8 = 22;

    pub const METRONOME: u8 = 23;


    pub const CALLED_PRIORITY: u8 = 24;

    pub const CALLED_SLEEP_USABLE: u8 = 25;

    pub const SNATCH: u8 = 26;

    pub const SNATCHED: u8 = 27;

    pub const INSTRUCTED: u8 = 28;


    pub const STALL: u8 = 29;


    pub const HELPINGHAND_RESTARTS: u8 = 30;


    pub const MEFIRST: u8 = 31;


    pub const MIMIC: u8 = 32;


    pub const BIDE: u8 = 33;


    pub const PLEDGE: u8 = 34;


    pub const SPORTS: u8 = 35;

    pub const POWDER: u8 = 36;


    pub const SKYDROP: u8 = 37;


    pub const SKYDROPPED: u8 = 38;



    pub const SKYDROP_TRACK: u8 = 39;


    pub const SPOTLIGHT: u8 = 40;


    pub const BURNINGBULWARK: u8 = 41;



    pub const PARADOX: u8 = 42;


    pub const LASERFOCUS: u8 = 43;

    pub const TARSHOT: u8 = 44;


    pub const SILKTRAP: u8 = 45;


    pub const SHELLTRAP: u8 = 46;


    pub const OBSTRUCT: u8 = 47;




    pub const GORILLATACTICS: u8 = 48;


    pub const MAXGUARD: u8 = 49;


    pub const GMAXCHISTRIKE: u8 = 50;


    pub const TORMENT_TURNS: u8 = 51;

    pub const BATON_PASSED: [u8; 8] = [EMBARGO, FURYCUTTER, MICLE, TELEKINESIS, RAGE, GRUDGE, LASERFOCUS, TARSHOT];
}




#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Conditions {


    slots: [(u8, u8); 12],
}

impl Conditions {
    fn find(&self, id: u8) -> Option<usize> {
        self.slots.iter().position(|&(c, _)| c == id)
    }
    pub fn has(&self, id: u8) -> bool {
        self.find(id).is_some()
    }

    pub fn turns(&self, id: u8) -> Option<u8> {
        self.find(id).map(|i| self.slots[i].1)
    }


    pub fn add(&mut self, id: u8, turns: u8) -> bool {
        debug_assert!(id != 0);
        if self.has(id) {
            return false;
        }
        let free = self.find(0).expect("timed-condition list full (12): widen it deliberately (decisions 10-22, 10-23)");
        self.slots[free] = (id, turns);
        true
    }

    pub fn set(&mut self, id: u8, turns: u8) {
        match self.find(id) {
            Some(i) => self.slots[i].1 = turns,
            None => {
                self.add(id, turns);
            }
        }
    }

    pub fn remove(&mut self, id: u8) -> bool {
        match self.find(id) {
            Some(i) => {
                self.slots[i] = (0, 0);
                true
            }
            None => false,
        }
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Volatiles {
    pub flags: u64,
    pub conds: Conditions,
}

impl Volatiles {
    pub fn has(&self, bit: u64) -> bool {
        self.flags & bit != 0
    }
    pub fn set(&mut self, bit: u64) {
        self.flags |= bit;
    }
    pub fn clear(&mut self, bit: u64) {
        self.flags &= !bit;
    }




    pub fn clear_turn_scoped(&mut self) {
        self.clear(volatile_flags::FLINCH);
        self.clear(volatile_flags::PROTECTED);
        self.clear(volatile_flags::KINGSSHIELD);
        self.clear(volatile_flags::SPIKYSHIELD);
        self.clear(volatile_flags::BANEFULBUNKER);
        self.conds.remove(condition_ids::BURNINGBULWARK);
        self.conds.remove(condition_ids::SILKTRAP);
        self.conds.remove(condition_ids::OBSTRUCT);
        self.conds.remove(condition_ids::MAXGUARD);
    }
}



#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct MegaState {
    pub active: bool,





    pub base_species: SpeciesId,


    pub base_ability: AbilityId,
}





#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct TeraState {

    pub tera_type: Option<Type>,
    pub active: bool,


    pub base_types: [Option<Type>; 2],

    pub stellar_boosted: u32,


    pub move_boosted: bool,
}

impl TeraState {

    pub fn typed(&self) -> bool {
        self.active && self.tera_type != Some(Type::Stellar)
    }
}



pub mod mon_flags {
    pub const FAINTED: u64 = 1 << 0;

    pub const ACTIVE: u64 = 1 << 1;

    pub const MOVED_THIS_TURN: u64 = 1 << 2;



    pub const ALIVE_AT_HIT_START: u64 = 1 << 3;

    pub const REVEALED: u64 = 1 << 4;


    pub const SEEN_FAINTED: u64 = 1 << 5;


    pub const ILLUSION_EXPOSED: u64 = 1 << 6;



    pub const SELF_DESTRUCTING: u64 = 1 << 7;


    pub const POWER_TRICK: u64 = 1 << 8;


    pub const STATS_SPLIT: u64 = 1 << 9;

    pub const ATE_BERRY: u64 = 1 << 10;

    pub const MAGIC_ROOM: u64 = 1 << 11;

    pub const WONDER_ROOM: u64 = 1 << 12;


    pub const ELECTRIFY_FAILS: u64 = 1 << 13;


    pub const BEAK_BURN_DUE: u64 = 1 << 14;

    pub const FALLEN_SHIFT: u64 = 15;
    pub const FALLEN_MASK: u64 = 0b111 << 15;

    pub const QUICK_CLAW: u64 = 1 << 18;



    pub const BEING_CALLED_BACK: u64 = 1 << 32;


    pub const DEFER_DRAG: u64 = 1 << 33;



    pub const FAINT_MESSAGED: u64 = 1 << 34;


    pub const DRAGGED_OUT: u64 = 1 << 35;


    pub const TOXIC_SURE_HIT: u64 = 1 << 36;


    pub const USING_Z: u64 = 1 << 37;



    pub const LAST_MOVE_Z: u64 = 1 << 39;


    pub const ACTIVE_MOVE_Z: u64 = 1 << 40;


    pub const IGNORES_ABILITIES: u64 = 1 << 38;

    pub const RED_CARD_DRAG: u64 = 1 << 19;

    pub const RED_CARD_HIT: u64 = 1 << 20;


    pub const TRANSFORMED: u64 = 1 << 21;


    pub const TRANSFORM_STASH: u64 = 1 << 22;

    pub const MOVES_LAST: u64 = 1 << 23;

    pub const SYRUP_TRIGGERED: u64 = 1 << 24;


    pub const STALL_SLOW: u64 = 1 << 25;


    pub const USED_ITEM_TURN: u64 = 1 << 26;


    pub const IN_RESIDUAL: u64 = 1 << 27;


    pub const GENDER_SHIFT: u64 = 28;
    pub const GENDER_MASK: u64 = 0b11 << 28;


    const _: () = {
        let bits = [FAINTED, ACTIVE, MOVED_THIS_TURN, ALIVE_AT_HIT_START, REVEALED, SEEN_FAINTED, ILLUSION_EXPOSED, SELF_DESTRUCTING, POWER_TRICK, STATS_SPLIT, ATE_BERRY, MAGIC_ROOM, WONDER_ROOM, ELECTRIFY_FAILS, BEAK_BURN_DUE, QUICK_CLAW, BEING_CALLED_BACK, DEFER_DRAG, FAINT_MESSAGED, DRAGGED_OUT, TOXIC_SURE_HIT, USING_Z, LAST_MOVE_Z, ACTIVE_MOVE_Z, IGNORES_ABILITIES, RED_CARD_DRAG, RED_CARD_HIT, TRANSFORMED, TRANSFORM_STASH, MOVES_LAST, SYRUP_TRIGGERED, STALL_SLOW, USED_ITEM_TURN, IN_RESIDUAL, RUN_SWITCH_PENDING, EJECT_BUTTON_HIT, CURSE_GLITCH, EJECT_PACK, BOOSTER_STARTED, SWORD_BOOST, SHIELD_BOOST, UNNERVED, TERA_SHELL_RESISTED, BERSERK_HOLD, NGAS_SUPPRESSED, NGAS_ENDING, NGAS_LIVE, COMMANDING, COMMANDED, COMMANDED_DROOPY, COMMANDED_STRETCHY, SWITCH_IN_PENDING, FAINT_HISTORY, TRACE_SEEK, BOND_TRIGGERED, GIGANTAMAX, DYNAMAXED, LAST_MOVE_MAX];
        let fields = FALLEN_MASK | GENDER_MASK;
        let mut all = 0u64;
        let mut i = 0;
        while i < bits.len() {
            assert!(bits[i].count_ones() == 1 && bits[i] & fields == 0 && bits[i] & all == 0, "mon_flags: overlapping bits");
            all |= bits[i];
            i += 1;
        }
    };



    pub const RUN_SWITCH_PENDING: u64 = 1 << 30;


    pub const EJECT_BUTTON_HIT: u64 = 1 << 31;


    pub const CURSE_GLITCH: u64 = 1 << 41;



    pub const EJECT_PACK: u64 = 1 << 42;


    pub const BOOSTER_STARTED: u64 = 1 << 43;


    pub const SWORD_BOOST: u64 = 1 << 44;
    pub const SHIELD_BOOST: u64 = 1 << 45;


    pub const TERA_SHELL_RESISTED: u64 = 1 << 47;


    pub const GIGANTAMAX: u64 = 1 << 60;


    pub const DYNAMAXED: u64 = 1 << 61;



    pub const LAST_MOVE_MAX: u64 = 1 << 62;


    pub const BERSERK_HOLD: u64 = 1 << 48;


    pub const NGAS_SUPPRESSED: u64 = 1 << 49;

    pub const NGAS_ENDING: u64 = 1 << 50;

    pub const NGAS_LIVE: u64 = 1 << 51;


    pub const COMMANDING: u64 = 1 << 52;


    pub const COMMANDED: u64 = 1 << 53;


    pub const COMMANDED_DROOPY: u64 = 1 << 54;
    pub const COMMANDED_STRETCHY: u64 = 1 << 55;


    pub const SWITCH_IN_PENDING: u64 = 1 << 56;


    pub const FAINT_HISTORY: u64 = 1 << 57;


    pub const TRACE_SEEK: u64 = 1 << 58;


    pub const UNNERVED: u64 = 1 << 46;


    pub const BOND_TRIGGERED: u64 = 1 << 59;
}


#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum Gender {
    #[default]
    Genderless = 0,
    Male = 1,
    Female = 2,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct MonFlags(pub u64);

impl MonFlags {
    pub fn has(self, bit: u64) -> bool {
        self.0 & bit != 0
    }
    pub fn set(&mut self, bit: u64) {
        self.0 |= bit;
    }
    pub fn clear(&mut self, bit: u64) {
        self.0 &= !bit;
    }
}



#[derive(Clone, Copy, Debug)]
pub struct Mon {
    pub species: SpeciesId,
    pub ability: AbilityId,


    pub base_ability: AbilityId,


    pub suppressed_ability: AbilityId,


    pub base_moves: [MoveId; 4],
    pub base_pp: [u8; 4],
    pub pre_transform_species: SpeciesId,


    pub item: ItemId,
    pub moves: [MoveId; 4],
    pub pp: [u8; 4],
    pub hp: u16,
    pub max_hp: u16,

    pub base_max_hp: u16,

    pub dynamax_level: u8,


    pub dynamax_turns: u8,


    pub regen_hidden: u16,


    pub stats: [u16; 5],





    pub stat_points: [u8; 6],


    pub ivs: [u8; 6],
    pub nature: Nature,

    pub happiness: u8,

    pub boosts: [i8; 7],



    pub mirror_herb: [i8; 7],
    pub status: Status,

    pub status_counter: u8,


    pub sleep_start: u8,
    pub volatiles: Volatiles,




    pub types: [Option<Type>; 3],
    pub mega: MegaState,
    pub tera: TeraState,
    pub flags: MonFlags,









    pub turns_active: u8,














    pub move_actions_since_switch_in: u8,












    pub protect_counter: u16,




    pub throat_chop_turns: u8,



    pub last_move: u16,


    pub last_move_target: u8,


    pub last_move_used_type: Option<engine_data::type_chart::Type>,

    pub bide_damage: u16,


    pub disable_move: u16,

    pub disable_turns: u8,



    pub trap_turns: u8,


    pub trapped_by: u8,



    pub confusion_turns: u8,



    pub charge_target: u8,


    pub charge_move: u16,


    pub encore_move: u16,


    pub encore_target: Option<u8>,


    pub ally_switch_counter: u16,


    pub choice_move: u16,



    pub speed_cache: i64,

    pub ally_switch_turn: u16,

    pub encore_turns: u8,


    pub perish_turns: u8,

    pub taunt_turns: u8,

    pub yawn_turns: u8,

    pub heal_block_turns: u8,

    pub times_attacked: u8,

    pub stockpile_layers: u8,


    pub stockpile_def: i8,
    pub stockpile_spd: i8,

    pub magnet_rise_turns: u8,


    pub leech_seeder: u8,


    pub syrup_turns: u8,
    pub syrup_source: u8,


    pub locked_by: u8,

    pub moves_used: u8,


    pub moves_revealed: u8,


    pub transform_known: u8,


    pub lock_on_target: u8,
    pub lock_on_turns: u8,


    pub hit_by_this_turn: u8,


    pub last_hit_slot: u8,
    pub last_hit_damage: u16,
    pub last_hit_this_turn: bool,


    pub counter_slot: u8,
    pub counter_damage: u16,
    pub mirror_slot: u8,
    pub mirror_damage: u16,


    pub octolock_source: u8,


    pub last_item: ItemId,

    pub cud_berry: ItemId,
    pub cud_counter: u8,


    pub hurt_hp: u16,



    pub lock_move: u16,
    pub lock_turns: u8,
    pub lock_true: u8,

    pub sub_hp: u16,

    pub roost_types: [Option<engine_data::type_chart::Type>; 3],


    pub move_result_this_turn: u8,
    pub move_result_last_turn: u8,


    pub faint_seq: u32,


    pub ability_order: u16,



    pub illusion: Option<u8>,
}



pub(crate) fn next_faint_seq() -> u32 {
    static SEQ: std::sync::atomic::AtomicU32 = std::sync::atomic::AtomicU32::new(0);
    SEQ.fetch_add(1, std::sync::atomic::Ordering::Relaxed)
}



pub mod move_result {
    pub const NONE: u8 = 0;
    pub const SUCCESS: u8 = 1;
    pub const FAILED: u8 = 2;
    pub const NULL: u8 = 3;
}



pub fn max_pp(move_id: MoveId) -> u8 {
    if move_id == 0 {
        return 0;
    }
    let pp = engine_data::moves_table::get(move_id).pp;

    if matches!(move_id, engine_data::moves_table::move_ids::REVIVALBLESSING | engine_data::moves_table::move_ids::SKETCH) {
        pp
    } else {
        (pp / 5 + 1) * 4
    }
}


pub fn full_pp(moves: [MoveId; 4]) -> [u8; 4] {
    moves.map(max_pp)
}

impl Mon {
    pub fn gender(&self) -> Gender {
        match (self.flags.0 & mon_flags::GENDER_MASK) >> mon_flags::GENDER_SHIFT {
            1 => Gender::Male,
            2 => Gender::Female,
            _ => Gender::Genderless,
        }
    }

    pub fn set_gender(&mut self, gender: Gender) {
        self.flags.0 = (self.flags.0 & !mon_flags::GENDER_MASK) | ((gender as u64) << mon_flags::GENDER_SHIFT);
    }




    pub fn unmimic(&mut self) {
        let Some(v) = self.volatiles.conds.turns(condition_ids::MIMIC) else {
            return;
        };
        self.volatiles.conds.remove(condition_ids::MIMIC);
        let (slot, pp) = ((v & 3) as usize, v >> 2);
        let mimic = engine_data::moves_table::move_ids::MIMIC;
        if self.flags.has(mon_flags::TRANSFORMED) {
            (self.base_moves[slot], self.base_pp[slot]) = (mimic, pp);
        } else {
            (self.moves[slot], self.pp[slot]) = (mimic, pp);
            self.moves_used |= 1 << slot;
        }
    }



    pub fn untransform(&mut self, rules: &crate::rules::Rules) {
        self.flags.clear(mon_flags::TRANSFORM_STASH);
        if !self.flags.has(mon_flags::TRANSFORMED) {
            return;
        }
        self.flags.clear(mon_flags::TRANSFORMED);
        self.moves = self.base_moves;
        self.pp = self.base_pp;
        self.untransform_species(rules);
    }



    pub fn untransform_on_faint(&mut self, rules: &crate::rules::Rules) {
        if !self.flags.has(mon_flags::TRANSFORMED) {
            return;
        }
        let transformed = self.moves;
        self.untransform(rules);
        self.base_moves = transformed;
        self.flags.set(mon_flags::TRANSFORM_STASH);
    }

    fn untransform_species(&mut self, rules: &crate::rules::Rules) {
        self.species = self.pre_transform_species;
        let data = rules.species_data(self.species);
        self.set_species_types(species_types_for(rules, self.species, self.ability, self.item));
        self.recalc_stats(rules, data.base_stats);
    }



    pub fn set_species_types(&mut self, types: [Option<Type>; 3]) {
        if self.tera.typed() {
            self.tera.base_types = [types[0], types[1]];
            self.types = [self.tera.tera_type, None, None];
        } else {
            self.types = types;
        }
    }


    pub fn end_tera(&mut self) {
        if self.tera.typed() {
            self.types = [self.tera.base_types[0], self.tera.base_types[1], None];
        }
        self.tera.active = false;
    }

    pub fn is_fainted(&self) -> bool {
        self.flags.has(mon_flags::FAINTED) || self.hp == 0
    }






    pub fn effective_item(&self) -> ItemId {
        use engine_data::items_table::item_ids;
        let ignores_klutz = matches!(
            self.item,
            item_ids::MACHOBRACE
                | item_ids::POWERANKLET
                | item_ids::POWERBAND
                | item_ids::POWERBELT
                | item_ids::POWERBRACER
                | item_ids::POWERLENS
                | item_ids::POWERWEIGHT
                | item_ids::ABILITYSHIELD
        );

        if (self.ability == engine_data::abilities_table::ability_ids::KLUTZ && !ignores_klutz)
            || self.flags.has(mon_flags::MAGIC_ROOM)
            || self.volatiles.conds.has(condition_ids::EMBARGO)
        {
            crate::ids::NONE_ID
        } else {
            self.item
        }
    }



    pub fn ignoring_item(&self) -> bool {
        self.flags.has(mon_flags::MAGIC_ROOM)
            || self.volatiles.conds.has(condition_ids::EMBARGO)
            || (self.ability == engine_data::abilities_table::ability_ids::KLUTZ
                && (self.item == crate::ids::NONE_ID || self.effective_item() == crate::ids::NONE_ID))
    }









    pub fn recalc_stats(&mut self, rules: &crate::rules::Rules, base_stats: [u16; 6]) {
        let stat_at = |stat: Stat| {
            let i = 1 + stat as usize;
            rules.stat(stat, base_stats[i] as u32, self.stat_points[i] as u32, self.ivs[i] as u32, self.nature) as u16
        };
        self.stats = [stat_at(Stat::Atk), stat_at(Stat::Def), stat_at(Stat::SpA), stat_at(Stat::SpD), stat_at(Stat::Spe)];


        self.speed_cache = self.stats[Stat::Spe as usize] as i64;

        let new_base_max_hp = rules.hp(base_stats[0] as u32, self.stat_points[0] as u32, self.ivs[0] as u32) as u16;
        if new_base_max_hp != self.base_max_hp {




            self.base_max_hp = new_base_max_hp;
            let new_max_hp = if self.flags.has(mon_flags::DYNAMAXED) { new_base_max_hp.saturating_mul(2) } else { new_base_max_hp };
            if self.hp > 0 {
                let damage_taken = self.max_hp.saturating_sub(self.hp);
                self.hp = new_max_hp.saturating_sub(damage_taken).max(1);
            }
            self.max_hp = new_max_hp;
        }
    }
}


pub fn species_types(types: [Option<Type>; 2]) -> [Option<Type>; 3] {
    [types[0], types[1], None]
}







pub fn species_types_for(
    rules: &crate::rules::Rules,
    species: engine_data::species_table::SpeciesId,
    ability: engine_data::abilities_table::AbilityId,
    item: engine_data::items_table::ItemId,
) -> [Option<Type>; 3] {
    use engine_data::abilities_table::ability_ids;
    use engine_data::species_table::species_ids::{ARCEUS, ARCEUSWATER, SILVALLY, SILVALLYWATER};
    let own = if (ARCEUS..=ARCEUSWATER).contains(&species) {
        ability == ability_ids::MULTITYPE
    } else if (SILVALLY..=SILVALLYWATER).contains(&species) {
        ability == ability_ids::RKSSYSTEM
    } else {
        return species_types(rules.species_data(species).types);
    };
    if own && ability == ability_ids::RKSSYSTEM {
        [Some(crate::items::memory_type(item).unwrap_or(Type::Normal)), None, None]
    } else if own && ability == ability_ids::MULTITYPE {
        [Some(crate::items::plate_type(item).unwrap_or(Type::Normal)), None, None]
    } else if own || rules.type_formes_normal_without_ability {
        [Some(Type::Normal), None, None]
    } else {
        species_types(rules.species_data(species).types)
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn conditions_add_is_a_no_op_when_present_and_remove_reports() {
        let mut c = Conditions::default();
        assert!(c.add(condition_ids::SLOWSTART, 5));
        assert!(!c.add(condition_ids::SLOWSTART, 2), "addVolatile on a present condition does nothing");
        assert_eq!(c.turns(condition_ids::SLOWSTART), Some(5));
        c.set(condition_ids::SLOWSTART, 4);
        assert_eq!(c.turns(condition_ids::SLOWSTART), Some(4));
        assert!(!c.has(condition_ids::TRUANT));
        assert!(c.remove(condition_ids::SLOWSTART));
        assert!(!c.remove(condition_ids::SLOWSTART));
        assert_eq!(c, Conditions::default(), "a removed condition frees its slot");
    }

    #[test]
    #[should_panic(expected = "timed-condition list full")]
    fn a_thirteenth_condition_fails_loudly() {
        let mut c = Conditions::default();
        for id in 1..=13u8 {
            c.add(id, 0);
        }
    }
}
