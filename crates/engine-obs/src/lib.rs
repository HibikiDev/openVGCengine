







































#![forbid(unsafe_code)]

use engine_core::battle::Battle;
use engine_core::event::{EventKind, NO_MON};
use engine_core::mon::{mon_flags, volatile_flags, Mon};
use engine_core::pending::Pending;
use engine_core::status::Status;
use engine_core::items::mega_forme;

pub const OBS_VERSION: u32 = 6;

pub const ROSTER_SIZE: usize = 6;
pub const BROUGHT_SIZE: usize = 4;
pub const MON_TOKENS: usize = 2 * ROSTER_SIZE;
pub const HISTORY_LEN: usize = 16;
pub const EVENT_FIELDS: usize = 5;

pub const FIELD_FEATURES: usize = field::COUNT;
pub const MON_IDS: usize = mon_id::COUNT;
pub const MON_FEATURES: usize = mon_feature::COUNT;


pub const SPECIES_VOCAB: usize = engine_data::species_table::SPECIES_COUNT + 1;
pub const ITEM_VOCAB: usize = engine_data::items_table::ITEM_COUNT + 1;
pub const ABILITY_VOCAB: usize = engine_data::abilities_table::ABILITY_COUNT + 1;
pub const MOVE_VOCAB: usize = engine_data::moves_table::MOVE_COUNT + 1;
pub const TYPE_VOCAB: usize = engine_data::type_chart::TYPE_COUNT + 1;


pub mod field {

    pub const WEATHER: usize = 0;
    pub const WEATHER_TURNS: usize = 5;

    pub const TERRAIN: usize = 6;
    pub const TERRAIN_TURNS: usize = 11;
    pub const TRICK_ROOM_TURNS: usize = 12;
    pub const GRAVITY_TURNS: usize = 13;
    pub const TURN: usize = 14;

    pub const MY_SIDE: usize = 15;
    pub const FOE_SIDE: usize = 21;
    pub const SIDE_FEATURES: usize = 6;

    pub const DECISION: usize = 27;

    pub const FORMAT: usize = 30;
    pub const FORMAT_SLOTS: usize = 4;

    pub const MY_Z_USED: usize = 34;
    pub const FOE_Z_USED: usize = 35;


    pub const FORMAT2: usize = 36;
    pub const FORMAT2_SLOTS: usize = 4;

    pub const MY_TERA_USED: usize = 40;
    pub const FOE_TERA_USED: usize = 41;

    pub const MY_DYNAMAX_USED: usize = 42;
    pub const FOE_DYNAMAX_USED: usize = 43;


    pub const MY_GMAX_RESIDUAL: usize = 44;
    pub const FOE_GMAX_RESIDUAL: usize = 45;
    pub const COUNT: usize = 46;
}


pub mod mon_id {
    pub const SPECIES: usize = 0;
    pub const ITEM: usize = 1;
    pub const ABILITY: usize = 2;
    pub const MOVES: usize = 3;
    pub const TYPES: usize = 7;

    pub const TERA_TYPE: usize = 9;
    pub const COUNT: usize = 10;
}


pub mod mon_feature {
    pub const IS_MINE: usize = 0;

    pub const IN_BATTLE: usize = 1;
    pub const ACTIVE_A: usize = 2;
    pub const ACTIVE_B: usize = 3;
    pub const FAINTED: usize = 4;

    pub const HP: usize = 5;

    pub const STATUS: usize = 6;
    pub const TOXIC_STAGE: usize = 13;

    pub const BOOSTS: usize = 14;
    pub const MEGA_ACTIVE: usize = 21;
    pub const CAN_MEGA: usize = 22;
    pub const TURNS_ACTIVE: usize = 23;
    pub const CONFUSED: usize = 24;
    pub const TAUNTED: usize = 25;
    pub const ENCORED: usize = 26;
    pub const DISABLED: usize = 27;
    pub const SUBSTITUTE: usize = 28;
    pub const PROTECT_STREAK: usize = 29;
    pub const PERISH: usize = 30;
    pub const YAWN: usize = 31;
    pub const PARTIALLY_TRAPPED: usize = 32;
    pub const CHARGING: usize = 33;
    pub const MUST_RECHARGE: usize = 34;
    pub const CHOICE_LOCKED: usize = 35;
    pub const THROAT_CHOPPED: usize = 36;
    pub const HEAL_BLOCKED: usize = 37;
    pub const HOLDS_ITEM: usize = 38;

