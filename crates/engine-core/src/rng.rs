




































#[derive(Clone, Copy, Debug)]
pub enum Rng {
    Generate(u64),
    Replay(&'static [ReplayDraw], usize),
}
















#[derive(Clone, Copy, Debug, PartialEq)]
pub struct ReplayDraw {
    pub from: Option<u32>,
    pub to: Option<u32>,
    pub result: f64,
    pub bookkeeping: bool,
}


pub static TRACE_DRAWS: core::sync::atomic::AtomicBool = core::sync::atomic::AtomicBool::new(false);



#[derive(Clone, Copy, Debug, PartialEq, Eq)]
#[repr(u8)]
pub enum Site {
    Accuracy = 1,
    Crit = 2,
    DamageRoll = 3,
    Secondary = 4,
    Flinch = 5,
    Confusion = 6,



    FullParalysis = 7,

    ConfusionSelfHit = 8,

    SleepTurns = 9,

    Thaw = 10,

    QuickClaw = 11,
}



pub static SCRIPT: core::sync::atomic::AtomicBool = core::sync::atomic::AtomicBool::new(false);




pub mod script {
    use super::Site;
    use std::cell::RefCell;




    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub struct Draw {
        pub site: Site,
        pub actor: u8,
        pub move_id: u16,
        pub target: u8,
        pub k: u8,
        pub bound: u32,
        pub numerator: Option<u32>,
        pub rolled: u32,
        pub result: u32,
        pub forced: bool,
    }


    #[derive(Clone, Copy, Debug, PartialEq, Eq)]
    pub struct Override {
        pub site: Site,
        pub actor: u8,
        pub move_id: u16,
        pub target: u8,
        pub k: u8,
        pub value: u32,
    }

    #[derive(Default)]
    struct State {
        active: bool,
        ctx: (u8, u16, u8),
        draws: Vec<Draw>,
        overrides: Vec<(Override, bool)>,
    }

    std::thread_local! {
        static STATE: RefCell<State> = RefCell::new(State::default());
    }


    pub fn begin(overrides: &[Override]) {
        STATE.with(|s| {
            let mut s = s.borrow_mut();
            *s = State { active: true, ctx: (0xFF, 0, 0xFF), draws: Vec::new(), overrides: overrides.iter().map(|&o| (o, false)).collect() };
        });
        super::SCRIPT.store(true, core::sync::atomic::Ordering::Relaxed);
    }



    pub fn end() -> (Vec<Draw>, Vec<Override>) {
        super::SCRIPT.store(false, core::sync::atomic::Ordering::Relaxed);
        STATE.with(|s| {
            let s = std::mem::take(&mut *s.borrow_mut());
            (s.draws, s.overrides.into_iter().filter(|(_, used)| !used).map(|(o, _)| o).collect())
        })
    }


    #[inline(always)]
    pub fn context(actor: crate::action::Actor, move_id: u16, target: crate::action::Actor) {
        if super::SCRIPT.load(core::sync::atomic::Ordering::Relaxed) {
            set_context(actor, move_id, target);
        }
    }


    #[cold]
    #[inline(never)]
    fn set_context(actor: crate::action::Actor, move_id: u16, target: crate::action::Actor) {
        STATE.with(|s| {
            let mut s = s.borrow_mut();
            if s.active {
                s.ctx = (actor.side * 2 + actor.slot, move_id, target.side * 2 + target.slot);
            }
        });
    }


    #[cold]
    #[inline(never)]
    pub(super) fn draw(site: Site, bound: u32, numerator: Option<u32>, rolled: u32) -> u32 {
        STATE.with(|s| {
            let mut s = s.borrow_mut();
            if !s.active {
                return rolled;
            }
            let (actor, move_id, target) = s.ctx;
            let k = s.draws.iter().filter(|d| d.site == site && d.actor == actor && d.move_id == move_id && d.target == target).count() as u8;
            let mut result = rolled;
            let mut forced = false;
            for (o, used) in s.overrides.iter_mut() {
                if o.site == site && o.actor == actor && o.move_id == move_id && o.target == target && o.k == k && o.value < bound {
                    result = o.value;
                    forced = true;
                    *used = true;
                }
            }
            s.draws.push(Draw { site, actor, move_id, target, k, bound, numerator, rolled, result, forced });
            result
        })
    }
}

impl Rng {
    pub fn new(seed: u64) -> Rng {
        Rng::Generate(seed)
    }




