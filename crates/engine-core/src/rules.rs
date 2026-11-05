










use engine_data::type_chart::Type;


#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Format {

    #[default]
    ChampionsMC = 0,

    Gen5Vgc13 = 1,


    Gen6Vgc = 2,


    Gen7Vgc = 3,


    Gen9Sv = 4,


    Gen9SvPreDlc = 5,


    Gen8Vgc = 6,
}

impl Format {

    pub fn from_id(id: &str) -> Option<Format> {
        match id {
            "gen9championsvgc2026regmc" | "gen9championsvgc2026regmcbo3" => Some(Format::ChampionsMC),
            "gen5vgc2013" => Some(Format::Gen5Vgc13),
            "gen6vgc2014" | "gen6vgc2015" | "gen6vgc2016" => Some(Format::Gen6Vgc),
            "gen7vgc2017" | "gen7vgc2018" | "gen7vgc2019" => Some(Format::Gen7Vgc),
            "gen9vgc2024regg" | "gen9vgc2025regi" => Some(Format::Gen9Sv),
            "gen9vgc2023regc" | "gen9vgc2023regd" => Some(Format::Gen9SvPreDlc),
            "gen8vgc2020" | "gen8vgc2021" | "gen8vgc2022" => Some(Format::Gen8Vgc),
            _ => None,
        }
    }
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum SleepLength {

    ChampionsSample,

    TwoToFour,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum StatFormula {

    ChampionsPoints,

    EvIv { level: u8 },
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum PpFormula {

    Champions,

    ThreePpUps,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Normalize {


    Ate,


    TypeOnly,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Conversion {

    FirstSlot,

    RandomMoveType,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum NaturePower {

    ByTerrain,

    Earthquake,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Camouflage {

    ByTerrain,

    Ground,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum CurseTarget {

    User,

    RandomFoe,



    RandomNormal,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct AbilityRules {

    pub snow_warning: crate::field::Weather,

    pub frisk_one_random_foe: bool,

    pub weak_armor_speed: i8,
    pub normalize: Normalize,

    pub heatproof_halves_base_power: bool,



    pub slow_start_data_category: bool,

    pub run_away_escapes_trapping: bool,

    pub healer_chance: (u8, u8),

    pub moody_accuracy_evasion: bool,



    pub sheer_force_skips_after_move_secondary: bool,


    pub intimidate_ability_reactions: bool,


    pub oblivious_blocks_taunt: bool,

    pub keen_eye_ignores_evasion: bool,

    pub illuminate_active: bool,


    pub protosynthesis_holds_suppressed_sun: bool,


    pub ate_modifier: (u16, u16),

    pub parental_bond_second_hit: (u8, u8),

    pub gale_wings_needs_full_hp: bool,

    pub protean_once_per_switch_in: bool,


    pub stance_change_before_move: bool,


    pub soundproof_blocks_own_moves: bool,


    pub symbiosis_skips_switching_ally: bool,


    pub disguise_bust_costs_hp: bool,


    pub disguise_forme_regression: bool,


    pub battle_bond_forme_change: bool,

    pub transistor_modifier: (u16, u16),


    pub sword_shield_every_switch_in: bool,


    pub emergency_exit_clears_switches: bool,


    pub unseen_fist_strips_protect_flag: bool,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct ItemRules {

    pub gem_modifier: (u16, u16),


    pub confusion_berry_pinch: (u8, u8),
    pub confusion_berry_heal: (u8, u8),


    pub life_orb_modern: bool,


    pub eject_button_cancels_user_switch: bool,


    pub jaboca_needs_standing_attacker: bool,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct MoveEffectRules {


    pub screen_doubles_modifier: (u16, u16),


    pub after_hit_needs_user_hp: bool,

    pub knock_off_boost: bool,
    pub conversion: Conversion,
    pub camouflage: Camouflage,
    pub nature_power: NaturePower,

    pub howl_boosts_ally: bool,
    pub curse_target: CurseTarget,

    pub guards_roll_stall: bool,


    pub sheer_cold_ice_rules: bool,

    pub poison_toxic_sure_hit: bool,



    pub poison_toxic_sure_hit_after_events: bool,

    pub wide_guard_blocks_status: bool,


    pub quick_guard_base_priority: bool,


    pub first_turn_moves_disabled: bool,


    pub berry_moves_disabled: bool,


    pub salt_cure_divisors: (u8, u8),


    pub disable_spares_cant_use_twice: bool,


    pub times_attacked_resets_on_switch: bool,



    pub encore_requeues_at_start: bool,


    pub modern_break_protect: bool,

    pub incinerate_burns_gems: bool,

    pub fury_cutter_max_mult: u8,


    pub healing_wish_waits_for_need: bool,

    pub ally_switch_stalls: bool,

    pub defog_clears_both_sides: bool,

    pub defog_clears_terrain: bool,

    pub psych_up_copies_crit_volatiles: bool,

    pub teleport_switches: bool,

    pub destiny_bond_fails_in_a_row: bool,


    pub curse_retargets_own_side: bool,


    pub curse_self_hit_retargets: bool,


    pub heal_bell_respects_abilities: bool,


    pub heal_bell_user_soundproof: bool,

    pub stockpile_tracks_actual_boosts: bool,


    pub sports_are_volatiles: bool,

    pub kings_shield_attack_drop: i8,


    pub terrain_boost: (u16, u16),

    pub misty_terrain_blocks_confusion: bool,

    pub fell_stinger_boost: i8,


    pub boost_needs_foes_left: bool,


    pub parting_shot_needs_drops: bool,


    pub choice_lock_fails_other_moves: bool,


    pub charge_ends_on_any_move: bool,


    pub weather_event_updates: bool,


    pub secondary_chance_overflow: bool,
}


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Rules {


    pub moves: &'static [engine_data::moves_table::MoveData; engine_data::moves_table::MOVE_COUNT],


    pub species: &'static [engine_data::species_table::SpeciesData; engine_data::species_table::SPECIES_COUNT],

    pub type_chart: &'static [[u8; engine_data::type_chart::TYPE_COUNT]; engine_data::type_chart::TYPE_COUNT],

    pub type_order: &'static [Type],

    pub metronome_pool: &'static [u16],


    pub fling_power: &'static [u8; engine_data::items_table::ITEM_COUNT],
    pub natural_gift: &'static [Option<(Type, u8)>; engine_data::items_table::ITEM_COUNT],


    pub stat_formula: StatFormula,


    pub open_team_sheets: bool,



    pub preview_shows_items: bool,


    pub shown_hp_scale: u16,


    pub shown_hp_rounds_up: bool,
    pub pp_formula: PpFormula,




    pub crit_mult: [u8; 6],
    pub crit_stage_max: u8,

    pub crit_modifier: (u8, u8),


    pub type_immunity_before_try_hit: bool,



    pub full_paralysis: (u8, u8),

    pub paralysis_speed_percent: u8,
    pub sleep_length: SleepLength,

    pub sleep_resets_on_switch_in: bool,

    pub thaw_chance: (u8, u8),

    pub freeze_timer: bool,

    pub burn_divisor: u8,

    pub burn_spares_facade: bool,


    pub confusion_roll: (u8, u8),
    pub confusion_hits_on_success: bool,


    pub partial_trap_divisor: (u8, u8),


    pub stall_base: u16,
    pub stall_factor: u16,
    pub stall_max: u16,


    pub modern_type_immunities: bool,

    pub prankster_dark_immunity: bool,


    pub type_formes_normal_without_ability: bool,

    pub skill_swap_fails_same_ability: bool,





    pub dynamic_speed: bool,




    pub mega_resort: bool,


    pub terastallization: bool,


    pub dynamax: bool,


    pub dragon_ascent_mega: bool,


    pub trick_room_speed_underflow: bool,


    pub permanent_ability_weather: bool,


    pub mega_reverts_on_faint: bool,



    pub instafaint_punish: bool,

    pub dark_void_darkrai_only: bool,

    pub sky_drop_weight_limit: bool,



    pub ability_flag_overrides: &'static [(engine_data::abilities_table::AbilityId, u8)],


    pub min_damage_before_final_modifiers: bool,


    pub ally_or_self_keeps_fainted_ally: bool,


    pub abilities: AbilityRules,
    pub items: ItemRules,
    pub move_effects: MoveEffectRules,
}


const TYPE_ORDER_CHAMPIONS: [Type; 19] = [
    Type::Bug, Type::Dark, Type::Dragon, Type::Electric, Type::Fairy, Type::Fighting, Type::Fire, Type::Flying, Type::Ghost, Type::Grass,
    Type::Ground, Type::Ice, Type::Normal, Type::Poison, Type::Psychic, Type::Rock, Type::Steel, Type::Stellar, Type::Water,
];

const TYPE_ORDER_GEN6: [Type; 18] = [
    Type::Dark, Type::Bug, Type::Dragon, Type::Electric, Type::Fairy, Type::Fighting, Type::Fire, Type::Flying, Type::Ghost, Type::Grass,
    Type::Ground, Type::Ice, Type::Normal, Type::Poison, Type::Psychic, Type::Rock, Type::Steel, Type::Water,
];

const TYPE_ORDER_GEN7: [Type; 18] = [
    Type::Bug, Type::Dark, Type::Dragon, Type::Electric, Type::Fairy, Type::Fighting, Type::Fire, Type::Flying, Type::Ghost, Type::Grass,
    Type::Ground, Type::Ice, Type::Normal, Type::Poison, Type::Psychic, Type::Rock, Type::Steel, Type::Water,
];

const TYPE_ORDER_GEN5: [Type; 17] = [
    Type::Electric, Type::Ghost, Type::Grass, Type::Steel, Type::Dark, Type::Bug, Type::Dragon, Type::Fighting, Type::Fire, Type::Flying,
    Type::Ground, Type::Ice, Type::Normal, Type::Poison, Type::Psychic, Type::Rock, Type::Water,
];

impl Rules {

    pub fn ability_has_flag(&self, ability: engine_data::abilities_table::AbilityId, flag: u8) -> bool {
        engine_data::abilities_table::has_flag_in(self.ability_flag_overrides, ability, flag)
    }

    pub const CHAMPIONS_MC: Rules = Rules {
        moves: &engine_data::moves_table::MOVES,
        species: &engine_data::species_table::SPECIES,
        type_chart: &engine_data::type_chart::TYPE_CHART,
        type_order: &TYPE_ORDER_CHAMPIONS,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_CHAMPIONS_MC,
        fling_power: &engine_data::items_table::FLING_POWER,
        natural_gift: &engine_data::items_table::NATURAL_GIFT,
        stat_formula: StatFormula::ChampionsPoints,
        open_team_sheets: true,
        preview_shows_items: true,
        shown_hp_scale: 100,
        shown_hp_rounds_up: false,
        pp_formula: PpFormula::Champions,
        crit_mult: [0, 24, 8, 2, 1, 1],
        crit_stage_max: 4,
        crit_modifier: (3, 2),
        type_immunity_before_try_hit: false,
        full_paralysis: (1, 8),
        paralysis_speed_percent: 50,
        sleep_length: SleepLength::ChampionsSample,
        sleep_resets_on_switch_in: false,
        thaw_chance: (1, 4),
        freeze_timer: true,
        burn_divisor: 16,
        burn_spares_facade: true,
        confusion_roll: (33, 100),
        confusion_hits_on_success: true,
        partial_trap_divisor: (8, 6),
        stall_base: 3,
        stall_factor: 3,
        stall_max: 729,
        modern_type_immunities: true,
        prankster_dark_immunity: true,
        type_formes_normal_without_ability: false,
        skill_swap_fails_same_ability: false,
        dynamic_speed: true,
        mega_resort: false,
        terastallization: false,
        dynamax: false,
        dragon_ascent_mega: false,
        trick_room_speed_underflow: false,
        permanent_ability_weather: false,
        mega_reverts_on_faint: false,
        instafaint_punish: false,
        dark_void_darkrai_only: true,
        sky_drop_weight_limit: true,
        ability_flag_overrides: &[],
        min_damage_before_final_modifiers: false,
        ally_or_self_keeps_fainted_ally: false,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Snow,
            frisk_one_random_foe: false,
            weak_armor_speed: 2,
            normalize: Normalize::Ate,
            heatproof_halves_base_power: false,
            slow_start_data_category: false,
            run_away_escapes_trapping: true,
            healer_chance: (1, 2),
            moody_accuracy_evasion: false,
            sheer_force_skips_after_move_secondary: false,
            intimidate_ability_reactions: true,
            oblivious_blocks_taunt: true,
            keen_eye_ignores_evasion: true,
            illuminate_active: true,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (4915, 4096),
            parental_bond_second_hit: (1, 4),
            gale_wings_needs_full_hp: true,
            protean_once_per_switch_in: true,
            stance_change_before_move: false,
            soundproof_blocks_own_moves: false,
            symbiosis_skips_switching_ally: true,
            disguise_bust_costs_hp: true,
            disguise_forme_regression: false,
            battle_bond_forme_change: false,
            transistor_modifier: (5325, 4096),
            sword_shield_every_switch_in: false,
            emergency_exit_clears_switches: false,
            unseen_fist_strips_protect_flag: false,
        },
        items: ItemRules { gem_modifier: (5325, 4096), confusion_berry_pinch: (1, 4), confusion_berry_heal: (1, 3), life_orb_modern: true, eject_button_cancels_user_switch: false, jaboca_needs_standing_attacker: true },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2732, 4096),
            after_hit_needs_user_hp: false,
            knock_off_boost: true,
            conversion: Conversion::FirstSlot,
            camouflage: Camouflage::ByTerrain,
            nature_power: NaturePower::ByTerrain,
            howl_boosts_ally: true,
            curse_target: CurseTarget::User,
            guards_roll_stall: false,
            poison_toxic_sure_hit: true,
            poison_toxic_sure_hit_after_events: false,
            sheer_cold_ice_rules: true,
            wide_guard_blocks_status: true,
            quick_guard_base_priority: false,
            first_turn_moves_disabled: true,
            berry_moves_disabled: false,
            salt_cure_divisors: (16, 8),
            disable_spares_cant_use_twice: true,
            times_attacked_resets_on_switch: true,
            encore_requeues_at_start: true,
            modern_break_protect: true,
            incinerate_burns_gems: true,
            fury_cutter_max_mult: 4,
            healing_wish_waits_for_need: true,
            ally_switch_stalls: true,
            defog_clears_both_sides: true,
            defog_clears_terrain: true,
            psych_up_copies_crit_volatiles: true,
            teleport_switches: true,
            destiny_bond_fails_in_a_row: true,
            curse_retargets_own_side: true,
            curse_self_hit_retargets: true,
            heal_bell_respects_abilities: true,
            heal_bell_user_soundproof: false,
            stockpile_tracks_actual_boosts: true,
            sports_are_volatiles: false,
            kings_shield_attack_drop: -1,
            terrain_boost: (5325, 4096),
            misty_terrain_blocks_confusion: true,
            fell_stinger_boost: 3,
            boost_needs_foes_left: true,
            parting_shot_needs_drops: true,
            choice_lock_fails_other_moves: true,
            charge_ends_on_any_move: false,
            weather_event_updates: true,
            secondary_chance_overflow: false,
        },
    };

    pub const GEN5_VGC13: Rules = Rules {
        moves: &engine_data::moves_table::MOVES_GEN5,
        species: &engine_data::species_table::SPECIES_GEN5,
        type_chart: &engine_data::type_chart::TYPE_CHART_GEN5,
        type_order: &TYPE_ORDER_GEN5,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN5_VGC13,
        fling_power: &engine_data::items_table::FLING_POWER_GEN5,
        natural_gift: &engine_data::items_table::NATURAL_GIFT_GEN5,
        stat_formula: StatFormula::EvIv { level: 50 },
        open_team_sheets: false,
        preview_shows_items: true,
        shown_hp_scale: 48,
        shown_hp_rounds_up: false,
        pp_formula: PpFormula::ThreePpUps,
        crit_mult: [0, 16, 8, 4, 3, 2],
        crit_stage_max: 5,
        crit_modifier: (2, 1),
        type_immunity_before_try_hit: true,
        full_paralysis: (1, 4),
        paralysis_speed_percent: 25,
        sleep_length: SleepLength::TwoToFour,
        sleep_resets_on_switch_in: true,
        thaw_chance: (1, 5),
        freeze_timer: false,
        burn_divisor: 8,
        burn_spares_facade: false,
        confusion_roll: (1, 2),
        confusion_hits_on_success: false,
        partial_trap_divisor: (16, 8),
        stall_base: 2,
        stall_factor: 2,
        stall_max: 256,
        modern_type_immunities: false,
        prankster_dark_immunity: false,
        type_formes_normal_without_ability: true,
        skill_swap_fails_same_ability: true,
        dynamic_speed: false,
        mega_resort: false,
        terastallization: false,
        dynamax: false,
        dragon_ascent_mega: false,
        trick_room_speed_underflow: true,
        permanent_ability_weather: true,
        mega_reverts_on_faint: false,
        instafaint_punish: true,
        dark_void_darkrai_only: false,
        sky_drop_weight_limit: false,
        ability_flag_overrides: engine_data::abilities_table::ABILITY_FLAG_OVERRIDES_GEN5,
        min_damage_before_final_modifiers: true,
        ally_or_self_keeps_fainted_ally: true,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Hail,
            frisk_one_random_foe: true,
            weak_armor_speed: 1,
            normalize: Normalize::TypeOnly,
            heatproof_halves_base_power: true,
            slow_start_data_category: true,
            run_away_escapes_trapping: false,
            healer_chance: (3, 10),
            moody_accuracy_evasion: true,
            sheer_force_skips_after_move_secondary: true,
            intimidate_ability_reactions: false,
            oblivious_blocks_taunt: false,
            keen_eye_ignores_evasion: false,
            illuminate_active: false,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (4915, 4096),
            parental_bond_second_hit: (1, 4),
            gale_wings_needs_full_hp: true,
            protean_once_per_switch_in: true,
            stance_change_before_move: false,
            soundproof_blocks_own_moves: true,
            symbiosis_skips_switching_ally: true,

            disguise_bust_costs_hp: false,
            disguise_forme_regression: true,
            battle_bond_forme_change: true,
            transistor_modifier: (6144, 4096),
            sword_shield_every_switch_in: true,
            emergency_exit_clears_switches: true,
            unseen_fist_strips_protect_flag: true,
        },
        items: ItemRules { gem_modifier: (6144, 4096), confusion_berry_pinch: (1, 2), confusion_berry_heal: (1, 8), life_orb_modern: false, eject_button_cancels_user_switch: true, jaboca_needs_standing_attacker: false },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2703, 4096),
            after_hit_needs_user_hp: true,
            knock_off_boost: false,
            conversion: Conversion::RandomMoveType,
            camouflage: Camouflage::Ground,
            nature_power: NaturePower::Earthquake,
            howl_boosts_ally: false,
            curse_target: CurseTarget::RandomFoe,
            guards_roll_stall: true,
            poison_toxic_sure_hit: false,
            poison_toxic_sure_hit_after_events: false,
            sheer_cold_ice_rules: false,
            wide_guard_blocks_status: false,
            quick_guard_base_priority: true,
            first_turn_moves_disabled: false,
            berry_moves_disabled: false,
            salt_cure_divisors: (8, 4),
            disable_spares_cant_use_twice: false,
            times_attacked_resets_on_switch: false,
            encore_requeues_at_start: false,
            modern_break_protect: false,
            incinerate_burns_gems: false,
            fury_cutter_max_mult: 8,
            healing_wish_waits_for_need: false,
            ally_switch_stalls: false,
            defog_clears_both_sides: false,
            defog_clears_terrain: false,
            psych_up_copies_crit_volatiles: false,
            teleport_switches: false,
            destiny_bond_fails_in_a_row: false,
            curse_retargets_own_side: false,
            curse_self_hit_retargets: false,
            heal_bell_respects_abilities: false,
            heal_bell_user_soundproof: false,
            stockpile_tracks_actual_boosts: false,
            sports_are_volatiles: true,
            kings_shield_attack_drop: -1,
            terrain_boost: (5325, 4096),
            misty_terrain_blocks_confusion: true,
            fell_stinger_boost: 3,
            boost_needs_foes_left: false,
            parting_shot_needs_drops: true,
            choice_lock_fails_other_moves: false,
            charge_ends_on_any_move: true,
            weather_event_updates: false,
            secondary_chance_overflow: true,
        },
    };





    pub const GEN6_VGC: Rules = Rules {
        moves: &engine_data::moves_table::MOVES_GEN6,
        species: &engine_data::species_table::SPECIES_GEN6,
        type_chart: &engine_data::type_chart::TYPE_CHART_GEN6,
        type_order: &TYPE_ORDER_GEN6,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN6_VGC,
        fling_power: &engine_data::items_table::FLING_POWER_GEN6,
        natural_gift: &engine_data::items_table::NATURAL_GIFT_GEN6,
        stat_formula: StatFormula::EvIv { level: 50 },
        open_team_sheets: false,

        preview_shows_items: true,

        shown_hp_scale: 48,
        shown_hp_rounds_up: false,
        pp_formula: PpFormula::ThreePpUps,

        crit_mult: [0, 16, 8, 2, 1, 1],
        crit_stage_max: 4,
        crit_modifier: (3, 2),
        type_immunity_before_try_hit: true,
        full_paralysis: (1, 4),
        paralysis_speed_percent: 25,
        sleep_length: SleepLength::TwoToFour,
        sleep_resets_on_switch_in: false,
        thaw_chance: (1, 5),
        freeze_timer: false,
        burn_divisor: 8,
        burn_spares_facade: true,
        confusion_roll: (1, 2),
        confusion_hits_on_success: false,
        partial_trap_divisor: (8, 6),
        stall_base: 3,
        stall_factor: 3,
        stall_max: 729,
        modern_type_immunities: true,
        prankster_dark_immunity: false,
        type_formes_normal_without_ability: true,
        skill_swap_fails_same_ability: false,
        dynamic_speed: false,
        mega_resort: false,
        terastallization: false,
        dynamax: false,
        dragon_ascent_mega: true,
        trick_room_speed_underflow: true,
        permanent_ability_weather: false,
        mega_reverts_on_faint: true,
        instafaint_punish: true,
        dark_void_darkrai_only: false,
        sky_drop_weight_limit: true,
        ability_flag_overrides: engine_data::abilities_table::ABILITY_FLAG_OVERRIDES_GEN6,
        min_damage_before_final_modifiers: false,
        ally_or_self_keeps_fainted_ally: false,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Hail,
            frisk_one_random_foe: false,
            weak_armor_speed: 1,
            normalize: Normalize::TypeOnly,
            heatproof_halves_base_power: true,
            slow_start_data_category: true,
            run_away_escapes_trapping: false,
            healer_chance: (3, 10),
            moody_accuracy_evasion: true,
            sheer_force_skips_after_move_secondary: true,
            intimidate_ability_reactions: false,
            oblivious_blocks_taunt: true,
            keen_eye_ignores_evasion: true,
            illuminate_active: false,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (5325, 4096),
            parental_bond_second_hit: (1, 2),
            gale_wings_needs_full_hp: false,
            protean_once_per_switch_in: false,
            stance_change_before_move: true,
            soundproof_blocks_own_moves: true,
            symbiosis_skips_switching_ally: false,

            disguise_bust_costs_hp: false,
            disguise_forme_regression: true,
            battle_bond_forme_change: true,
            transistor_modifier: (6144, 4096),
            sword_shield_every_switch_in: true,
            emergency_exit_clears_switches: true,
            unseen_fist_strips_protect_flag: true,
        },
        items: ItemRules { gem_modifier: (5325, 4096), confusion_berry_pinch: (1, 2), confusion_berry_heal: (1, 8), life_orb_modern: false, eject_button_cancels_user_switch: true, jaboca_needs_standing_attacker: false },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2732, 4096),
            after_hit_needs_user_hp: true,
            knock_off_boost: true,
            conversion: Conversion::FirstSlot,
            camouflage: Camouflage::ByTerrain,
            nature_power: NaturePower::ByTerrain,
            howl_boosts_ally: false,
            curse_target: CurseTarget::RandomFoe,
            guards_roll_stall: false,
            poison_toxic_sure_hit: false,
            poison_toxic_sure_hit_after_events: true,
            sheer_cold_ice_rules: false,
            wide_guard_blocks_status: false,
            quick_guard_base_priority: false,
            first_turn_moves_disabled: false,
            berry_moves_disabled: true,
            salt_cure_divisors: (8, 4),
            disable_spares_cant_use_twice: false,
            times_attacked_resets_on_switch: false,
            encore_requeues_at_start: false,
            modern_break_protect: true,
            incinerate_burns_gems: true,
            fury_cutter_max_mult: 4,
            healing_wish_waits_for_need: false,
            ally_switch_stalls: false,
            defog_clears_both_sides: true,
            defog_clears_terrain: false,
            psych_up_copies_crit_volatiles: true,
            teleport_switches: false,
            destiny_bond_fails_in_a_row: false,
            curse_retargets_own_side: false,
            curse_self_hit_retargets: false,
            heal_bell_respects_abilities: true,
            heal_bell_user_soundproof: true,
            stockpile_tracks_actual_boosts: false,
            sports_are_volatiles: false,
            kings_shield_attack_drop: -2,
            terrain_boost: (6144, 4096),
            misty_terrain_blocks_confusion: false,
            fell_stinger_boost: 2,
            boost_needs_foes_left: true,
            parting_shot_needs_drops: false,
            choice_lock_fails_other_moves: false,
            charge_ends_on_any_move: true,
            weather_event_updates: false,
            secondary_chance_overflow: true,
        },
    };




    pub const GEN7_VGC: Rules = Rules {
        moves: &engine_data::moves_table::MOVES_GEN7,
        species: &engine_data::species_table::SPECIES_GEN7,
        type_chart: &engine_data::type_chart::TYPE_CHART_GEN7,
        type_order: &TYPE_ORDER_GEN7,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN7_VGC,
        fling_power: &engine_data::items_table::FLING_POWER_GEN7,
        natural_gift: &engine_data::items_table::NATURAL_GIFT_GEN7,
        stat_formula: StatFormula::EvIv { level: 50 },
        open_team_sheets: false,

        preview_shows_items: true,

        shown_hp_scale: 100,
        shown_hp_rounds_up: true,
        pp_formula: PpFormula::ThreePpUps,

        crit_mult: [0, 24, 8, 2, 1, 1],
        crit_stage_max: 4,
        crit_modifier: (3, 2),

        type_immunity_before_try_hit: false,
        full_paralysis: (1, 4),
        paralysis_speed_percent: 50,
        sleep_length: SleepLength::TwoToFour,
        sleep_resets_on_switch_in: false,
        thaw_chance: (1, 5),
        freeze_timer: false,
        burn_divisor: 16,
        burn_spares_facade: true,
        confusion_roll: (33, 100),
        confusion_hits_on_success: true,
        partial_trap_divisor: (8, 6),
        stall_base: 3,
        stall_factor: 3,
        stall_max: 729,
        modern_type_immunities: true,
        prankster_dark_immunity: true,
        type_formes_normal_without_ability: true,
        skill_swap_fails_same_ability: false,
        dynamic_speed: false,
        mega_resort: true,
        terastallization: false,
        dynamax: false,
        dragon_ascent_mega: true,
        trick_room_speed_underflow: true,
        permanent_ability_weather: false,
        mega_reverts_on_faint: true,
        instafaint_punish: false,
        dark_void_darkrai_only: true,
        sky_drop_weight_limit: true,
        ability_flag_overrides: engine_data::abilities_table::ABILITY_FLAG_OVERRIDES_GEN7,
        min_damage_before_final_modifiers: false,
        ally_or_self_keeps_fainted_ally: false,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Hail,
            frisk_one_random_foe: false,
            weak_armor_speed: 2,
            normalize: Normalize::Ate,
            heatproof_halves_base_power: true,
            slow_start_data_category: true,
            run_away_escapes_trapping: false,
            healer_chance: (3, 10),
            moody_accuracy_evasion: true,
            sheer_force_skips_after_move_secondary: true,
            intimidate_ability_reactions: false,
            oblivious_blocks_taunt: true,
            keen_eye_ignores_evasion: true,
            illuminate_active: false,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (4915, 4096),
            parental_bond_second_hit: (1, 4),
            gale_wings_needs_full_hp: true,
            protean_once_per_switch_in: false,
            stance_change_before_move: false,
            soundproof_blocks_own_moves: true,
            symbiosis_skips_switching_ally: true,
            disguise_bust_costs_hp: false,
            disguise_forme_regression: true,
            battle_bond_forme_change: true,
            transistor_modifier: (6144, 4096),
            sword_shield_every_switch_in: true,
            emergency_exit_clears_switches: true,
            unseen_fist_strips_protect_flag: true,
        },
        items: ItemRules { gem_modifier: (5325, 4096), confusion_berry_pinch: (1, 4), confusion_berry_heal: (1, 2), life_orb_modern: true, eject_button_cancels_user_switch: true, jaboca_needs_standing_attacker: true },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2732, 4096),
            after_hit_needs_user_hp: true,
            knock_off_boost: true,
            conversion: Conversion::FirstSlot,
            camouflage: Camouflage::ByTerrain,
            nature_power: NaturePower::ByTerrain,
            howl_boosts_ally: false,
            curse_target: CurseTarget::RandomFoe,
            guards_roll_stall: false,
            poison_toxic_sure_hit: false,
            poison_toxic_sure_hit_after_events: true,
            sheer_cold_ice_rules: true,
            wide_guard_blocks_status: true,
            quick_guard_base_priority: false,
            first_turn_moves_disabled: false,
            berry_moves_disabled: true,
            salt_cure_divisors: (8, 4),
            disable_spares_cant_use_twice: false,
            times_attacked_resets_on_switch: false,
            encore_requeues_at_start: false,
            modern_break_protect: true,
            incinerate_burns_gems: true,
            fury_cutter_max_mult: 4,
            healing_wish_waits_for_need: false,
            ally_switch_stalls: false,
            defog_clears_both_sides: true,
            defog_clears_terrain: false,
            psych_up_copies_crit_volatiles: true,
            teleport_switches: false,
            destiny_bond_fails_in_a_row: true,
            curse_retargets_own_side: false,
            curse_self_hit_retargets: false,
            heal_bell_respects_abilities: true,
            heal_bell_user_soundproof: true,
            stockpile_tracks_actual_boosts: true,
            sports_are_volatiles: false,
            kings_shield_attack_drop: -2,
            terrain_boost: (6144, 4096),
            misty_terrain_blocks_confusion: true,
            fell_stinger_boost: 3,
            boost_needs_foes_left: true,
            parting_shot_needs_drops: true,
            choice_lock_fails_other_moves: true,
            charge_ends_on_any_move: true,
            weather_event_updates: true,
            secondary_chance_overflow: true,
        },
    };







    pub const GEN8_VGC: Rules = Rules {
        moves: &engine_data::moves_table::MOVES_GEN8,
        species: &engine_data::species_table::SPECIES_GEN8,

        type_chart: &engine_data::type_chart::TYPE_CHART_GEN7,
        type_order: &TYPE_ORDER_GEN7,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN8_VGC,

        fling_power: &engine_data::items_table::FLING_POWER,
        natural_gift: &engine_data::items_table::NATURAL_GIFT,
        stat_formula: StatFormula::EvIv { level: 50 },
        open_team_sheets: false,

        preview_shows_items: false,

        shown_hp_scale: 100,
        shown_hp_rounds_up: true,
        pp_formula: PpFormula::ThreePpUps,

        crit_mult: [0, 24, 8, 2, 1, 1],
        crit_stage_max: 4,
        crit_modifier: (3, 2),

        type_immunity_before_try_hit: false,
        full_paralysis: (1, 4),
        paralysis_speed_percent: 50,
        sleep_length: SleepLength::TwoToFour,
        sleep_resets_on_switch_in: false,
        thaw_chance: (1, 5),
        freeze_timer: false,
        burn_divisor: 16,
        burn_spares_facade: true,
        confusion_roll: (33, 100),
        confusion_hits_on_success: true,
        partial_trap_divisor: (8, 6),
        stall_base: 3,
        stall_factor: 3,
        stall_max: 729,
        modern_type_immunities: true,
        prankster_dark_immunity: true,

        type_formes_normal_without_ability: false,
        skill_swap_fails_same_ability: false,

        dynamic_speed: true,
        mega_resort: false,
        terastallization: false,
        dynamax: true,

        dragon_ascent_mega: false,
        trick_room_speed_underflow: true,
        permanent_ability_weather: false,
        mega_reverts_on_faint: true,
        instafaint_punish: false,
        dark_void_darkrai_only: true,
        sky_drop_weight_limit: true,
        ability_flag_overrides: engine_data::abilities_table::ABILITY_FLAG_OVERRIDES_GEN8,
        min_damage_before_final_modifiers: false,
        ally_or_self_keeps_fainted_ally: false,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Hail,
            frisk_one_random_foe: false,
            weak_armor_speed: 2,
            normalize: Normalize::Ate,
            heatproof_halves_base_power: true,
            slow_start_data_category: false,
            run_away_escapes_trapping: false,
            healer_chance: (3, 10),
            moody_accuracy_evasion: false,
            sheer_force_skips_after_move_secondary: true,
            intimidate_ability_reactions: true,
            oblivious_blocks_taunt: true,
            keen_eye_ignores_evasion: true,
            illuminate_active: false,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (4915, 4096),
            parental_bond_second_hit: (1, 4),
            gale_wings_needs_full_hp: true,
            protean_once_per_switch_in: false,
            stance_change_before_move: false,
            soundproof_blocks_own_moves: false,
            symbiosis_skips_switching_ally: true,

            disguise_bust_costs_hp: true,
            disguise_forme_regression: true,
            battle_bond_forme_change: true,
            transistor_modifier: (6144, 4096),
            sword_shield_every_switch_in: true,
            emergency_exit_clears_switches: true,
            unseen_fist_strips_protect_flag: true,
        },
        items: ItemRules { gem_modifier: (5325, 4096), confusion_berry_pinch: (1, 4), confusion_berry_heal: (1, 3), life_orb_modern: true, eject_button_cancels_user_switch: true, jaboca_needs_standing_attacker: true },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2732, 4096),
            after_hit_needs_user_hp: true,
            knock_off_boost: true,
            conversion: Conversion::FirstSlot,
            camouflage: Camouflage::ByTerrain,
            nature_power: NaturePower::ByTerrain,
            howl_boosts_ally: true,

            curse_target: CurseTarget::RandomNormal,
            guards_roll_stall: false,
            poison_toxic_sure_hit: true,
            poison_toxic_sure_hit_after_events: false,
            sheer_cold_ice_rules: true,
            wide_guard_blocks_status: true,
            quick_guard_base_priority: false,
            first_turn_moves_disabled: false,
            berry_moves_disabled: true,
            salt_cure_divisors: (8, 4),
            disable_spares_cant_use_twice: false,
            times_attacked_resets_on_switch: false,
            encore_requeues_at_start: false,
            modern_break_protect: true,
            incinerate_burns_gems: true,
            fury_cutter_max_mult: 4,
            healing_wish_waits_for_need: true,
            ally_switch_stalls: false,
            defog_clears_both_sides: true,
            defog_clears_terrain: true,
            psych_up_copies_crit_volatiles: true,
            teleport_switches: true,
            destiny_bond_fails_in_a_row: true,
            curse_retargets_own_side: false,
            curse_self_hit_retargets: false,
            heal_bell_respects_abilities: true,
            heal_bell_user_soundproof: false,
            stockpile_tracks_actual_boosts: true,
            sports_are_volatiles: false,
            kings_shield_attack_drop: -1,
            terrain_boost: (5325, 4096),
            misty_terrain_blocks_confusion: true,
            fell_stinger_boost: 3,
            boost_needs_foes_left: true,
            parting_shot_needs_drops: true,
            choice_lock_fails_other_moves: true,
            charge_ends_on_any_move: true,
            weather_event_updates: true,
            secondary_chance_overflow: true,
        },
    };




    pub const GEN9_SV: Rules = Rules {


        moves: &engine_data::moves_table::MOVES_GEN9,
        species: &engine_data::species_table::SPECIES,
        type_chart: &engine_data::type_chart::TYPE_CHART,
        type_order: &TYPE_ORDER_CHAMPIONS,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN9_SV,
        fling_power: &engine_data::items_table::FLING_POWER,
        natural_gift: &engine_data::items_table::NATURAL_GIFT,

        stat_formula: StatFormula::EvIv { level: 50 },
        open_team_sheets: true,

        preview_shows_items: false,

        shown_hp_scale: 100,
        shown_hp_rounds_up: true,
        pp_formula: PpFormula::ThreePpUps,
        crit_mult: [0, 24, 8, 2, 1, 1],
        crit_stage_max: 4,
        crit_modifier: (3, 2),
        type_immunity_before_try_hit: false,

        full_paralysis: (1, 4),
        paralysis_speed_percent: 50,
        sleep_length: SleepLength::TwoToFour,
        sleep_resets_on_switch_in: false,
        thaw_chance: (1, 5),
        freeze_timer: false,
        burn_divisor: 16,
        burn_spares_facade: true,
        confusion_roll: (33, 100),
        confusion_hits_on_success: true,
        partial_trap_divisor: (8, 6),
        stall_base: 3,
        stall_factor: 3,
        stall_max: 729,
        modern_type_immunities: true,
        prankster_dark_immunity: true,
        type_formes_normal_without_ability: false,
        skill_swap_fails_same_ability: false,
        dynamic_speed: true,
        mega_resort: false,
        terastallization: true,
        dynamax: false,
        dragon_ascent_mega: false,

        trick_room_speed_underflow: true,
        permanent_ability_weather: false,

        mega_reverts_on_faint: true,
        instafaint_punish: false,
        dark_void_darkrai_only: true,
        sky_drop_weight_limit: true,
        ability_flag_overrides: &[],
        min_damage_before_final_modifiers: false,
        ally_or_self_keeps_fainted_ally: false,
        abilities: AbilityRules {
            snow_warning: crate::field::Weather::Snow,
            frisk_one_random_foe: false,
            weak_armor_speed: 2,
            normalize: Normalize::Ate,
            heatproof_halves_base_power: false,
            slow_start_data_category: false,

            run_away_escapes_trapping: false,
            healer_chance: (3, 10),
            moody_accuracy_evasion: false,

            sheer_force_skips_after_move_secondary: true,
            intimidate_ability_reactions: true,
            oblivious_blocks_taunt: true,
            keen_eye_ignores_evasion: true,
            illuminate_active: true,
            protosynthesis_holds_suppressed_sun: false,
            ate_modifier: (4915, 4096),
            parental_bond_second_hit: (1, 4),
            gale_wings_needs_full_hp: true,
            protean_once_per_switch_in: true,
            stance_change_before_move: false,
            soundproof_blocks_own_moves: false,
            symbiosis_skips_switching_ally: true,
            disguise_bust_costs_hp: true,
            disguise_forme_regression: false,
            battle_bond_forme_change: false,
            transistor_modifier: (5325, 4096),
            sword_shield_every_switch_in: false,
            emergency_exit_clears_switches: true,
            unseen_fist_strips_protect_flag: true,
        },

        items: ItemRules { gem_modifier: (5325, 4096), confusion_berry_pinch: (1, 4), confusion_berry_heal: (1, 3), life_orb_modern: true, eject_button_cancels_user_switch: true, jaboca_needs_standing_attacker: true },
        move_effects: MoveEffectRules {
            screen_doubles_modifier: (2732, 4096),

            after_hit_needs_user_hp: true,
            knock_off_boost: true,
            conversion: Conversion::FirstSlot,
            camouflage: Camouflage::ByTerrain,
            nature_power: NaturePower::ByTerrain,
            howl_boosts_ally: true,

            curse_target: CurseTarget::RandomFoe,
            guards_roll_stall: false,
            poison_toxic_sure_hit: true,
            poison_toxic_sure_hit_after_events: false,
            sheer_cold_ice_rules: true,
            wide_guard_blocks_status: true,
            quick_guard_base_priority: false,

            first_turn_moves_disabled: false,
            berry_moves_disabled: true,
            salt_cure_divisors: (8, 4),
            disable_spares_cant_use_twice: false,
            times_attacked_resets_on_switch: false,

            encore_requeues_at_start: false,
            modern_break_protect: true,
            incinerate_burns_gems: true,
            fury_cutter_max_mult: 4,
            healing_wish_waits_for_need: true,
            ally_switch_stalls: true,
            defog_clears_both_sides: true,
            defog_clears_terrain: true,
            psych_up_copies_crit_volatiles: true,
            teleport_switches: true,
            destiny_bond_fails_in_a_row: true,
            curse_retargets_own_side: true,

            curse_self_hit_retargets: false,
            heal_bell_respects_abilities: true,
            heal_bell_user_soundproof: false,
            stockpile_tracks_actual_boosts: true,
            sports_are_volatiles: false,
            kings_shield_attack_drop: -1,
            terrain_boost: (5325, 4096),
            misty_terrain_blocks_confusion: true,
            fell_stinger_boost: 3,
            boost_needs_foes_left: true,
            parting_shot_needs_drops: true,
            choice_lock_fails_other_moves: true,
            charge_ends_on_any_move: false,
            weather_event_updates: true,
            secondary_chance_overflow: false,
        },
    };






    pub const GEN9_SV_PREDLC: Rules = Rules {
        ability_flag_overrides: engine_data::abilities_table::ABILITY_FLAG_OVERRIDES_GEN9_PREDLC,
        moves: &engine_data::moves_table::MOVES_GEN9_PREDLC,
        species: &engine_data::species_table::SPECIES_GEN9_PREDLC,
        metronome_pool: &engine_data::moves_table::METRONOME_POOL_GEN9_SV_PREDLC,
        abilities: AbilityRules { illuminate_active: false, protosynthesis_holds_suppressed_sun: true, ..Rules::GEN9_SV.abilities },
        ..Rules::GEN9_SV
    };


    #[inline]
    pub fn move_data(&self, id: engine_data::moves_table::MoveId) -> &'static engine_data::moves_table::MoveData {
        &self.moves[(id - 1) as usize]
    }

    #[inline]
    pub fn species_data(&self, id: engine_data::species_table::SpeciesId) -> &'static engine_data::species_table::SpeciesData {
        &self.species[(id - 1) as usize]
    }


    pub fn stat(&self, stat: crate::stats::Stat, base: u32, invest: u32, iv: u32, nature: crate::stats::Nature) -> u32 {
        match self.stat_formula {
            StatFormula::ChampionsPoints => crate::stats::calc_stat(stat, base, invest, nature),
            StatFormula::EvIv { level } => crate::stats::calc_stat_ev(stat, base, invest, iv, level as u32, nature),
        }
    }


    pub fn hp(&self, base: u32, invest: u32, iv: u32) -> u32 {
        match self.stat_formula {
            StatFormula::ChampionsPoints => crate::stats::calc_hp(base, invest),
            StatFormula::EvIv { level } => crate::stats::calc_hp_ev(base, invest, iv, level as u32),
        }
    }


    pub fn max_pp(&self, move_id: engine_data::moves_table::MoveId) -> u8 {
        match self.pp_formula {
            PpFormula::Champions => crate::mon::max_pp(move_id),
            PpFormula::ThreePpUps => {
                use engine_data::moves_table::move_ids::{SKETCH, STRUGGLE, TRUMPCARD};
                if move_id == 0 {
                    return 0;
                }
                let pp = self.move_data(move_id).pp;
                if matches!(move_id, SKETCH | STRUGGLE | TRUMPCARD) { pp } else { (pp as u16 * 8 / 5) as u8 }
            }
        }
    }

    pub fn full_pp(&self, moves: [engine_data::moves_table::MoveId; 4]) -> [u8; 4] {
        moves.map(|m| self.max_pp(m))
    }

    pub const fn of(format: Format) -> &'static Rules {
        match format {
            Format::ChampionsMC => &Rules::CHAMPIONS_MC,
            Format::Gen5Vgc13 => &Rules::GEN5_VGC13,
            Format::Gen6Vgc => &Rules::GEN6_VGC,
            Format::Gen7Vgc => &Rules::GEN7_VGC,
            Format::Gen9Sv => &Rules::GEN9_SV,
            Format::Gen9SvPreDlc => &Rules::GEN9_SV_PREDLC,
            Format::Gen8Vgc => &Rules::GEN8_VGC,
        }
    }
}

#[cfg(test)]
mod tests {


    #[test]
    fn format_identity_stays_in_rules() {
        for (name, src) in [
            ("turn.rs", include_str!("turn.rs")),
            ("abilities.rs", include_str!("abilities.rs")),
            ("items.rs", include_str!("items.rs")),
            ("damage.rs", include_str!("damage.rs")),
            ("mon.rs", include_str!("mon.rs")),
            ("legal.rs", include_str!("legal.rs")),
            ("boosts.rs", include_str!("boosts.rs")),
            ("status.rs", include_str!("status.rs")),
        ] {

            let code = ["\nmod tests {", "\npub(crate) mod tests {"].iter().filter_map(|m| src.find(m)).min().map_or(src, |i| &src[..i]);
            for needle in ["Format::", "Rules::of(", "Rules::CHAMPIONS_MC", "Rules::GEN5_VGC13", "Rules::GEN6_VGC", "Rules::GEN7_VGC", "Rules::GEN9_SV"] {
                assert!(!code.contains(needle), "{name} names a format ({needle}): read a `Rules` field instead");
            }
        }
    }
}