    pub const STATS: usize = 39;

    pub const PP: usize = 45;
    pub const STOCKPILE: usize = 49;

    pub const TERASTALLIZED: usize = 50;

    pub const STELLAR_LEFT: usize = 51;

    pub const COMMANDING: usize = 52;

    pub const DYNAMAX_TURNS: usize = 53;

    pub const GIGANTAMAX: usize = 54;

    pub const CHI_STRIKE: usize = 55;
    pub const COUNT: usize = 56;
}


#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct SheetMon {
    pub species: u16,
    pub item: u16,
    pub ability: u16,
    pub moves: [u16; 4],

    pub tera_type: u8,
}

#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct TeamSheet {
    pub mons: [SheetMon; ROSTER_SIZE],
}



#[derive(Clone, Copy, Debug, Default, PartialEq, Eq)]
pub struct ObsContext {
    pub sheets: [TeamSheet; 2],
    pub brought: [[u8; BROUGHT_SIZE]; 2],



    pub open_sheets: bool,
}

impl ObsContext {


    pub fn from_battle(battle: &Battle) -> ObsContext {
        let sheet = |s: usize| {
            let mut sheet = TeamSheet::default();
            for (i, m) in battle.sides[s].mons.iter().enumerate() {
                let tera_type = m.tera.tera_type.map_or(0, |t| t as u8 + 1);
                sheet.mons[i] = SheetMon { species: m.species, item: m.item, ability: m.base_ability, moves: m.moves, tera_type };
            }
            sheet
        };
        ObsContext { sheets: [sheet(0), sheet(1)], brought: [[0, 1, 2, 3]; 2], open_sheets: false }
    }
}


pub struct ObsBuffers<'a> {
    pub field: &'a mut [f32],
    pub mon_ids: &'a mut [i32],
    pub mon_features: &'a mut [f32],
    pub history: &'a mut [i32],
}


pub const BUFFER_SIZES: [usize; 4] = [FIELD_FEATURES, MON_TOKENS * MON_IDS, MON_TOKENS * MON_FEATURES, HISTORY_LEN * EVENT_FIELDS];


pub fn encode(battle: &Battle, ctx: &ObsContext, me: u8, out: ObsBuffers) {
    assert_eq!(out.field.len(), FIELD_FEATURES);
    assert_eq!(out.mon_ids.len(), MON_TOKENS * MON_IDS);
    assert_eq!(out.mon_features.len(), MON_TOKENS * MON_FEATURES);
    assert_eq!(out.history.len(), HISTORY_LEN * EVENT_FIELDS);
    out.field.fill(0.0);
    out.mon_ids.fill(0);
    out.mon_features.fill(0.0);
    out.history.fill(0);
    encode_field(battle, me, out.field);
    for side in [me, 1 - me] {
        for r in 0..ROSTER_SIZE {
            let token = token_of(me, side, r);
            encode_mon(
                battle,
                ctx,
                me,
                side,
                r,
                &mut out.mon_ids[token * MON_IDS..(token + 1) * MON_IDS],
                &mut out.mon_features[token * MON_FEATURES..(token + 1) * MON_FEATURES],
            );
        }
    }
    encode_history(battle, ctx, me, out.history);
}


fn token_of(me: u8, side: u8, r: usize) -> usize {
    if side == me { r } else { ROSTER_SIZE + r }
}

