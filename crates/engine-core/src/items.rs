




use crate::action::Actor;
use crate::battle::Battle;
use crate::mon::Mon;
use crate::turn::{apply_boosts, apply_damage_at, mon_at, mon_at_mut};
use engine_data::items_table::item_ids;





pub fn foe_has_unnerve(battle: &Battle, holder: Actor) -> bool {
    use engine_data::abilities_table::ability_ids;
    let foe = &battle.sides[holder.other_side() as usize];
    (0..2).any(|slot| {
        let m = &foe.mons[foe.active[slot] as usize];


        !m.is_fainted()
            && matches!(m.ability, ability_ids::UNNERVE | ability_ids::ASONEGLASTRIER | ability_ids::ASONESPECTRIER)
            && m.flags.has(crate::mon::mon_flags::UNNERVED)
    })
}


pub fn mail_locked(item: engine_data::items_table::ItemId) -> bool {
    item == engine_data::items_table::item_ids::MAIL
}



pub fn mega_forme(item: u16, species: u16, moves: &[u16], dragon_ascent: bool) -> Option<u16> {
    use engine_data::species_table::species_ids::{RAYQUAZA, RAYQUAZAMEGA};
    engine_data::items_table::mega_forme_for(item, species)
        .or_else(|| (dragon_ascent && species == RAYQUAZA && moves.contains(&engine_data::moves_table::move_ids::DRAGONASCENT)).then_some(RAYQUAZAMEGA))

        .or_else(|| is_ultra_burst(item, species).then_some(engine_data::species_table::species_ids::NECROZMAULTRA))
}



pub fn is_ultra_burst(item: u16, species: u16) -> bool {
    use engine_data::species_table::species_ids::{NECROZMADAWNWINGS, NECROZMADUSKMANE};
    item == engine_data::items_table::item_ids::ULTRANECROZIUMZ && matches!(species, NECROZMADAWNWINGS | NECROZMADUSKMANE)
}


pub fn pre_transform_species(mon: &crate::mon::Mon) -> u16 {
    if mon.flags.has(crate::mon::mon_flags::TRANSFORMED) { mon.pre_transform_species } else { mon.species }
}



pub fn mega_target(rules: &crate::rules::Rules, mon: &crate::mon::Mon) -> Option<u16> {
    let transformed = mon.flags.has(crate::mon::mon_flags::TRANSFORMED);
    let (species, moves) = if transformed { (mon.pre_transform_species, mon.base_moves) } else { (mon.species, mon.moves) };
    mega_forme(mon.item, species, &moves, rules.dragon_ascent_mega)
}



pub fn species_locked_item(item: u16, species: u16) -> bool {
    use engine_data::items_table::item_ids;
    use engine_data::species_table::species_ids::{GROUDON, GROUDONPRIMAL, KYOGRE, KYOGREPRIMAL};
    engine_data::items_table::MEGA_STONES.iter().any(|&(i, base, mega)| i == item && (species == base || species == mega))
        || (item == item_ids::REDORB && matches!(species, GROUDON | GROUDONPRIMAL))
        || (item == item_ids::BLUEORB && matches!(species, KYOGRE | KYOGREPRIMAL))

        || engine_data::z_table::crystal(item).is_some()

        || (item == item_ids::BOOSTERENERGY && is_paradox(species))

        || (item == item_ids::RUSTEDSWORD
            && matches!(species, engine_data::species_table::species_ids::ZACIAN | engine_data::species_table::species_ids::ZACIANCROWNED))
        || (item == item_ids::RUSTEDSHIELD
            && matches!(species, engine_data::species_table::species_ids::ZAMAZENTA | engine_data::species_table::species_ids::ZAMAZENTACROWNED))

        || (item == item_ids::ADAMANTCRYSTAL
            && matches!(species, engine_data::species_table::species_ids::DIALGA | engine_data::species_table::species_ids::DIALGAORIGIN))
        || (item == item_ids::LUSTROUSGLOBE
            && matches!(species, engine_data::species_table::species_ids::PALKIA | engine_data::species_table::species_ids::PALKIAORIGIN))
        || (item == item_ids::GRISEOUSCORE
            && matches!(species, engine_data::species_table::species_ids::GIRATINA | engine_data::species_table::species_ids::GIRATINAORIGIN))

        || (matches!(item, item_ids::WELLSPRINGMASK | item_ids::HEARTHFLAMEMASK | item_ids::CORNERSTONEMASK) && is_ogerpon(species))

        || (memory_type(item).is_some() && is_silvally(species))

        || (plate_type(item).is_some() && is_arceus(species))

        || (drive_type(item).is_some() && is_genesect(species))
}