    pub fn new_replay(trace: &'static [ReplayDraw]) -> Rng {
        Rng::Replay(trace, 0)
    }



    pub fn unconsumed_real_draws(&self) -> Option<usize> {
        match self {
            Rng::Replay(trace, cursor) => Some(trace[(*cursor).min(trace.len())..].iter().filter(|d| !d.bookkeeping).count()),
            _ => None,
        }
    }







    fn next_replay_draw(trace: &[ReplayDraw], cursor: &mut usize) -> ReplayDraw {
        loop {
            let draw = trace.get(*cursor).copied().unwrap_or_else(|| {
                panic!("RNG replay desync: trace exhausted at index {cursor} (engine-core asked for another draw, oracle recorded none)")
            });
            *cursor += 1;
            if !draw.bookkeeping {
                return draw;
            }
        }
    }








    pub fn next_u64(&mut self) -> u64 {
        match self {
            Rng::Generate(state) => {
                *state = state.wrapping_add(0x9E3779B97F4A7C15);
                let mut z = *state;
                z = (z ^ (z >> 30)).wrapping_mul(0xBF58476D1CE4E5B9);
                z = (z ^ (z >> 27)).wrapping_mul(0x94D049BB133111EB);
                z ^ (z >> 31)
            }
            Rng::Replay(..) => panic!("Rng::next_u64 has no replay-mode equivalent - every real draw site should go through random/random_range/chance instead"),
        }
    }

    pub fn next_u32(&mut self) -> u32 {
        (self.next_u64() >> 32) as u32
    }










    pub fn random(&mut self, bound: u32) -> u32 {
        debug_assert!(bound > 0, "Rng::random bound must be positive");
        let r = self.random_inner(bound);
        if TRACE_DRAWS.load(core::sync::atomic::Ordering::Relaxed) {
            let idx = if let Rng::Replay(_, c) = self { *c as i64 - 1 } else { -1 };
            std::eprintln!("DRAW {idx} random({bound})={r}");
        }
        r
    }

    fn random_inner(&mut self, bound: u32) -> u32 {
        match self {
            Rng::Generate(_) => ((self.next_u32() as u64 * bound as u64) >> 32) as u32,
            Rng::Replay(trace, cursor) => {
                let draw = Self::next_replay_draw(trace, cursor);
                if draw.from != Some(bound) || draw.to.is_some() {
                    panic!("RNG replay desync at draw index {}: engine-core asked for random({bound}), oracle recorded {draw:?}", *cursor - 1);
                }
                draw.result as u32
            }
        }
    }





    pub fn random_range(&mut self, lo: u32, hi: u32) -> u32 {
        debug_assert!(hi > lo, "Rng::random_range requires hi > lo");
        let r = self.random_range_inner(lo, hi);
        if TRACE_DRAWS.load(core::sync::atomic::Ordering::Relaxed) {
            let idx = if let Rng::Replay(_, c) = self { *c as i64 - 1 } else { -1 };
            std::eprintln!("DRAW {idx} random_range({lo}, {hi})={r}");
        }
        r
    }

    fn random_range_inner(&mut self, lo: u32, hi: u32) -> u32 {
        match self {
            Rng::Generate(_) => lo + self.random(hi - lo),
            Rng::Replay(trace, cursor) => {
                let draw = Self::next_replay_draw(trace, cursor);
                if draw.from != Some(lo) || draw.to != Some(hi) {
                    panic!("RNG replay desync at draw index {}: engine-core asked for random_range({lo}, {hi}), oracle recorded {draw:?}", *cursor - 1);
                }
                draw.result as u32
            }
        }
    }





