
use engine_fuzz::{random_battle, run_random_battle};

fn main() {
    let n = 5000;
    let total: u64 = (0..n)
        .map(|seed| {
            let mut battle = random_battle(seed);
            run_random_battle(&mut battle, 200) as u64
        })
        .sum();
    println!("average turns/battle over {n} seeds: {:.2}", total as f64 / n as f64);
}
