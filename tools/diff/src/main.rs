










mod compare;
mod fixture_io;
mod fixtures;
mod random_legal;
mod replay;
mod scripted;

use std::path::PathBuf;
use std::process::Command;

fn parse_arg(args: &[String], flag: &str, default: &str) -> String {
    args.iter()
        .position(|a| a == flag)
        .and_then(|i| args.get(i + 1))
        .cloned()
        .unwrap_or_else(|| default.to_string())
}

fn oracle_script_path() -> PathBuf {

    PathBuf::from(env!("CARGO_MANIFEST_DIR"))
        .parent()
        .expect("tools/diff has a parent dir")
        .join("showdown-oracle")
        .join("oracle.js")
}

fn run_oracle(seed: &str, format: &str, max_turns: &str) -> serde_json::Value {
    let script = oracle_script_path();
    let output = Command::new("node")
        .arg(&script)
        .args(["--seed", seed, "--format", format, "--max-turns", max_turns])
        .output()
        .unwrap_or_else(|e| panic!("failed to spawn node on {}: {e}", script.display()));

    if !output.status.success() {
        eprintln!("oracle stderr:\n{}", String::from_utf8_lossy(&output.stderr));
        panic!("oracle exited with {}", output.status);
    }

    serde_json::from_slice(&output.stdout).expect("oracle printed valid JSON")
}

fn run_random_summary() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    let seed = parse_arg(&args, "--seed", "1");
    let format = parse_arg(&args, "--format", "gen9championsvgc2026regmc");
    let max_turns = parse_arg(&args, "--max-turns", "100");

    let oracle_result = run_oracle(&seed, &format, &max_turns);
    let turn_count = oracle_result["turnCount"].as_u64().unwrap_or(0);
    let last_turn = oracle_result["turns"].as_array().and_then(|t| t.last());

    println!("oracle: seed={seed} format={format} turns={turn_count}");
    if let Some(last) = last_turn {
        println!(
            "  final turn={} ended={} winner={}",
            last["turn"],
            last["ended"],
            last["winner"].as_str().unwrap_or("<ongoing>"),
        );
    }
    println!(
        "\n(random-legal oracle summary only - use `diff scripted <fixture.json>` to actually \
         compare against engine-core on a hand-authored scenario.)"
    );
}

fn main() {
    let args: Vec<String> = std::env::args().skip(1).collect();
    match args.first().map(String::as_str) {
        Some("scripted") => {
            let fixture = args.get(1).expect("usage: diff scripted <fixture.json>");
            scripted::run(fixture);
        }
        Some("replay") => {
            let fixture = args.get(1).expect("usage: diff replay <fixture.json>");
            if !replay::run(fixture, None) {
                std::process::exit(1);
            }
        }


        Some("replay-many") => {
            fixture_io::start_oracle_server();
            let mut failed = 0;
            for fixture in &args[1..] {
                let ok = std::panic::catch_unwind(|| replay::run(fixture, None)).unwrap_or(false);
                failed += usize::from(!ok);
                println!("RESULT {} {fixture}", if ok { "PASS" } else { "FAIL" });
            }
            if failed > 0 {
                std::process::exit(1);
            }
        }


        Some("obs") => {
            let fixture = args.get(1).expect("usage: diff obs <fixture.json> <out.json>");
            let out = args.get(2).expect("usage: diff obs <fixture.json> <out.json>");
            if !replay::run(fixture, Some(out)) {
                std::process::exit(1);
            }
        }
        Some("random-legal") => {
            let count: u32 = parse_arg(&args, "--count", "200").parse().expect("--count must be a number");
            let seed: u32 = parse_arg(&args, "--seed", "1").parse().expect("--seed must be a number");
            random_legal::run(count, seed);
        }
        _ => run_random_summary(),
    }
}
