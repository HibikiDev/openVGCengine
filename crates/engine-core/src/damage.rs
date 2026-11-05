














use engine_data::type_chart::Type;

use crate::rng::{Rng, Site};





#[derive(Clone, Copy, PartialEq, Eq, Debug)]
pub enum Effectiveness {
    Immune,
    Normal(i8),
}






pub type TypeChart = [[u8; engine_data::type_chart::TYPE_COUNT]; engine_data::type_chart::TYPE_COUNT];

pub fn type_effectiveness<const N: usize>(chart: &TypeChart, move_type: Type, defender_types: [Option<Type>; N]) -> Effectiveness {
    let mut stage: i32 = 0;
    for ty in defender_types.into_iter().flatten() {
        match chart[ty as usize][move_type as usize] {
            3 => return Effectiveness::Immune,
            1 => stage += 1,
            2 => stage -= 1,
            _ => {}
        }
    }
    Effectiveness::Normal(stage.clamp(-6, 6) as i8)
}







pub fn modify(value: i64, numerator: i64, denominator: i64) -> i64 {
    let modifier = numerator * 4096 / denominator;
    (value * modifier + 2047) / 4096
}













pub fn round_frac(value: i64, numerator: i64, denominator: i64) -> i64 {
    (2 * value * numerator + denominator) / (2 * denominator)
}



pub fn base_damage(level: u32, base_power: u32, attack: u32, defense: u32) -> i64 {
    let level_factor = (2 * level as i64 / 5) + 2;
    let step = level_factor * base_power as i64 * attack as i64;
    (step / defense as i64) / 50
}



pub fn apply_spread_modifier(damage: i64) -> i64 {
    modify(damage, 3, 4)
}



pub fn apply_crit(damage: i64, (num, den): (u8, u8)) -> i64 {
    damage * num as i64 / den as i64
}






pub fn apply_random_roll_value(damage: i64, r: i64) -> i64 {
    (damage * (100 - r)) / 100
}



pub fn apply_random_roll(damage: i64, rng: &mut Rng) -> i64 {
    apply_random_roll_value(damage, rng.random(16) as i64)
}



pub fn apply_random_roll_at(damage: i64, rng: &mut Rng) -> i64 {
    apply_random_roll_value(damage, rng.random_at(Site::DamageRoll, 16) as i64)
}




pub fn apply_stab(damage: i64, stab: (i64, i64)) -> i64 {
    if stab == (1, 1) {
        return damage;
    }
    modify(damage, stab.0, stab.1)
}


pub fn apply_effectiveness(damage: i64, eff: Effectiveness) -> i64 {
    match eff {
        Effectiveness::Immune => 0,
        Effectiveness::Normal(stage) => {
            let mut d = damage;
            if stage > 0 {
                for _ in 0..stage {
                    d *= 2;
                }
            } else {
                for _ in 0..(-stage) {
                    d /= 2;
                }
            }
            d
        }
    }
}




pub fn apply_burn(damage: i64, attacker_burned: bool, is_physical: bool) -> i64 {
    if attacker_burned && is_physical {
        modify(damage, 1, 2)
    } else {
        damage
    }
}





pub fn apply_weather_modifier(damage: i64, weather_modifier: Option<(i64, i64)>) -> i64 {
    match weather_modifier {
        Some((num, den)) => modify(damage, num, den),
        None => damage,
    }
}







pub const LIFE_ORB_MODIFIER: (i64, i64) = (5324, 4096);




















pub(crate) fn chain_two(a: (i64, i64), b: (i64, i64)) -> (i64, i64) {
    let mod_a = a.0 * 4096 / a.1;
    let mod_b = b.0 * 4096 / b.1;
    ((mod_a * mod_b + 2048) >> 12, 4096)
}






















pub fn apply_base_power_stage<const N: usize>(base_power: i64, modifiers: [Option<(i64, i64)>; N]) -> i64 {
    match modifiers.into_iter().flatten().reduce(chain_two) {
        Some((n, d)) => modify(base_power, n, d).max(1),
        None => base_power,
    }
}