fn encode_field(battle: &Battle, me: u8, f: &mut [f32]) {
    use engine_core::field::{Terrain, Weather};
    let weather = battle.weather();


    let w = match weather {
        Weather::None | Weather::DeltaStream => 0,
        Weather::Sun | Weather::DesolateLand => 1,
        Weather::Rain | Weather::PrimordialSea => 2,
        Weather::Sand => 3,

        Weather::Snow | Weather::Hail => 4,
    };
    f[field::WEATHER + w] = 1.0;
    if weather != Weather::None {
        f[field::WEATHER_TURNS] = battle.field.weather_turns as f32 / 8.0;
    }
    let t = match battle.field.terrain {
        Terrain::None => 0,
        Terrain::Electric => 1,
        Terrain::Grassy => 2,
        Terrain::Misty => 3,
        Terrain::Psychic => 4,
    };
    f[field::TERRAIN + t] = 1.0;
    f[field::TERRAIN_TURNS] = battle.field.terrain_turns as f32 / 8.0;
    f[field::TRICK_ROOM_TURNS] = battle.field.trick_room_turns as f32 / 5.0;
    f[field::GRAVITY_TURNS] = battle.field.gravity_turns as f32 / 5.0;
    f[field::TURN] = battle.turn.min(30) as f32 / 30.0;
    for (side, base) in [(me, field::MY_SIDE), (1 - me, field::FOE_SIDE)] {
        let s = &battle.sides[side as usize];
        let c = &s.side_conditions;
        f[base] = c.reflect_turns as f32 / 8.0;
        f[base + 1] = c.light_screen_turns as f32 / 8.0;
        f[base + 2] = c.aurora_veil_turns as f32 / 8.0;
        f[base + 3] = c.tailwind_turns as f32 / 4.0;
        f[base + 4] = s.mega_used as u8 as f32;
        f[base + 5] = c.healing_wish.iter().any(|&h| h) as u8 as f32;
    }
    let decision = match battle.pending {
        Pending::Turn | Pending::Over { .. } => 0,
        Pending::ForcedSwitch { side0, side1 } => {
            if (me == 0 && side0) || (me == 1 && side1) { 1 } else { 2 }
        }
    };
    f[field::DECISION + decision] = 1.0;
    let format = battle.format.obs_slot();
    if format < field::FORMAT_SLOTS {
        f[field::FORMAT + format] = 1.0;
    } else {
        f[field::FORMAT2 + (format - field::FORMAT_SLOTS).min(field::FORMAT2_SLOTS - 1)] = 1.0;
    }
    f[field::MY_Z_USED] = battle.sides[me as usize].z_used as u8 as f32;
    f[field::FOE_Z_USED] = battle.sides[1 - me as usize].z_used as u8 as f32;
    f[field::MY_TERA_USED] = battle.sides[me as usize].tera_used as u8 as f32;
    f[field::FOE_TERA_USED] = battle.sides[1 - me as usize].tera_used as u8 as f32;
    f[field::MY_DYNAMAX_USED] = battle.sides[me as usize].dynamax_used as u8 as f32;
    f[field::FOE_DYNAMAX_USED] = battle.sides[1 - me as usize].dynamax_used as u8 as f32;
    let residual = |s: usize| *battle.sides[s].side_conditions.gmax_residual_turns.iter().max().unwrap_or(&0) as f32 / 4.0;
    f[field::MY_GMAX_RESIDUAL] = residual(me as usize);
    f[field::FOE_GMAX_RESIDUAL] = residual(1 - me as usize);
}



fn mon_can_dynamax(rules: &engine_core::rules::Rules, s: &engine_core::side::Side, mon: &Mon) -> bool {
    rules.dynamax
        && !s.dynamax_used
        && !mon.flags.has(mon_flags::DYNAMAXED)
        && !engine_data::max_table::CANNOT_DYNAMAX.contains(&mon.species)
        && !mon.illusion.is_some_and(|i| engine_data::max_table::CANNOT_DYNAMAX.contains(&s.mons[i as usize].species))
        && engine_data::z_table::crystal(mon.item).is_none()
}



fn stellar_left(mon: &Mon) -> f32 {
    use engine_data::type_chart::Type;
    if !mon.tera.active || mon.tera.tera_type != Some(Type::Stellar) {
        return 0.0;
    }
    if mon.species == engine_data::species_table::species_ids::TERAPAGOSSTELLAR {
        return 1.0;
    }

    let spent = (0..engine_data::type_chart::TYPE_COUNT as u32)
        .filter(|&t| t != Type::Stellar as u32 && mon.tera.stellar_boosted & (1 << t) != 0)
        .count();
    (18 - spent) as f32 / 18.0
}


