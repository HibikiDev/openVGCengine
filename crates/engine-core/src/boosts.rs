








pub const BOOST_NUMERATOR: [u32; 7] = [2, 3, 4, 5, 6, 7, 8];
pub const BOOST_DENOMINATOR: u32 = 2;


#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Boost {
    Atk = 0,
    Def = 1,
    SpA = 2,
    SpD = 3,
    Spe = 4,
    Accuracy = 5,
    Evasion = 6,
}




pub fn apply_boost(stat: u32, boost: i8) -> u32 {
    let boost = boost.clamp(-6, 6);
    if boost >= 0 {
        stat * BOOST_NUMERATOR[boost as usize] / BOOST_DENOMINATOR
    } else {
        stat * BOOST_DENOMINATOR / BOOST_NUMERATOR[(-boost) as usize]
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn neutral_boost_is_identity() {
        assert_eq!(apply_boost(100, 0), 100);
    }

    #[test]
    fn positive_boosts_match_showdown_table() {

        assert_eq!(apply_boost(100, 1), 150);
        assert_eq!(apply_boost(100, 2), 200);
        assert_eq!(apply_boost(100, 6), 400);
    }

    #[test]
    fn negative_boosts_are_reciprocal() {
        assert_eq!(apply_boost(100, -1), 66);
        assert_eq!(apply_boost(100, -6), 25);
    }

    #[test]
    fn out_of_range_boosts_clamp() {
        assert_eq!(apply_boost(100, 10), apply_boost(100, 6));
        assert_eq!(apply_boost(100, -10), apply_boost(100, -6));
    }
}