pub fn is_arceus(species: u16) -> bool {
    (engine_data::species_table::species_ids::ARCEUS..=engine_data::species_table::species_ids::ARCEUSWATER).contains(&species)
}


fn is_genesect(species: u16) -> bool {
    (engine_data::species_table::species_ids::GENESECT..=engine_data::species_table::species_ids::GENESECTSHOCK).contains(&species)
}


pub fn plate_type(item: u16) -> Option<engine_data::type_chart::Type> {
    use engine_data::type_chart::Type;
    Some(match item {
        item_ids::MEADOWPLATE => Type::Grass,
        item_ids::PIXIEPLATE => Type::Fairy,
        item_ids::FLAMEPLATE => Type::Fire,
        item_ids::DREADPLATE => Type::Dark,
        item_ids::SPLASHPLATE => Type::Water,
        item_ids::MINDPLATE => Type::Psychic,
        item_ids::SKYPLATE => Type::Flying,
        item_ids::ICICLEPLATE => Type::Ice,
        item_ids::EARTHPLATE => Type::Ground,
        item_ids::STONEPLATE => Type::Rock,
        item_ids::ZAPPLATE => Type::Electric,
        item_ids::FISTPLATE => Type::Fighting,
        item_ids::DRACOPLATE => Type::Dragon,
        item_ids::IRONPLATE => Type::Steel,
        item_ids::TOXICPLATE => Type::Poison,
        item_ids::INSECTPLATE => Type::Bug,
        item_ids::SPOOKYPLATE => Type::Ghost,
        _ => return None,
    })
}


pub fn drive_type(item: u16) -> Option<engine_data::type_chart::Type> {
    use engine_data::type_chart::Type;
    Some(match item {
        item_ids::DOUSEDRIVE => Type::Water,
        item_ids::SHOCKDRIVE => Type::Electric,
        item_ids::BURNDRIVE => Type::Fire,
        item_ids::CHILLDRIVE => Type::Ice,
        _ => return None,
    })
}


fn is_silvally(species: u16) -> bool {
    (engine_data::species_table::species_ids::SILVALLY..=engine_data::species_table::species_ids::SILVALLYWATER).contains(&species)
}


pub fn memory_type(item: u16) -> Option<engine_data::type_chart::Type> {
    use engine_data::type_chart::Type;
    Some(match item {
        item_ids::BUGMEMORY => Type::Bug,
        item_ids::DARKMEMORY => Type::Dark,
        item_ids::DRAGONMEMORY => Type::Dragon,
        item_ids::ELECTRICMEMORY => Type::Electric,
        item_ids::FAIRYMEMORY => Type::Fairy,
        item_ids::FIGHTINGMEMORY => Type::Fighting,
        item_ids::FIREMEMORY => Type::Fire,
        item_ids::FLYINGMEMORY => Type::Flying,
        item_ids::GHOSTMEMORY => Type::Ghost,
        item_ids::GRASSMEMORY => Type::Grass,
        item_ids::GROUNDMEMORY => Type::Ground,
        item_ids::ICEMEMORY => Type::Ice,
        item_ids::POISONMEMORY => Type::Poison,
        item_ids::PSYCHICMEMORY => Type::Psychic,
        item_ids::ROCKMEMORY => Type::Rock,
        item_ids::STEELMEMORY => Type::Steel,
        item_ids::WATERMEMORY => Type::Water,
        _ => return None,
    })
}

fn is_ogerpon(species: u16) -> bool {
    use engine_data::species_table::species_ids::*;
    matches!(
        species,
        OGERPON
            | OGERPONWELLSPRING
            | OGERPONHEARTHFLAME
            | OGERPONCORNERSTONE
            | OGERPONTEALTERA
            | OGERPONWELLSPRINGTERA
            | OGERPONHEARTHFLAMETERA
            | OGERPONCORNERSTONETERA
    )
}



fn is_paradox(species: u16) -> bool {
    use engine_data::species_table::species_ids::*;
    matches!(
        species,
        GREATTUSK | SCREAMTAIL | BRUTEBONNET | FLUTTERMANE | SLITHERWING | SANDYSHOCKS | ROARINGMOON | WALKINGWAKE | IRONTREADS | IRONBUNDLE
            | IRONHANDS | IRONJUGULIS | IRONMOTH | IRONTHORNS | IRONVALIANT | IRONLEAVES
    )
}




