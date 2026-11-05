



use crate::battle::Battle;
use crate::event::EventRing;
use crate::field::Field;
use crate::ids::NONE_ID;
use crate::mon::{Gender, MegaState, Mon, MonFlags, Volatiles};
use crate::pending::Pending;
use crate::rng::Rng;
use crate::side::{Side, SideConds};
use crate::stats::{Nature, Stat};
use crate::status::Status;
use engine_data::abilities_table::{self, AbilityId};
use engine_data::items_table::{self, ItemId};
use engine_data::moves_table::{self, MoveId};
use engine_data::species_table::{self, SpeciesId};
use engine_data::support_table;


#[derive(Clone, Copy, Debug, PartialEq, Eq)]
pub struct MonSet {
    pub species: SpeciesId,

    pub ability: AbilityId,
    pub item: ItemId,
    pub moves: [MoveId; 4],
    pub nature: Nature,

    pub stat_points: [u8; 6],

    pub ivs: [u8; 6],

    pub gender: SetGender,

    pub happiness: u8,

    pub tera_type: Option<engine_data::type_chart::Type>,

    pub dynamax_level: u8,

    pub gigantamax: bool,
}






#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum SetGender {
    #[default]
    Unspecified,
    Male,
    Female,
    Genderless,
}




pub fn hidden_power(ivs: [u8; 6]) -> (engine_data::type_chart::Type, u8) {
    use engine_data::type_chart::Type::*;
    const TYPES: [engine_data::type_chart::Type; 16] =
        [Fighting, Flying, Poison, Ground, Rock, Bug, Ghost, Steel, Fire, Water, Grass, Electric, Psychic, Ice, Dragon, Dark];
    let showdown_order = [ivs[0], ivs[1], ivs[2], ivs[5], ivs[3], ivs[4]];
    let (mut t, mut p) = (0u32, 0u32);
    for (i, &iv) in showdown_order.iter().enumerate() {
        t += (1 << i) * (iv as u32 % 2);
        p += (1 << i) * ((iv as u32 / 2) % 2);
    }
    (TYPES[(t * 15 / 63) as usize], (p * 40 / 63 + 30) as u8)
}


pub fn resolve_gender(set: SetGender, species: SpeciesId) -> Gender {
    use species_table::SpeciesGender;
    match set {
        SetGender::Male => Gender::Male,
        SetGender::Female => Gender::Female,
        SetGender::Genderless => Gender::Genderless,
        SetGender::Unspecified => match species_table::get(species).gender {
            SpeciesGender::Male => Gender::Male,
            SpeciesGender::Female => Gender::Female,
            SpeciesGender::Genderless | SpeciesGender::Mixed => Gender::Genderless,
        },
    }
}


pub fn unsupported(set: &MonSet) -> Option<String> {
    let ability = if set.ability == NONE_ID { species_table::get(set.species).abilities[0] } else { set.ability };
    if !support_table::ability_supported(ability) {
        return Some(format!("ability {} isn't implemented", abilities_table::name(ability)));
    }
    if set.item != NONE_ID && !support_table::item_supported(set.item) {
        return Some(format!("item {} isn't implemented", items_table::name(set.item)));
    }

    if let Some(&m) = set.moves.iter().find(|&&m| m != NONE_ID && !moves_table::ported(m)) {
        return Some(format!("move {} isn't implemented", moves_table::name(m)));
    }


    if let Some(mega) = crate::items::mega_forme(set.item, set.species, &set.moves, true) {
        let mega_ability = species_table::get(mega).abilities[0];
        if !support_table::ability_supported(mega_ability) {
            return Some(format!("its Mega forme's ability {} isn't implemented", abilities_table::name(mega_ability)));
        }
    }
    None
}





pub fn build_mon(set: &MonSet) -> Mon {
    build_mon_in(crate::rules::Rules::of(crate::rules::Format::ChampionsMC), set)
}


