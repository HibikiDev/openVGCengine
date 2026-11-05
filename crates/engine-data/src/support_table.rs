







use crate::abilities_table::AbilityId;
use crate::items_table::{item_ids, ItemId};

pub const UNPORTED_ABILITIES: &[AbilityId] = &[

];

pub const UNPORTED_ITEMS: &[ItemId] = &[
    item_ids::BERRY,
    item_ids::BERSERKGENE,
    item_ids::BITTERBERRY,
    item_ids::BURNTBERRY,
    item_ids::GOLDBERRY,
    item_ids::ICEBERRY,
    item_ids::MINTBERRY,
    item_ids::MIRACLEBERRY,
    item_ids::MYSTERYBERRY,
    item_ids::PINKBOW,
    item_ids::POLKADOTBOW,
    item_ids::PRZCUREBERRY,
    item_ids::PSNCUREBERRY,
];

pub fn ability_supported(id: AbilityId) -> bool {
    !UNPORTED_ABILITIES.contains(&id)
}

pub fn item_supported(id: ItemId) -> bool {
    !UNPORTED_ITEMS.contains(&id)
}
