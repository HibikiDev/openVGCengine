




#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Weather {
    #[default]
    None = 0,
    Sun = 1,
    Rain = 2,
    Sand = 3,
    Snow = 4,


    Hail = 5,






    DesolateLand = 6,
    PrimordialSea = 7,
    DeltaStream = 8,
}

impl Weather {

    pub fn reader(self) -> Weather {
        match self {
            Weather::DesolateLand => Weather::Sun,
            Weather::PrimordialSea => Weather::Rain,
            Weather::DeltaStream => Weather::None,
            w => w,
        }
    }

    pub fn is_strong(self) -> bool {
        matches!(self, Weather::DesolateLand | Weather::PrimordialSea | Weather::DeltaStream)
    }
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
#[repr(u8)]
pub enum Terrain {
    #[default]
    None = 0,
    Electric = 1,
    Grassy = 2,
    Misty = 3,
    Psychic = 4,
}

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Field {
    pub weather: Weather,

    pub weather_turns: u8,

    pub weather_source: u8,
    pub terrain: Terrain,
    pub terrain_turns: u8,

    pub trick_room_turns: u8,

    pub gravity_turns: u8,

    pub fairy_lock_turns: u8,

    pub magic_room_turns: u8,

    pub wonder_room_turns: u8,


    pub echoed_voice_turns: u8,
    pub echoed_voice_mult: u8,

    pub mud_sport_turns: u8,
    pub water_sport_turns: u8,




    pub sports_called: u8,


    pub ion_deluge: bool,



    pub last_move: u16,

    pub last_move_z: bool,


    pub last_success_move: u16,


    pub pending_z: u16,


    pub pending_max: u16,



    pub faint_switches_held: bool,


    pub hazard_seq: u16,


    pub prior_hits_damage: u16,
}
