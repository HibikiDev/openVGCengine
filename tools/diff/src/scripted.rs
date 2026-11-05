






use std::path::Path;

use crate::compare::compare_one_turn;
use crate::fixture_io::{run_oracle, Scenario};

pub fn run(scenario_path: &str) {
    let path = Path::new(scenario_path);
    let scenario = Scenario::load(path);
    let oracle_result = run_oracle(path);

    let report = compare_one_turn(&scenario, &oracle_result);
    for msg in &report.messages {
        println!("{msg}");
    }
    println!("stat check: {} failures / 8 mons", report.stat_failures);
    println!(
        "\n=== {} ({} stat, {} damage-range, {} exact) ===",
        if report.total_failures() == 0 { "PASS" } else { "FAIL" },
        report.stat_failures, report.damage_failures, report.exact_failures
    );
    if report.total_failures() > 0 {
        std::process::exit(1);
    }
}