fn details_species(s: engine_data::species_table::SpeciesId) -> engine_data::species_table::SpeciesId {
    use engine_data::species_table::species_ids::*;
    match s {
        GRENINJABOND => GRENINJA,
        ROCKRUFFDUSK => ROCKRUFF,
        _ => s,
    }
}







fn preview_species(s: engine_data::species_table::SpeciesId) -> engine_data::species_table::SpeciesId {
    use engine_data::species_table::species_ids::*;
    match s {
        ZACIANCROWNED => ZACIAN,
        ZAMAZENTACROWNED => ZAMAZENTA,
        GRENINJAASH | GRENINJABOND | GRENINJAMEGA => GRENINJA,
        GOURGEISTLARGE | GOURGEISTSMALL | GOURGEISTSUPER => GOURGEIST,
        PUMPKABOOLARGE | PUMPKABOOSMALL | PUMPKABOOSUPER => PUMPKABOO,
        SILVALLYBUG | SILVALLYDARK | SILVALLYDRAGON | SILVALLYELECTRIC | SILVALLYFAIRY | SILVALLYFIGHTING | SILVALLYFIRE | SILVALLYFLYING
        | SILVALLYGHOST | SILVALLYGRASS | SILVALLYGROUND | SILVALLYICE | SILVALLYPOISON | SILVALLYPSYCHIC | SILVALLYROCK | SILVALLYSTEEL
        | SILVALLYWATER => SILVALLY,
        URSHIFUGMAX | URSHIFURAPIDSTRIKE | URSHIFURAPIDSTRIKEGMAX => URSHIFU,
        DUDUNSPARCETHREESEGMENT => DUDUNSPARCE,
        ROCKRUFFDUSK => ROCKRUFF,
        _ => s,
    }
}


fn z_capable(battle: &Battle, side: u8, item: u16, species: u16, moves: &[u16]) -> bool {
    !battle.sides[side as usize].z_used && z_capable_sheet(battle.rules(), item, species, moves)
}



pub fn z_move_of_sheet(rules: &engine_core::rules::Rules, item: u16, species: u16, base: u16) -> Option<u16> {
    use engine_data::z_table::{crystal, type_z_move, z_move, Crystal};
    if base == 0 {
        return None;
    }
    match crystal(item)? {
        Crystal::Signature { base_move, z_move: z, users } => (base == base_move && users.contains(&species)).then_some(z),
        Crystal::Type(t) => {
            let d = rules.move_data(base);
            if d.move_type != t {
                None
            } else if d.category == engine_data::moves_table::Category::Status {
                Some(base)
            } else if z_move(base).power > 0 {
                Some(type_z_move(t))
            } else {
                None
            }
        }
    }
}




pub fn z_capable_sheet(rules: &engine_core::rules::Rules, item: u16, species: u16, moves: &[u16]) -> bool {
    use engine_data::z_table::{crystal, z_move, Crystal};
    match crystal(item) {
        None => false,
        Some(Crystal::Signature { base_move, users, .. }) => users.contains(&species) && moves.contains(&base_move),
        Some(Crystal::Type(t)) => moves.iter().any(|&m| {
            m != 0 && {
                let d = rules.move_data(m);
                d.move_type == t && (d.category == engine_data::moves_table::Category::Status || z_move(m).power > 0)
            }
        }),
    }
}


fn battle_index(ctx: &ObsContext, side: u8, r: usize) -> Option<usize> {
    ctx.brought[side as usize].iter().position(|&b| b as usize == r)
}