pub fn knock_off_boosts(holder: &Mon) -> bool {
    holder.item != crate::ids::NONE_ID && !species_locked_item(holder.item, pre_transform_species(holder))
}






pub fn knock_off_removable(holder: &Mon, taker_species: u16) -> bool {
    use engine_data::abilities_table::ability_ids;


    let sticky = holder.ability == ability_ids::STICKYHOLD && holder.hp > 0 && holder.item != engine_data::items_table::item_ids::STICKYBARB;
    if holder.item == crate::ids::NONE_ID || sticky {
        return false;
    }
    !species_locked_item(holder.item, taker_species)
}









pub fn survive_lethal_hit(mon: &mut Mon, incoming_damage: u16) -> u16 {
    if mon.effective_item() == item_ids::FOCUSSASH && mon.hp == mon.max_hp && incoming_damage >= mon.hp {
        crate::turn::spend_item(mon);
        mon.hp - 1
    } else {
        incoming_damage
    }
}






pub fn contact_punish(battle: &mut Battle, attacker: Actor, defender: Actor, contact: bool, rng: &mut crate::rng::Rng) -> i64 {
    if contact && mon_at(battle, defender).effective_item() == item_ids::ROCKYHELMET {


        if mon_at(battle, attacker).hp > 0 {
            crate::turn::damage_event_ties(battle, attacker, rng);
        }
        if mon_at(battle, attacker).ability == engine_data::abilities_table::ability_ids::MAGICGUARD {
            return 0;
        }
        let max_hp = mon_at(battle, attacker).base_max_hp;
        crate::turn::focus_band_roll_at(battle, attacker, rng);
        let dealt = apply_damage_at(battle, attacker, (max_hp / 6).max(1)) as i64;
        crate::turn::instafaint(battle, attacker);
        dealt
    } else {
        0
    }
}











pub fn check_eject_button(battle: &mut Battle, target: Actor) {

    if mon_at(battle, target).effective_item() != item_ids::EJECTBUTTON || mon_at(battle, target).volatiles.has(crate::mon::volatile_flags::DRAG_PENDING) {
        return;
    }
    crate::turn::request_voluntary_switch(battle, target, true);
    if mon_at(battle, target).volatiles.has(crate::mon::volatile_flags::VOLUNTARY_SWITCH) {
        let holder = mon_at_mut(battle, target);
        holder.item = crate::ids::NONE_ID;
        holder.volatiles.set(crate::mon::volatile_flags::ITEM_CONSUMED);
    }
}















pub fn apply_terrain_seed(mon: &mut Mon, terrain: crate::field::Terrain, trick_room: bool) -> bool {
    use crate::field::Terrain;
    use crate::stats::Stat;
    if trick_room && mon.effective_item() == item_ids::ROOMSERVICE {
        crate::turn::spend_item(mon);
        crate::turn::apply_boosts(mon, [0, 0, 0, 0, -1, 0, 0]);
        return true;
    }
    let stat = match (mon.effective_item(), terrain) {
        (item_ids::ELECTRICSEED, Terrain::Electric) | (item_ids::GRASSYSEED, Terrain::Grassy) => Stat::Def,
        (item_ids::MISTYSEED, Terrain::Misty) | (item_ids::PSYCHICSEED, Terrain::Psychic) => Stat::SpD,
        _ => return false,
    };
    crate::turn::spend_item(mon);







    let mut deltas = [0i8; 7];
    deltas[stat as usize] = 1;
    apply_boosts(mon, deltas);
    true
}

#[cfg(test)]
mod tests {
    use super::*;
    use crate::turn::tests::test_mon;
    use engine_data::type_chart::Type;

    #[test]
    fn focus_sash_reduces_a_lethal_hit_from_full_hp_to_one() {
        let mut mon = test_mon([Some(Type::Normal), None], [100; 5], [0; 4]);
        mon.item = item_ids::FOCUSSASH;
        let hp_before = mon.hp;
        let dealt = survive_lethal_hit(&mut mon, hp_before + 50);
        assert_eq!(dealt, hp_before - 1);
        assert_eq!(mon.item, crate::ids::NONE_ID, "sash is consumed");
    }

    #[test]
    fn focus_sash_does_nothing_below_full_hp() {
        let mut mon = test_mon([Some(Type::Normal), None], [100; 5], [0; 4]);
        mon.item = item_ids::FOCUSSASH;
        mon.hp -= 1;
        let hp_before = mon.hp;
        let dealt = survive_lethal_hit(&mut mon, hp_before + 50);
        assert_eq!(dealt, hp_before + 50, "sash doesn't trigger below full HP");
        assert_eq!(mon.item, item_ids::FOCUSSASH, "not consumed");
    }

