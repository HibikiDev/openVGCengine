




use criterion::{criterion_group, criterion_main, BatchSize, Criterion};
use engine_fuzz::{random_battle, run_random_battle};

const MAX_TURNS: u32 = 200;

fn full_random_battle(c: &mut Criterion) {
    let mut seed = 0u64;
    c.bench_function("full_random_battle", |b| {
        b.iter_batched(
            || {
                seed += 1;
                random_battle(seed)
            },
            |mut battle| run_random_battle(&mut battle, MAX_TURNS),
            BatchSize::SmallInput,
        )
    });
}


fn battle_copy(c: &mut Criterion) {
    let battle = random_battle(1);
    c.bench_function("battle_copy", |b| b.iter(|| std::hint::black_box(*std::hint::black_box(&battle))));
}

criterion_group!(benches, full_random_battle, battle_copy);
criterion_main!(benches);