    pub fn chance(&mut self, numerator: u32, denominator: u32) -> bool {
        self.random(denominator) < numerator
    }




    #[inline(always)]
    pub fn random_at(&mut self, site: Site, bound: u32) -> u32 {
        let r = self.random(bound);
        if SCRIPT.load(core::sync::atomic::Ordering::Relaxed) {
            return self.scripted(site, bound, None, r);
        }
        r
    }


    #[cold]
    #[inline(never)]
    fn scripted(&self, site: Site, bound: u32, numerator: Option<u32>, rolled: u32) -> u32 {
        assert!(!matches!(self, Rng::Replay(..)), "a scripted step can't run on a replayed RNG");
        script::draw(site, bound, numerator, rolled)
    }


    #[inline(always)]
    pub fn chance_at(&mut self, site: Site, numerator: u32, denominator: u32) -> bool {
        let r = self.random(denominator);
        if SCRIPT.load(core::sync::atomic::Ordering::Relaxed) {
            return self.scripted(site, denominator, Some(numerator), r) < numerator;
        }
        r < numerator
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn same_seed_same_sequence() {
        let mut a = Rng::new(42);
        let mut b = Rng::new(42);
        for _ in 0..100 {
            assert_eq!(a.next_u64(), b.next_u64());
        }
    }

    #[test]
    fn different_seeds_diverge() {
        let mut a = Rng::new(1);
        let mut b = Rng::new(2);
        assert_ne!(a.next_u64(), b.next_u64());
    }

    #[test]
    fn random_stays_in_bounds() {
        let mut rng = Rng::new(7);
        for _ in 0..10_000 {
            let n = rng.random(16);
            assert!(n < 16);
        }
    }





    #[test]
    fn rng_is_still_copy() {
        fn assert_copy<T: Copy>() {}
        assert_copy::<Rng>();
    }

    #[test]
    fn replay_consumes_recorded_draws_in_order() {
        let trace: &'static [ReplayDraw] = Box::leak(Box::new([
            ReplayDraw { from: Some(100), to: None, result: 42.0, bookkeeping: false },
            ReplayDraw { from: Some(2), to: None, result: 1.0, bookkeeping: false },
        ]));
        let mut rng = Rng::new_replay(trace);
        assert_eq!(rng.random(100), 42);
        assert!(!rng.chance(1, 2), "result 1 is not < numerator 1, so chance(1, 2) should be false");
    }

    #[test]
    fn replay_silently_skips_bookkeeping_entries() {




        let trace: &'static [ReplayDraw] = Box::leak(Box::new([
            ReplayDraw { from: Some(2), to: None, result: 0.0, bookkeeping: true },
            ReplayDraw { from: Some(2), to: None, result: 1.0, bookkeeping: true },
            ReplayDraw { from: Some(100), to: None, result: 42.0, bookkeeping: false },
        ]));
        let mut rng = Rng::new_replay(trace);
        assert_eq!(rng.random(100), 42, "the two bookkeeping entries ahead of it should be skipped, not matched");
    }

    #[test]
    #[should_panic(expected = "RNG replay desync")]
    fn replay_panics_on_a_shape_mismatch() {
        let trace: &'static [ReplayDraw] = Box::leak(Box::new([ReplayDraw { from: Some(100), to: None, result: 42.0, bookkeeping: false }]));
        let mut rng = Rng::new_replay(trace);
        rng.random(24);
    }

    #[test]
    #[should_panic(expected = "RNG replay desync: trace exhausted")]
    fn replay_panics_on_exhaustion() {
        let trace: &'static [ReplayDraw] = &[];
        let mut rng = Rng::new_replay(trace);
        rng.random(2);
    }

    #[test]
    fn replay_supports_random_range_for_speed_tie_shuffles() {
        let trace: &'static [ReplayDraw] = Box::leak(Box::new([ReplayDraw { from: Some(0), to: Some(4), result: 3.0, bookkeeping: false }]));
        let mut rng = Rng::new_replay(trace);
        assert_eq!(rng.random_range(0, 4), 3);
    }
}
