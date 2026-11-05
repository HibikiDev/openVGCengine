


#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Status {
    #[default]
    None = 0,
    Burn = 1,
    Freeze = 2,
    Paralysis = 3,
    Poison = 4,
    Toxic = 5,
    Sleep = 6,
}









pub fn is_immune_to_status<const N: usize>(types: [Option<engine_data::type_chart::Type>; N], status: Status) -> bool {
    use engine_data::type_chart::Type;
    let immune_type = match status {
        Status::Paralysis => Type::Electric,
        Status::Burn => Type::Fire,
        Status::Freeze => Type::Ice,
        Status::Poison | Status::Toxic => return types.into_iter().flatten().any(|t| t == Type::Poison || t == Type::Steel),
        Status::None | Status::Sleep => return false,
    };
    types.into_iter().flatten().any(|t| t == immune_type)
}

#[cfg(test)]
mod tests {
    use super::*;
    use engine_data::type_chart::Type;

    #[test]
    fn electric_immune_to_paralysis() {
        assert!(is_immune_to_status([Some(Type::Electric), None], Status::Paralysis));
        assert!(!is_immune_to_status([Some(Type::Normal), None], Status::Paralysis));
    }

    #[test]
    fn fire_immune_to_burn() {
        assert!(is_immune_to_status([Some(Type::Fire), Some(Type::Flying)], Status::Burn));
    }

    #[test]
    fn ice_immune_to_freeze() {
        assert!(is_immune_to_status([Some(Type::Ice), None], Status::Freeze));
    }

    #[test]
    fn poison_and_steel_immune_to_poison_and_toxic() {
        assert!(is_immune_to_status([Some(Type::Poison), None], Status::Toxic));
        assert!(is_immune_to_status([Some(Type::Steel), None], Status::Poison));
        assert!(!is_immune_to_status([Some(Type::Normal), None], Status::Toxic));
    }

    #[test]
    fn sleep_has_no_type_immunity() {


        assert!(!is_immune_to_status([Some(Type::Grass), None], Status::Sleep));
    }
}