    #[test]
    fn focus_sash_does_nothing_without_the_item() {
        let mut mon = test_mon([Some(Type::Normal), None], [100; 5], [0; 4]);
        let hp_before = mon.hp;
        let dealt = survive_lethal_hit(&mut mon, hp_before + 50);
        assert_eq!(dealt, hp_before + 50);
    }

    #[test]
    fn focus_sash_does_nothing_against_non_lethal_damage() {
        let mut mon = test_mon([Some(Type::Normal), None], [100; 5], [0; 4]);
        mon.item = item_ids::FOCUSSASH;
        let hp_before = mon.hp;
        let dealt = survive_lethal_hit(&mut mon, hp_before - 10);
        assert_eq!(dealt, hp_before - 10);
        assert_eq!(mon.item, item_ids::FOCUSSASH, "not consumed - this hit wasn't lethal anyway");
    }

    #[test]
    fn rocky_helmet_damages_an_attacker_on_a_contact_hit() {
        use crate::turn::tests::test_battle;

        let mut holder = test_mon([Some(Type::Normal), None], [1; 5], [0; 4]);
        holder.item = item_ids::ROCKYHELMET;
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [80; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let attacker = Actor { side: 0, slot: 0 };
        let defender = Actor { side: 1, slot: 0 };
        let hp_before = mon_at(&battle, attacker).hp;
        contact_punish(&mut battle, attacker, defender, true, &mut crate::rng::Rng::new(0));
        let max_hp = mon_at(&battle, attacker).max_hp;
        assert_eq!(mon_at(&battle, attacker).hp, hp_before - (max_hp / 6).max(1), "1/6 max HP recoil to the attacker");
    }

    #[test]
    fn rocky_helmet_does_nothing_on_a_non_contact_hit() {
        use crate::turn::tests::test_battle;

        let mut holder = test_mon([Some(Type::Normal), None], [1; 5], [0; 4]);
        holder.item = item_ids::ROCKYHELMET;
        let mut battle = test_battle(
            [test_mon([Some(Type::Normal), None], [80; 5], [0; 4]), test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            [holder, test_mon([Some(Type::Normal), None], [1; 5], [0; 4])],
            1,
        );
        let attacker = Actor { side: 0, slot: 0 };
        let defender = Actor { side: 1, slot: 0 };
        let hp_before = mon_at(&battle, attacker).hp;
        contact_punish(&mut battle, attacker, defender, false, &mut crate::rng::Rng::new(0));
        assert_eq!(mon_at(&battle, attacker).hp, hp_before, "no recoil without contact");
    }

    #[test]
    fn multitype_arceus_takes_its_plates_type_and_plates_and_drives_stay_with_their_owner() {
        use crate::rules::Rules;
        use engine_data::abilities_table::ability_ids;
        use engine_data::species_table::species_ids as sp;
        let types = |r: &Rules, s, a, i| crate::mon::species_types_for(r, s, a, i);
        for r in [&Rules::GEN5_VGC13, &Rules::GEN7_VGC, &Rules::GEN9_SV] {
            assert_eq!(types(r, sp::ARCEUSFIRE, ability_ids::MULTITYPE, item_ids::FLAMEPLATE), [Some(Type::Fire), None, None]);
            assert_eq!(types(r, sp::ARCEUS, ability_ids::MULTITYPE, item_ids::LEFTOVERS), [Some(Type::Normal), None, None]);
        }

        assert_eq!(types(&Rules::GEN7_VGC, sp::ARCEUSFIRE, ability_ids::PRESSURE, item_ids::FLAMEPLATE), [Some(Type::Normal), None, None]);
        assert_eq!(types(&Rules::GEN9_SV, sp::ARCEUSFIRE, ability_ids::PRESSURE, item_ids::FLAMEPLATE), [Some(Type::Fire), None, None]);
        assert!(species_locked_item(item_ids::FLAMEPLATE, sp::ARCEUS) && species_locked_item(item_ids::FLAMEPLATE, sp::ARCEUSWATER));
        assert!(!species_locked_item(item_ids::FLAMEPLATE, sp::SILVALLY));
        assert!(species_locked_item(item_ids::DOUSEDRIVE, sp::GENESECTDOUSE) && species_locked_item(item_ids::BURNDRIVE, sp::GENESECT));
        assert!(!species_locked_item(item_ids::DOUSEDRIVE, sp::ARCEUS));
        assert_eq!(drive_type(item_ids::CHILLDRIVE), Some(Type::Ice));
    }
}