fn encode_mon(battle: &Battle, ctx: &ObsContext, me: u8, side: u8, r: usize, ids: &mut [i32], f: &mut [f32]) {
    use mon_feature as mf;
    let sheet = &ctx.sheets[side as usize].mons[r];
    let mine = side == me;

    if sheet.species == 0 && battle_index(ctx, side, r).is_none() {
        return;
    }
    f[mf::IS_MINE] = mine as u8 as f32;
    let rules = battle.rules();

    let open = rules.open_team_sheets || ctx.open_sheets;
    let sheet_known = mine || open;
    let live = battle_index(ctx, side, r)
        .map(|i| (i, &battle.sides[side as usize].mons[i]))
        .filter(|(_, m)| mine || m.flags.has(mon_flags::REVEALED));
    let Some((index, mon)) = live else {


        let species = if sheet_known { sheet.species } else { preview_species(sheet.species) };
        ids[mon_id::SPECIES] = species as i32;
        if sheet_known {
            ids[mon_id::ITEM] = sheet.item as i32;
            ids[mon_id::ABILITY] = sheet.ability as i32;
            for k in 0..4 {
                ids[mon_id::MOVES + k] = sheet.moves[k] as i32;
            }
        }
        let types = rules.species_data(species).types;
        for k in 0..2 {
            ids[mon_id::TYPES + k] = types[k].map_or(0, |t| t as i32 + 1);
        }
        if sheet_known && rules.terastallization {
            ids[mon_id::TERA_TYPE] = sheet.tera_type as i32;
        }
        f[mf::HP] = 1.0;
        f[mf::STATUS] = 1.0;
        f[mf::HOLDS_ITEM] = ((sheet_known || rules.preview_shows_items) && sheet.item != 0) as u8 as f32;
        f[mf::CAN_MEGA] =
            (sheet_known
                && ((!battle.sides[side as usize].forme_change_used(engine_core::items::is_ultra_burst(sheet.item, sheet.species))
                    && mega_forme(sheet.item, sheet.species, &sheet.moves, rules.dragon_ascent_mega).is_some())
                    || z_capable(battle, side, sheet.item, sheet.species, &sheet.moves)

                    || (rules.terastallization
                        && !battle.sides[side as usize].tera_used
                        && sheet.tera_type != 0
                        && engine_data::z_table::crystal(sheet.item).is_none()
                        && mega_forme(sheet.item, sheet.species, &sheet.moves, rules.dragon_ascent_mega).is_none())

                    || (rules.dynamax
                        && !battle.sides[side as usize].dynamax_used
                        && !engine_data::max_table::CANNOT_DYNAMAX.contains(&sheet.species)
                        && engine_data::z_table::crystal(sheet.item).is_none()))) as u8 as f32;
        return;
    };


    ids[mon_id::SPECIES] = if sheet_known { mon.species } else { details_species(mon.species) } as i32;

    let transformed = mon.flags.has(mon_flags::TRANSFORMED);
    if sheet_known {
        ids[mon_id::ITEM] = mon.item as i32;


        if !transformed || open {
            ids[mon_id::ABILITY] = mon.ability as i32;
        }
    }
    for k in 0..4 {
        if sheet_known || (transformed && mon.transform_known & (1 << k) != 0) || (!transformed && mon.moves_revealed & (1 << k) != 0) {
            ids[mon_id::MOVES + k] = mon.moves[k] as i32;
        }
    }
    if sheet_known && rules.terastallization {
        ids[mon_id::TERA_TYPE] = mon.tera.tera_type.map_or(0, |t| t as i32 + 1);
    }
    let s = &battle.sides[side as usize];
    f[mf::IN_BATTLE] = 1.0;
    let mut active = [s.active[0] as usize == index, s.active[1] as usize == index];


    let mut src = mon;
    let mut hidden_holder = false;
    let mut seen_fainted = false;
    if !mine {
        let disguised = |m: &engine_core::mon::Mon| m.illusion.is_some() && !m.flags.has(mon_flags::ILLUSION_EXPOSED);
        if let Some(k) = (0..2).find(|&k| s.mons[s.active[k] as usize].illusion == Some(index as u8) && disguised(&s.mons[s.active[k] as usize])) {
            src = &s.mons[s.active[k] as usize];
            active[k] = true;
        } else if disguised(mon) {
            active = [false, false];
            hidden_holder = true;
        } else {
            seen_fainted = mon.flags.has(mon_flags::SEEN_FAINTED);
        }
    }


    let shown_types = if !std::ptr::eq(src, mon) && src.tera.active && src.tera.typed() { &src.types } else { &mon.types };
    for k in 0..2 {
        ids[mon_id::TYPES + k] = shown_types[k].map_or(0, |t| t as i32 + 1);
    }
    if active[0] {
        f[mf::ACTIVE_A] = 1.0;
    }
    if active[1] {
        f[mf::ACTIVE_B] = 1.0;
    }
    let fainted = src.is_fainted() || seen_fainted;
    f[mf::FAINTED] = fainted as u8 as f32;
    f[mf::HP] = if seen_fainted {
        0.0
    } else if mine {
        mon.hp as f32 / mon.max_hp.max(1) as f32
    } else {
        let scale = battle.rules().shown_hp_scale;


        let mut shown = *src;
        if !sheet_known {
            shown.hp -= shown.regen_hidden.min(shown.hp.saturating_sub(1));
        }
        shown_hp(&shown, scale, battle.rules().shown_hp_rounds_up) as f32 / scale as f32
    };
    let status = match src.status {
        Status::None => 0,
        Status::Burn => 1,
        Status::Freeze => 2,
        Status::Paralysis => 3,
        Status::Poison => 4,
        Status::Toxic => 5,
        Status::Sleep => 6,
    };
    f[mf::STATUS + status] = 1.0;
    if src.status == Status::Toxic {
        f[mf::TOXIC_STAGE] = src.status_counter as f32 / 15.0;
    }
    if !hidden_holder {
        for k in 0..7 {
            f[mf::BOOSTS + k] = src.boosts[k] as f32 / 6.0;
        }
    }
    f[mf::MEGA_ACTIVE] = src.mega.active as u8 as f32;

    let ultra = engine_core::items::is_ultra_burst(mon.item, engine_core::items::pre_transform_species(mon));
    f[mf::CAN_MEGA] = (sheet_known
        && ((!s.forme_change_used(ultra) && !mon.mega.active && engine_core::items::mega_target(rules, mon).is_some())
            || z_capable(battle, side, mon.item, mon.species, &mon.moves)
            || engine_core::legal::mon_can_terastallize(rules, s, mon)
            || mon_can_dynamax(rules, s, mon))) as u8 as f32;
    f[mf::TERASTALLIZED] = src.tera.active as u8 as f32;
    f[mf::STELLAR_LEFT] = stellar_left(src);
    f[mf::COMMANDING] = (src.flags.has(mon_flags::COMMANDING) && !src.is_fainted()) as u8 as f32;


    let dynamaxed = src.flags.has(mon_flags::DYNAMAXED) && !src.is_fainted();
    if dynamaxed {
        f[mf::DYNAMAX_TURNS] = 3u8.saturating_sub(src.dynamax_turns) as f32 / 3.0;
    }
    f[mf::GIGANTAMAX] = (rules.dynamax && mon.flags.has(mon_flags::GIGANTAMAX) && (sheet_known || (dynamaxed && std::ptr::eq(src, mon)))) as u8 as f32;
    if !fainted {
        f[mf::CHI_STRIKE] = src.volatiles.conds.turns(engine_core::mon::condition_ids::GMAXCHISTRIKE).unwrap_or(0) as f32 / 3.0;
    }
    if (active[0] || active[1]) && !fainted {
        f[mf::TURNS_ACTIVE] = src.turns_active.min(5) as f32 / 5.0;
        f[mf::CONFUSED] = (src.confusion_turns > 0) as u8 as f32;
        f[mf::TAUNTED] = (src.taunt_turns > 0) as u8 as f32;
        f[mf::ENCORED] = (src.encore_turns > 0) as u8 as f32;
        f[mf::DISABLED] = (src.disable_turns > 0) as u8 as f32;
        f[mf::SUBSTITUTE] = (src.sub_hp > 0) as u8 as f32;
        f[mf::PROTECT_STREAK] = (src.protect_counter > 0) as u8 as f32;

        f[mf::PERISH] = src.perish_turns.min(3) as f32 / 4.0;
        f[mf::YAWN] = (src.yawn_turns > 0) as u8 as f32;
        f[mf::PARTIALLY_TRAPPED] = (src.trap_turns > 0) as u8 as f32;
        f[mf::CHARGING] = src.volatiles.has(volatile_flags::CHARGING) as u8 as f32;
        f[mf::MUST_RECHARGE] = src.volatiles.has(volatile_flags::MUSTRECHARGE) as u8 as f32;

        f[mf::CHOICE_LOCKED] = if !sheet_known {
            false
        } else if std::ptr::eq(src, mon) {
            src.volatiles.has(volatile_flags::CHOICE_LOCKED)
        } else {

            engine_core::turn::is_choice_item(mon.item) && src.last_move != 0
        } as u8 as f32;
        f[mf::THROAT_CHOPPED] = (src.throat_chop_turns > 0) as u8 as f32;
        f[mf::HEAL_BLOCKED] = (src.heal_block_turns > 0) as u8 as f32;
        f[mf::STOCKPILE] = src.stockpile_layers as f32 / 3.0;
    }


    f[mf::HOLDS_ITEM] = ((sheet_known || battle.rules().preview_shows_items) && mon.item != 0) as u8 as f32;
    if mine {
        f[mf::STATS] = mon.max_hp as f32 / 300.0;


        if !mon.flags.has(mon_flags::TRANSFORMED) || open {
            for k in 0..5 {
                f[mf::STATS + 1 + k] = mon.stats[k] as f32 / 250.0;
            }
        }
        for k in 0..4 {
            if mon.moves[k] != 0 {

                f[mf::PP + k] = mon.pp[k] as f32 / battle.rules().max_pp(mon.moves[k]).max(1) as f32;
            }
        }
    }
}