pub fn build_mon_in(rules: &crate::rules::Rules, set: &MonSet) -> Mon {
    if let Some(what) = unsupported(set) {
        panic!("unsupported set: {what}");
    }

    if rules.terastallization
        && species_table::get(set.species).name.starts_with("Terapagos")
        && set.tera_type.is_some_and(|t| t != engine_data::type_chart::Type::Stellar)
    {
        panic!("unsupported set: {} can only Terastallize into Stellar", species_table::get(set.species).name);
    }


    if rules.terastallization {
        if let Some((_, own)) = crate::turn::ogerpon_tera(set.species) {
            if set.tera_type.is_some_and(|t| t != own) {
                panic!("unsupported set: {} can only Terastallize into {:?}", species_table::get(set.species).name, own);
            }
        }
    }
    let data = rules.species_data(set.species);
    let (pts, ivs) = (set.stat_points, set.ivs);
    let stat_at = |stat: Stat| {
        let i = 1 + stat as usize;
        rules.stat(stat, data.base_stats[i] as u32, pts[i] as u32, ivs[i] as u32, set.nature) as u16
    };

    let hp = if data.fixed_max_hp != 0 { data.fixed_max_hp } else { rules.hp(data.base_stats[0] as u32, pts[0] as u32, ivs[0] as u32) as u16 };
    Mon {
        species: set.species,
        ability: if set.ability == NONE_ID { data.abilities[0] } else { set.ability },
        base_ability: NONE_ID,
        suppressed_ability: NONE_ID,
        base_moves: [NONE_ID; 4],
        base_pp: [0; 4],
        pre_transform_species: NONE_ID,
        item: set.item,
        moves: set.moves,
        pp: rules.full_pp(set.moves),
        hp,
        max_hp: hp,
        base_max_hp: hp,
        dynamax_level: set.dynamax_level,
        dynamax_turns: 0,
        regen_hidden: 0,
        stats: [stat_at(Stat::Atk), stat_at(Stat::Def), stat_at(Stat::SpA), stat_at(Stat::SpD), stat_at(Stat::Spe)],
        stat_points: pts,
        ivs,
        nature: set.nature,
        boosts: [0; 7],
        mirror_herb: [0; 7],
        status: Status::None,
        status_counter: 0,
        sleep_start: 0,
        volatiles: Volatiles::default(),
        happiness: set.happiness,
        types: crate::mon::species_types_for(rules, set.species, if set.ability == NONE_ID { data.abilities[0] } else { set.ability }, set.item),
        mega: MegaState::default(),
        tera: crate::mon::TeraState {
            tera_type: rules.terastallization.then(|| set.tera_type.or(data.types[0])).flatten(),
            ..Default::default()
        },
        flags: MonFlags(
            (resolve_gender(set.gender, set.species) as u64) << crate::mon::mon_flags::GENDER_SHIFT
                | if set.gigantamax { crate::mon::mon_flags::GIGANTAMAX } else { 0 },
        ),
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


pub fn build_side(mons: [Mon; 4]) -> Side {
    Side { mons, active: [0, 1, crate::side::NO_PHANTOM], side_conditions: SideConds::default(), mega_used: false, z_used: false, ultra_used: false, tera_used: false, dynamax_used: false, revivals: 0, order: [0, 1, 2, 3] }
}



pub fn new_battle(sides: [Side; 2], seed: u64) -> Battle {
    new_battle_in(crate::rules::Format::ChampionsMC, sides, seed)
}


pub fn new_battle_in(format: crate::rules::Format, sides: [Side; 2], seed: u64) -> Battle {
    let mut battle = Battle {
        sides,
        field: Field::default(),
        turn: 0,
        rng: Rng::new(seed),
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
    crate::turn::start_battle(&mut battle);
    battle
}

#[cfg(test)]
mod tests {
    use super::*;
    use engine_data::abilities_table::ability_ids;
    use engine_data::moves_table::move_ids;
    use engine_data::species_table::species_ids;

    fn set(species: SpeciesId, ability: AbilityId, item: ItemId, moves: [MoveId; 4]) -> MonSet {
        MonSet { species, ability, item, moves, nature: Nature::neutral(), ivs: [31; 6], stat_points: [0; 6], gender: SetGender::Unspecified, happiness: 255, tera_type: None, dynamax_level: 10, gigantamax: false }
    }

    #[test]
    fn hidden_power_from_ivs() {
        use engine_data::type_chart::Type;


        assert_eq!(hidden_power([31; 6]), (Type::Dark, 70));
        assert_eq!(hidden_power([31, 2, 31, 30, 31, 30]).0, Type::Fire);
        assert_eq!(hidden_power([31, 30, 30, 31, 31, 31]), (Type::Ice, 70));
        assert_eq!(hidden_power([0; 6]), (Type::Fighting, 30));
    }

    #[test]
    fn catalog_entries_are_data_only_until_ported() {

        let ok = set(species_ids::BULBASAUR, ability_ids::CHLOROPHYLL, NONE_ID, [move_ids::TACKLE, move_ids::PROTECT, 0, 0]);
        assert_eq!(unsupported(&ok), None);


        let unported = (1..=moves_table::MOVE_COUNT as MoveId).find(|&m| !moves_table::ported(m)).expect("an unported move");
        let mv = set(species_ids::BULBASAUR, ability_ids::CHLOROPHYLL, NONE_ID, [move_ids::TACKLE, unported, 0, 0]);
        assert_eq!(unsupported(&mv), Some(format!("move {} isn't implemented", moves_table::name(unported))));

        if let Some(&unported_ability) = engine_data::support_table::UNPORTED_ABILITIES.first() {
            let ab = set(species_ids::BULBASAUR, unported_ability, NONE_ID, [move_ids::TACKLE, 0, 0, 0]);
            assert_eq!(unsupported(&ab), Some(format!("ability {} isn't implemented", engine_data::abilities_table::name(unported_ability))));
        }
        let unported_item = engine_data::support_table::UNPORTED_ITEMS[0];
        let it = set(species_ids::BULBASAUR, ability_ids::CHLOROPHYLL, unported_item, [move_ids::TACKLE, 0, 0, 0]);
        assert_eq!(unsupported(&it), Some(format!("item {} isn't implemented", engine_data::items_table::name(unported_item))));
    }
}
