





















#[derive(Clone, Copy, PartialEq, Eq, Debug)]
#[repr(u8)]
pub enum Stat {
    Atk = 0,
    Def = 1,
    SpA = 2,
    SpD = 3,
    Spe = 4,
}



#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub struct Nature {
    pub plus: Stat,
    pub minus: Stat,
}

impl Nature {



    pub const fn neutral() -> Nature {
        Nature { plus: Stat::Atk, minus: Stat::Atk }
    }




    pub fn from_id(id: &str) -> Option<Nature> {
        use Stat::*;

        let (plus, minus) = match id {
            "hardy" => (Atk, Atk),
            "lonely" => (Atk, Def),
            "brave" => (Atk, Spe),
            "adamant" => (Atk, SpA),
            "naughty" => (Atk, SpD),
            "bold" => (Def, Atk),
            "docile" => (Def, Def),
            "relaxed" => (Def, Spe),
            "impish" => (Def, SpA),
            "lax" => (Def, SpD),
            "timid" => (Spe, Atk),
            "hasty" => (Spe, Def),
            "serious" => (Spe, Spe),
            "jolly" => (Spe, SpA),
            "naive" => (Spe, SpD),
            "modest" => (SpA, Atk),
            "mild" => (SpA, Def),
            "quiet" => (SpA, Spe),
            "bashful" => (SpA, SpA),
            "rash" => (SpA, SpD),
            "calm" => (SpD, Atk),
            "gentle" => (SpD, Def),
            "sassy" => (SpD, Spe),
            "careful" => (SpD, SpA),
            "quirky" => (SpD, SpD),
            _ => return None,
        };
        Some(Nature { plus, minus })
    }
}




fn trunc16(num: u32) -> u32 {
    num % 65536
}




pub fn calc_stat(stat: Stat, base: u32, stat_points: u32, nature: Nature) -> u32 {
    let mut s = base + stat_points + 20;
    if nature.plus == stat && nature.plus != nature.minus {
        s = trunc16(s * 110) / 100;
    } else if nature.minus == stat && nature.plus != nature.minus {
        s = trunc16(s * 90) / 100;
    }
    s
}


pub fn calc_hp(base: u32, stat_points: u32) -> u32 {
    base + stat_points + 75
}



pub fn calc_stat_ev(stat: Stat, base: u32, ev: u32, iv: u32, level: u32, nature: Nature) -> u32 {
    let mut s = (2 * base + iv + ev / 4) * level / 100 + 5;
    if nature.plus == stat && nature.plus != nature.minus {
        s = trunc16(s * 110) / 100;
    } else if nature.minus == stat && nature.plus != nature.minus {
        s = trunc16(s * 90) / 100;
    }
    s
}


pub fn calc_hp_ev(base: u32, ev: u32, iv: u32, level: u32) -> u32 {
    (2 * base + iv + ev / 4 + 100) * level / 100 + 10
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn gen5_formula_at_level_50() {


        let jolly = Nature::from_id("jolly").unwrap();
        assert_eq!(calc_hp_ev(108, 0, 31, 50), 183);
        assert_eq!(calc_stat_ev(Stat::Atk, 130, 252, 31, 50, jolly), 182);
        assert_eq!(calc_stat_ev(Stat::Def, 95, 4, 31, 50, jolly), 116);
        assert_eq!(calc_stat_ev(Stat::Spe, 102, 252, 31, 50, jolly), 169);

        let brave = Nature::from_id("brave").unwrap();
        assert_eq!(calc_stat_ev(Stat::Spe, 30, 0, 0, 50, brave), 31);
    }

    #[test]
    fn max_stat_points_adamant_charizard_atk() {

        let nature = Nature::from_id("adamant").unwrap();
        let atk = calc_stat(Stat::Atk, 84, 32, nature);
        assert_eq!(atk, 149);
    }

    #[test]
    fn neutral_nature_no_change() {
        let nature = Nature::from_id("hardy").unwrap();
        let def = calc_stat(Stat::Def, 78, 0, nature);
        assert_eq!(def, 98);
    }

    #[test]
    fn zero_investment_is_base_plus_twenty() {
        let nature = Nature::from_id("serious").unwrap();
        assert_eq!(calc_stat(Stat::Atk, 100, 0, nature), 120);
    }

    #[test]
    fn hp_formula_has_no_nature_or_level_term() {

        assert_eq!(calc_hp(78, 4), 157);
    }

    #[test]
    fn unknown_nature_id_fails_loudly() {
        assert!(Nature::from_id("not-a-nature").is_none());
    }
}
