

#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub enum Action {
    Move {
        move_slot: u8,




        target_slot: u8,







        mega: bool,


        z: bool,
    },



    Switch { bench_slot: u8 },






    #[default]
    Pass,
}

impl Action {
    pub fn is_pass(self) -> bool {
        matches!(self, Action::Pass)
    }
}


pub type JointAction = [Action; 2];


#[derive(Clone, Copy, PartialEq, Eq, Debug, Default)]
pub struct Actor {
    pub side: u8,
    pub slot: u8,
}

impl Actor {
    pub fn other_side(self) -> u8 {
        1 - self.side
    }
}
