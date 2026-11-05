












use std::path::PathBuf;
use std::process::Command;

use crate::compare::compare_one_turn;
use crate::fixture_io::{run_oracle, Scenario};

fn generator_script_path() -> PathBuf {
    PathBuf::from(env!("CARGO_MANIFEST_DIR")).parent().expect("tools/diff has a parent dir").join("showdown-oracle").join("random-legal.js")
}

fn generate_scenarios(count: u32, seed: u32, out_dir: &std::path::Path) {
    let _ = std::fs::remove_dir_all(out_dir);
    let script = generator_script_path();
    let output = Command::new("node")
        .arg(&script)
        .args(["--count", &count.to_string(), "--seed", &seed.to_string(), "--out-dir"])
        .arg(out_dir)
        .output()
        .unwrap_or_else(|e| panic!("failed to spawn node on {}: {e}", script.display()));
    if !output.status.success() {
        eprintln!("generator stderr:\n{}", String::from_utf8_lossy(&output.stderr));
        panic!("random-legal.js exited with {}", output.status);
    }
}



pub fn run(count: u32, seed: u32) {
    let out_dir = std::env::temp_dir().join(format!("engine-core-random-legal-{seed}"));
    generate_scenarios(count, seed, &out_dir);
    crate::fixture_io::start_oracle_server();

    let mut passed = 0u32;
    let mut failed = 0u32;
    let mut failure_details: Vec<String> = Vec::new();

    for i in 0..count {
        let path = out_dir.join(format!("scenario-{i}.json"));
        let scenario = Scenario::load(&path);
        let oracle_result = run_oracle(&path);
        let report = compare_one_turn(&scenario, &oracle_result);
        if report.total_failures() == 0 {
            passed += 1;
        } else {
            failed += 1;
            failure_details.push(format!("--- scenario {i} ({}) ---\n{}", path.display(), report.messages.join("\n")));
        }
    }

    let pass_rate = passed as f64 / count as f64 * 100.0;
    println!("random-legal: {passed}/{count} passed ({pass_rate:.1}%), {failed} failed");
    if failed > 0 {
        println!("\nfirst {} failure(s):", failure_details.len().min(10));
        for detail in failure_details.iter().take(10) {
            println!("{detail}\n");
        }
    }
    println!(
        "\n=== {} (M2 accept criterion: \u{2265} 99% diff-clean) ===",
        if pass_rate >= 99.0 { "PASS" } else { "FAIL" }
    );
    if pass_rate < 99.0 {
        std::process::exit(1);
    }
}