pub fn apply_modify_damage_stage(
    damage: i64,
    screen_modifier: Option<(i64, i64)>,
    attacker_item: Option<(i64, i64)>,
    is_crit: bool,
    resist_berry: Option<(i64, i64)>,
    filter_modifier: Option<(i64, i64)>,
    ally_modifier: Option<(i64, i64)>,
) -> i64 {
    let screen = if is_crit { None } else { screen_modifier };
    let combined = [screen, attacker_item, resist_berry, filter_modifier, ally_modifier].into_iter().flatten().reduce(chain_two);
    match combined {
        Some((n, d)) => modify(damage, n, d),
        None => damage,
    }
}




#[derive(Clone, Copy, Debug)]
pub struct DamageInputs {
    pub level: u32,
    pub base_power: u32,
    pub attack: u32,
    pub defense: u32,
    pub is_spread: bool,
    pub is_crit: bool,

    pub crit_multiplier: (u8, u8),

    pub stab: (i64, i64),
    pub effectiveness: Effectiveness,
    pub attacker_burned: bool,
    pub is_physical: bool,


    pub weather_modifier: Option<(i64, i64)>,



    pub screen_modifier: Option<(i64, i64)>,


    pub attacker_item_modifier: Option<(i64, i64)>,






    pub resist_berry_modifier: Option<(i64, i64)>,






    pub filter_modifier: Option<(i64, i64)>,

    pub ally_modifier: Option<(i64, i64)>,


    pub crit_modifier: Option<(i64, i64)>,







    pub attack_other_crit: u32,

    pub defense_other_crit: u32,

    pub bypass_protect: bool,


    pub parental_bond_hit: Option<(i64, i64)>,

    pub min_damage_before_final: bool,
}





pub fn calculate(inputs: &DamageInputs, rng: &mut Rng) -> i64 {
    let result = calculate_inner(inputs, rng);
    if DEBUG_DAMAGE.load(core::sync::atomic::Ordering::Relaxed) {
        std::eprintln!("DMG {inputs:?} -> {result}");
    }
    result
}


pub static DEBUG_DAMAGE: core::sync::atomic::AtomicBool = core::sync::atomic::AtomicBool::new(false);


fn ally_and_crit_modifier(inputs: &DamageInputs) -> Option<(i64, i64)> {
    let crit = if inputs.is_crit { inputs.crit_modifier } else { None };
    [inputs.ally_modifier, crit].into_iter().flatten().reduce(chain_two)
}



fn final_modifiers(d: i64, inputs: &DamageInputs) -> i64 {
    let d = if inputs.min_damage_before_final { d.max(1) } else { d };
    let d = apply_modify_damage_stage(d, inputs.screen_modifier, inputs.attacker_item_modifier, inputs.is_crit, inputs.resist_berry_modifier, inputs.filter_modifier, ally_and_crit_modifier(inputs));
    if inputs.bypass_protect {
        modify(d, 1, 4)
    } else {
        d
    }
}

fn calculate_inner(inputs: &DamageInputs, rng: &mut Rng) -> i64 {
    let mut d = base_damage(inputs.level, inputs.base_power, inputs.attack, inputs.defense);
    d += 2;
    if inputs.is_spread {
        d = apply_spread_modifier(d);
    } else if let Some((n, den)) = inputs.parental_bond_hit {
        d = modify(d, n, den);
    }
    d = apply_weather_modifier(d, inputs.weather_modifier);
    if inputs.is_crit {
        d = apply_crit(d, inputs.crit_multiplier);
    }
    d = apply_random_roll_at(d, rng);
    d = apply_stab(d, inputs.stab);
    d = apply_effectiveness(d, inputs.effectiveness);
    d = apply_burn(d, inputs.attacker_burned, inputs.is_physical);
    d = final_modifiers(d, inputs);
    if inputs.effectiveness == Effectiveness::Immune {
        0
    } else if inputs.min_damage_before_final {
        d
    } else {
        d.max(1)
    }
}




