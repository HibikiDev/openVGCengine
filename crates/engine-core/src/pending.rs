

#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Pending {

    Turn,


    ForcedSwitch { side0: bool, side1: bool },

    Over { winner: Option<u8> },
}

impl Default for Pending {
    fn default() -> Self {
        Pending::Turn
    }
}
