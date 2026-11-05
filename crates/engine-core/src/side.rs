





use crate::mon::Mon;




#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct SideConds {

    pub reflect_turns: u8,
    pub light_screen_turns: u8,
    pub aurora_veil_turns: u8,
    pub tailwind_turns: u8,


    pub safeguard_turns: u8,
    pub stealth_rock: bool,

    pub spikes: u8,

    pub toxic_spikes: u8,
    pub sticky_web: bool,



    pub wide_guard: bool,



    pub quick_guard: bool,


    pub crafty_shield: bool,


    pub mat_block: bool,


    pub healing_wish: [bool; 2],


    pub heal_replacement: [bool; 2],


    pub wish_turns: [u8; 2],
    pub wish_hp: [u16; 2],

    pub mist_turns: u8,

    pub lucky_chant_turns: u8,



    pub sea_of_fire_turns: u8,
    pub swamp_turns: u8,
    pub rainbow_turns: u8,


    pub fainted_last_turn: bool,
    pub fainted_count: u8,

    pub lunar_dance: [bool; 2],




    pub future_turns: [u8; 2],
    pub future_source: [u8; 2],
    pub future_move: [u16; 2],



    pub gmax_residual_turns: [u8; 4],

    pub steelsurge: bool,



    pub hazard_order: [u16; 5],
}


pub const HAZARD_ROCKS: usize = 0;
pub const HAZARD_STEELSURGE: usize = 1;
pub const HAZARD_SPIKES: usize = 2;
pub const HAZARD_WEB: usize = 3;
pub const HAZARD_TOXIC_SPIKES: usize = 4;


pub const FUTURE_NEVER: u8 = 255;

pub const NO_PHANTOM: u8 = 4;

#[derive(Clone, Copy, Debug)]
pub struct Side {
    pub mons: [Mon; 4],



    pub active: [u8; 3],
    pub side_conditions: SideConds,


    pub mega_used: bool,


    pub z_used: bool,


    pub ultra_used: bool,

    pub tera_used: bool,

    pub dynamax_used: bool,


    pub order: [u8; 4],


    pub revivals: u8,
}

impl Side {


    pub fn forme_change_used(&self, ultra: bool) -> bool {
        if ultra { self.ultra_used } else { self.mega_used }
    }


    pub fn total_fainted(&self) -> u8 {
        self.mons.iter().filter(|m| m.is_fainted()).count() as u8 + self.revivals
    }

    pub fn active_mon(&self, slot: usize) -> &Mon {
        &self.mons[self.active[slot] as usize]
    }

    pub fn active_mon_mut(&mut self, slot: usize) -> &mut Mon {
        &mut self.mons[self.active[slot] as usize]
    }
}