pub fn possible_damages(inputs: &DamageInputs) -> [i64; 16] {
    let mut base = base_damage(inputs.level, inputs.base_power, inputs.attack, inputs.defense);
    base += 2;
    if inputs.is_spread {
        base = apply_spread_modifier(base);
    } else if let Some((n, den)) = inputs.parental_bond_hit {
        base = modify(base, n, den);
    }
    base = apply_weather_modifier(base, inputs.weather_modifier);
    if inputs.is_crit {
        base = apply_crit(base, inputs.crit_multiplier);
    }
    core::array::from_fn(|r| {
        let mut d = apply_random_roll_value(base, r as i64);
        d = apply_stab(d, inputs.stab);
        d = apply_effectiveness(d, inputs.effectiveness);
        d = apply_burn(d, inputs.attacker_burned, inputs.is_physical);
        d = final_modifiers(d, inputs);
        if inputs.effectiveness == Effectiveness::Immune {
            0
        } else if inputs.min_damage_before_final {
            d
        } else {
            d.max(1)
        }
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn base_damage_formula() {

        assert_eq!(base_damage(50, 80, 100, 100), 35);
    }

    #[test]
    fn spread_modifier_is_three_quarters() {
        assert_eq!(apply_spread_modifier(100), 75);
    }

    #[test]
    fn crit_is_one_point_five_no_rounding() {
        assert_eq!(apply_crit(101, (3, 2)), 151);
    }

    #[test]
    fn stab_ratios() {
        assert_eq!(apply_stab(100, (3, 2)), 150);
        assert_eq!(apply_stab(100, (1, 1)), 100);
        assert_eq!(apply_stab(100, (2, 1)), 200);
        assert_eq!(apply_stab(100, (9, 4)), 225);
        assert_eq!(apply_stab(100, (4915, 4096)), 120);
    }

    #[test]
    fn life_orb_alone_is_5324_over_4096() {

        assert_eq!(apply_modify_damage_stage(1000, None, Some(LIFE_ORB_MODIFIER), false, None, None, None), 1300);
    }

    #[test]
    fn screen_alone_is_2732_over_4096() {

        assert_eq!(apply_modify_damage_stage(1000, Some((2732, 4096)), None, false, None, None, None), 667);
    }

    #[test]
    fn screen_and_life_orb_chain_into_one_combined_modifier() {





        assert_eq!(apply_modify_damage_stage(1000, Some((2732, 4096)), Some(LIFE_ORB_MODIFIER), false, None, None, None), 867);
    }

    #[test]
    fn screen_is_bypassed_on_a_crit_but_life_orb_is_not() {
        assert_eq!(apply_modify_damage_stage(1000, Some((2732, 4096)), None, true, None, None, None), 1000, "screen skipped on crit");
        assert_eq!(apply_modify_damage_stage(1000, None, Some(LIFE_ORB_MODIFIER), true, None, None, None), 1300, "life orb still applies on crit");
    }

    #[test]
    fn resist_berry_halves_damage_and_is_not_bypassed_on_a_crit() {
        assert_eq!(apply_modify_damage_stage(1000, None, None, false, Some((1, 2)), None, None), 500);
        assert_eq!(apply_modify_damage_stage(1000, None, None, true, Some((1, 2)), None, None), 500, "unlike screens, a resist berry still applies on a crit");
    }

    #[test]
    fn filter_reduces_damage_by_a_quarter_and_is_not_bypassed_on_a_crit() {
        assert_eq!(apply_modify_damage_stage(1000, None, None, false, None, Some((3, 4)), None), 750);
        assert_eq!(apply_modify_damage_stage(1000, None, None, true, None, Some((3, 4)), None), 750, "unlike screens, Filter/Solid Rock still applies on a crit");
    }

    #[test]
    fn filter_chains_with_a_resist_berry_rather_than_overriding_it() {

        let combined = apply_modify_damage_stage(1000, None, None, false, Some((1, 2)), Some((3, 4)), None);
        assert_eq!(combined, 375);
    }

    #[test]
    fn effectiveness_super_and_resisted() {
        assert_eq!(apply_effectiveness(100, Effectiveness::Normal(1)), 200);
        assert_eq!(apply_effectiveness(100, Effectiveness::Normal(2)), 400);
        assert_eq!(apply_effectiveness(100, Effectiveness::Normal(-1)), 50);
        assert_eq!(apply_effectiveness(100, Effectiveness::Immune), 0);
    }

    #[test]
    fn water_vs_fire_is_super_effective() {
        let eff = type_effectiveness(&engine_data::type_chart::TYPE_CHART, Type::Water, [Some(Type::Fire), None]);
        assert_eq!(eff, Effectiveness::Normal(1));
    }

    #[test]
    fn electric_vs_ground_is_immune() {
        let eff = type_effectiveness(&engine_data::type_chart::TYPE_CHART, Type::Electric, [Some(Type::Ground), None]);
        assert_eq!(eff, Effectiveness::Immune);
    }

    #[test]
    fn dual_type_resist_stacks() {





        let eff = type_effectiveness(&engine_data::type_chart::TYPE_CHART, Type::Normal, [Some(Type::Rock), Some(Type::Steel)]);
        assert_eq!(eff, Effectiveness::Normal(-2));
        assert_eq!(apply_effectiveness(400, eff), 100);
    }

    #[test]
    fn random_roll_stays_in_85_to_100_percent() {
        let mut rng = Rng::new(123);
        for _ in 0..1000 {
            let d = apply_random_roll(1000, &mut rng);
            assert!((850..=1000).contains(&d), "{d} out of range");
        }
    }

    #[test]
    fn full_calculation_minimum_one_damage() {
        let mut rng = Rng::new(1);
        let inputs = DamageInputs {
            level: 50,
            base_power: 1,
            attack: 1,
            defense: 500,
            is_spread: false,
            is_crit: false,
            crit_multiplier: (3, 2),
            stab: (1, 1),
            effectiveness: Effectiveness::Normal(-2),
            attacker_burned: false,
            is_physical: true,
            weather_modifier: None,
            screen_modifier: None,
            resist_berry_modifier: None,
            filter_modifier: None,
            ally_modifier: None,
            crit_modifier: None,
            attacker_item_modifier: None,
            attack_other_crit: 0,
            defense_other_crit: 0,
            bypass_protect: false,
            parental_bond_hit: None,
            min_damage_before_final: false,
        };
        assert_eq!(calculate(&inputs, &mut rng), 1);
    }

    #[test]
    fn possible_damages_contains_every_actual_roll() {
        let inputs = DamageInputs {
            level: 50,
            base_power: 90,
            attack: 150,
            defense: 100,
            is_spread: true,
            is_crit: false,
            crit_multiplier: (3, 2),
            stab: (3, 2),
            effectiveness: Effectiveness::Normal(1),
            attacker_burned: false,
            is_physical: false,
            weather_modifier: None,
            screen_modifier: None,
            resist_berry_modifier: None,
            filter_modifier: None,
            ally_modifier: None,
            crit_modifier: None,
            attacker_item_modifier: None,
            attack_other_crit: 0,
            defense_other_crit: 0,
            bypass_protect: false,
            parental_bond_hit: None,
            min_damage_before_final: false,
        };
        let possible = possible_damages(&inputs);
        for seed in 0..100 {
            let mut rng = Rng::new(seed);
            let actual = calculate(&inputs, &mut rng);
            assert!(possible.contains(&actual), "seed {seed}: {actual} not in {possible:?}");
        }
    }

    #[test]
    fn immunity_overrides_everything() {
        let mut rng = Rng::new(1);
        let inputs = DamageInputs {
            level: 50,
            base_power: 150,
            attack: 300,
            defense: 50,
            is_spread: false,
            is_crit: true,
            crit_multiplier: (3, 2),
            stab: (3, 2),
            effectiveness: Effectiveness::Immune,
            attacker_burned: false,
            is_physical: true,
            weather_modifier: None,
            screen_modifier: None,
            resist_berry_modifier: None,
            filter_modifier: None,
            ally_modifier: None,
            crit_modifier: None,
            attacker_item_modifier: None,
            attack_other_crit: 0,
            defense_other_crit: 0,
            bypass_protect: false,
            parental_bond_hit: None,
            min_damage_before_final: false,
        };
        assert_eq!(calculate(&inputs, &mut rng), 0);
    }
}
