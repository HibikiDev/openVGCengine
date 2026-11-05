


use crate::action::{Action, Actor};
use crate::event::EventRing;
use crate::field::Field;
use crate::pending::Pending;
use crate::rng::Rng;
use crate::side::Side;



#[derive(Clone, Copy, Debug)]
pub struct TurnResume {

    pub entries: [QueueEntry; QUEUE_CAP],
    pub len: u8,
    pub next: u8,
}


pub type QueueEntry = (Actor, Action, i8, i64);


pub const QUEUE_CAP: usize = 8;

pub const QUEUE_PAD: QueueEntry = (Actor { side: 0, slot: 0 }, Action::Pass, 0, 0);

#[derive(Clone, Copy, Debug)]
pub struct Battle {
    pub sides: [Side; 2],
    pub field: Field,
    pub turn: u16,
    pub rng: Rng,
    pub pending: Pending,
    pub history: EventRing,

    pub resume: Option<TurnResume>,

    pub end_turn_pending: bool,


    pub started: bool,



    pub opportunist: [[i8; 7]; 4],




    pub opportunist_bank: u8,

    pub format: crate::rules::Format,



    pub speed_order: [u8; 4],


    pub ability_seq: u16,


    pub dance_move: u16,


    pub active_target: u8,
}

impl Battle {

    #[inline]
    pub fn rules(&self) -> &'static crate::rules::Rules {
        crate::rules::Rules::of(self.format)
    }


    #[inline]
    pub fn species_data(&self, id: engine_data::species_table::SpeciesId) -> &'static engine_data::species_table::SpeciesData {
        self.rules().species_data(id)
    }


    #[inline]
    pub fn move_data(&self, id: engine_data::moves_table::MoveId) -> &'static engine_data::moves_table::MoveData {
        &self.rules().moves[(id - 1) as usize]
    }




    pub fn weather(&self) -> crate::field::Weather {
        let suppressed = self.weather_suppressed();
        if suppressed { crate::field::Weather::None } else { self.field.weather.reader() }
    }



    pub fn strong_weather(&self) -> crate::field::Weather {
        let w = self.field.weather;
        if w.is_strong() && !self.weather_suppressed() { w } else { crate::field::Weather::None }
    }


    pub fn weather_suppressed(&self) -> bool {
        self.sides.iter().any(|s| {
            s.active[..2].iter().any(|&i| {
                let m = &s.mons[i as usize];
                !(m.is_fainted() && m.flags.has(crate::mon::mon_flags::FAINT_MESSAGED))
                    && matches!(m.ability, engine_data::abilities_table::ability_ids::CLOUDNINE | engine_data::abilities_table::ability_ids::AIRLOCK)
            })
        })
    }


    pub fn effective_field(&self) -> Field {
        Field { weather: self.weather(), ..self.field }
    }
}




const BATTLE_SIZE_BUDGET: usize = 3072;

const _: () = assert!(
    std::mem::size_of::<Battle>() <= BATTLE_SIZE_BUDGET,
    "Battle grew past its size budget (design.md §5.2) - update BATTLE_SIZE_BUDGET intentionally, \
     or shrink the struct back"
);

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn battle_is_copy_and_clone_is_equal_bytes() {
        fn assert_copy<T: Copy>() {}
        assert_copy::<Battle>();
    }

    #[test]
    fn report_actual_size() {


        println!("size_of::<Battle>() = {}, size_of::<Mon>() = {}", std::mem::size_of::<Battle>(), std::mem::size_of::<crate::mon::Mon>());
    }
}
