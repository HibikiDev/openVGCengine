



use crate::{abilities_table, items_table, moves_table, species_table};


pub fn to_id(s: &str) -> String {
    s.chars().filter(|c| c.is_ascii_alphanumeric()).map(|c| c.to_ascii_lowercase()).collect()
}

fn find(names: impl Iterator<Item = &'static str>, name: &str) -> Option<u16> {
    let target = to_id(name);
    names.enumerate().find(|(_, n)| to_id(n) == target).map(|(i, _)| (i + 1) as u16)
}

pub fn species(name: &str) -> Option<species_table::SpeciesId> {
    find(species_table::SPECIES.iter().map(|s| s.name), name)
}



pub fn move_id(name: &str) -> Option<moves_table::MoveId> {
    if to_id(name).starts_with("hiddenpower") {
        return hidden_power_named_type(name).map(|_| moves_table::move_ids::HIDDENPOWER);
    }
    find(moves_table::MOVE_NAMES.iter().copied(), name)
}



pub fn hidden_power_named_type(name: &str) -> Option<Option<crate::type_chart::Type>> {
    let id = to_id(name);
    let rest = id.strip_prefix("hiddenpower")?;
    if rest.is_empty() {
        return Some(None);
    }
    crate::type_chart::Type::ALL.iter().find(|t| to_id(&format!("{t:?}")) == rest).map(|&t| Some(t))
}

pub fn ability(name: &str) -> Option<abilities_table::AbilityId> {
    find(abilities_table::ABILITY_NAMES.iter().copied(), name)
}

pub fn item(name: &str) -> Option<items_table::ItemId> {
    find(items_table::ITEM_NAMES.iter().copied(), name)
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn names_resolve_whatever_their_spelling() {
        assert_eq!(move_id("Close Combat"), Some(moves_table::move_ids::CLOSECOMBAT));
        assert_eq!(move_id("closecombat"), Some(moves_table::move_ids::CLOSECOMBAT));
        assert_eq!(species("Salamence"), Some(species_table::species_ids::SALAMENCE));
        assert_eq!(item("Choice Scarf"), Some(items_table::item_ids::CHOICESCARF));
        assert_eq!(ability("SNOW WARNING"), Some(abilities_table::ability_ids::SNOWWARNING));
        assert_eq!(move_id("Not A Move"), None);
        assert_eq!(move_id("Hidden Power [Fire]"), Some(moves_table::move_ids::HIDDENPOWER));
        assert_eq!(hidden_power_named_type("Hidden Power [Fire]"), Some(Some(crate::type_chart::Type::Fire)));
        assert_eq!(hidden_power_named_type("hiddenpower"), Some(None));
        assert_eq!(move_id("Hidden Power [Sound]"), None);
    }
}