fn shown_hp(mon: &Mon, scale: u16, rounds_up: bool) -> u32 {
    if mon.hp == 0 {
        return 0;
    }
    let (hp, max) = (mon.hp as u32 * scale as u32, mon.max_hp.max(1) as u32);
    if rounds_up {
        let shown = hp.div_ceil(max);
        return if shown == scale as u32 && mon.hp < mon.max_hp { shown - 1 } else { shown };
    }
    (hp / max).max(1)
}

fn encode_history(battle: &Battle, ctx: &ObsContext, me: u8, h: &mut [i32]) {
    let token = |packed: u8| -> i32 {
        if packed == NO_MON {
            return -1;
        }
        let (side, i) = (packed / 4, (packed % 4) as usize);
        token_of(me, side, ctx.brought[side as usize][i] as usize) as i32
    };

    let len = battle.history.len();
    let take = len.min(HISTORY_LEN);
    let start = HISTORY_LEN - take;
    for (k, e) in battle.history.iter().skip(len - take).enumerate() {
        let row = &mut h[(start + k) * EVENT_FIELDS..(start + k + 1) * EVENT_FIELDS];
        row[0] = e.kind as i32;
        row[1] = token(e.actor);
        row[2] = token(e.target);
        row[3] = if e.kind == EventKind::Move { e.subject as i32 } else { 0 };
        row[4] = if e.kind == EventKind::Switch { e.subject as i32 } else { e.outcome as i32 };
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    struct Owned {
        field: Vec<f32>,
        ids: Vec<i32>,
        feats: Vec<f32>,
        hist: Vec<i32>,
    }

    fn encode_owned(battle: &Battle, ctx: &ObsContext, me: u8) -> Owned {
        let mut o = Owned {
            field: vec![0.0; BUFFER_SIZES[0]],
            ids: vec![0; BUFFER_SIZES[1]],
            feats: vec![0.0; BUFFER_SIZES[2]],
            hist: vec![0; BUFFER_SIZES[3]],
        };
        encode(battle, ctx, me, ObsBuffers { field: &mut o.field, mon_ids: &mut o.ids, mon_features: &mut o.feats, history: &mut o.hist });
        o
    }

    fn feat(o: &Owned, token: usize, f: usize) -> f32 {
        o.feats[token * MON_FEATURES + f]
    }

    #[test]
    fn a_fresh_battle_shows_both_leads_and_hides_the_opponents_bench_and_stats() {
        let battle = test_battle();
        let ctx = ObsContext::from_battle(&battle);
        let o = encode_owned(&battle, &ctx, 0);

        for t in 0..4 {
            assert_eq!(feat(&o, t, mon_feature::IN_BATTLE), 1.0, "my mon {t}");
            assert!(feat(&o, t, mon_feature::STATS + 1) > 0.0, "my stats are visible");
        }
        assert_eq!(feat(&o, 0, mon_feature::ACTIVE_A), 1.0);
        assert_eq!(feat(&o, 1, mon_feature::ACTIVE_B), 1.0);

        assert_eq!(feat(&o, ROSTER_SIZE, mon_feature::IN_BATTLE), 1.0);
        assert_eq!(feat(&o, ROSTER_SIZE + 2, mon_feature::IN_BATTLE), 0.0);
        for t in ROSTER_SIZE..MON_TOKENS {
            assert_eq!(feat(&o, t, mon_feature::STATS + 1), 0.0);
            assert_eq!(feat(&o, t, mon_feature::PP), 0.0);
        }

        assert!(o.ids[4 * MON_IDS..6 * MON_IDS].iter().all(|&x| x == 0));
        assert_eq!(o.field[field::DECISION], 1.0);
    }

    #[test]
    fn closed_sheets_hide_the_opponents_items_abilities_and_unused_moves() {
        let mut battle = test_battle();
        let open = encode_owned(&battle, &ObsContext::from_battle(&battle), 0);
        assert_eq!(open.field[field::FORMAT], 1.0, "the champions format's slot");
        battle.format = engine_core::rules::Format::Gen5Vgc13;
        let ctx = ObsContext::from_battle(&battle);
        let o = encode_owned(&battle, &ctx, 0);
        assert_eq!(o.field[field::FORMAT + 1], 1.0, "the Gen 5 format's slot");
        let foe = ROSTER_SIZE * MON_IDS;

        assert_eq!(o.ids[mon_id::ITEM], open.ids[mon_id::ITEM]);
        assert_eq!(o.ids[foe + mon_id::SPECIES], open.ids[foe + mon_id::SPECIES]);
        assert_eq!(o.ids[foe + mon_id::ITEM], 0);
        assert_eq!(o.ids[foe + mon_id::ABILITY], 0);
        assert!(o.ids[foe + mon_id::MOVES..foe + mon_id::MOVES + 4].iter().all(|&m| m == 0));

        battle.sides[1].mons[0].moves_revealed = 1 << 0;
        let o = encode_owned(&battle, &ctx, 0);
        assert_eq!(o.ids[foe + mon_id::MOVES], battle.sides[1].mons[0].moves[0] as i32);
        assert_eq!(o.ids[foe + mon_id::MOVES + 1], 0);
    }

    #[test]
    fn both_perspectives_mirror_each_other() {
        let mut battle = test_battle();
        let ctx = ObsContext::from_battle(&battle);
        let mut rng = battle.rng;
        for _ in 0..3 {
            if let Pending::Over { .. } = battle.pending {
                break;
            }
            let actions = random_actions(&battle, &mut rng);
            engine_core::turn::step(&mut battle, actions);
        }
        let p0 = encode_owned(&battle, &ctx, 0);
        let p1 = encode_owned(&battle, &ctx, 1);

        assert_eq!(p0.ids[..MON_IDS], p1.ids[ROSTER_SIZE * MON_IDS..(ROSTER_SIZE + 1) * MON_IDS]);
        let exact = feat(&p0, 0, mon_feature::HP);
        let shown = feat(&p1, ROSTER_SIZE, mon_feature::HP);
        assert!(exact >= shown && exact - shown <= 0.0101, "{exact} vs {shown}");
    }

    #[test]
    fn history_records_moves_with_tokens_from_the_observers_perspective() {
        let mut battle = test_battle();
        let ctx = ObsContext::from_battle(&battle);
        let mut rng = battle.rng;
        let actions = random_actions(&battle, &mut rng);
        engine_core::turn::step(&mut battle, actions);
        let o = encode_owned(&battle, &ctx, 1);
        let rows: Vec<&[i32]> = o.hist.chunks(EVENT_FIELDS).filter(|r| r[0] != 0).collect();
        assert!(!rows.is_empty(), "a turn records events");
        for r in &rows {
            assert!((0..MON_TOKENS as i32).contains(&r[1]), "actor token {r:?}");
        }
    }

    fn test_battle() -> Battle {
        engine_fuzz::random_battle(7)
    }

    fn random_actions(battle: &Battle, rng: &mut engine_core::rng::Rng) -> [engine_core::action::JointAction; 2] {
        engine_fuzz::random_legal_actions(battle, rng)
    }
}
