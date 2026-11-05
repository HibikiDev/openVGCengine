












use engine_core::mon::Mon;
use engine_core::stats::Nature;
use engine_data::species_table::{self, SpeciesId};

pub fn species_id_for(name: &str) -> SpeciesId {
    let target = crate::fixture_io::to_id(name);
    (1..=species_table::SPECIES_COUNT)
        .find(|&id| crate::fixture_io::to_id(species_table::SPECIES[id - 1].name) == target)
        .unwrap_or_else(|| panic!("fixtures::species_id_for: no mapping for \"{name}\" - check crates/engine-data/src/species_table.rs for the exact name")) as SpeciesId
}






#[allow(clippy::too_many_arguments)]
pub fn build_mon(
    rules: &engine_core::rules::Rules,
    species_name: &str,
    nature_id: &str,
    stat_points: [u32; 6],
    ivs: [u32; 6],
    moves: [u16; 4],
    ability: engine_data::abilities_table::AbilityId,
    item: engine_data::items_table::ItemId,
    gender: engine_core::team::SetGender,
) -> Mon {

    let nature = Nature::from_id(&nature_id.to_lowercase()).unwrap_or_else(|| panic!("unknown nature \"{nature_id}\""));
    engine_core::team::build_mon_in(rules, &engine_core::team::MonSet {
        species: species_id_for(species_name),
        ability,
        item,
        moves,
        nature,
        stat_points: stat_points.map(|p| p as u8),
        ivs: ivs.map(|v| v as u8),
        gender,
        happiness: 255,
        tera_type: None,
        dynamax_level: 10,
        gigantamax: false,
    })
}
