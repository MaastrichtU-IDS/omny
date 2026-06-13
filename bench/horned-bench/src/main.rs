//! Manchester / OWL I/O micro-benchmark. One JSON line on stdout:
//! {"format":..,"mode":..,"wall_hot_median_s":..,"wall_hot_min_s":..,
//!  "wall_cold_s":..,"peak_rss_bytes":..,"component_count":..,"bytes":..}
use std::io::BufReader;
use std::rc::Rc;
use std::time::Instant;

use horned_owl::io::ParserConfiguration;
use horned_owl::model::AnnotatedComponent;
use horned_owl::ontology::component_mapped::ComponentMappedOntology;
use horned_owl::ontology::set::SetOntology;

type Set = SetOntology<Rc<str>>;
type Amo = ComponentMappedOntology<Rc<str>, Rc<AnnotatedComponent<Rc<str>>>>;

fn arg(flag: &str, default: &str) -> String {
    let a: Vec<String> = std::env::args().collect();
    a.iter().position(|x| x == flag).and_then(|i| a.get(i + 1)).cloned()
        .unwrap_or_else(|| default.into())
}
fn input_path() -> String { std::env::args().last().expect("input path") }

fn peak_rss_bytes() -> u64 {
    std::fs::read_to_string("/proc/self/status").ok()
        .and_then(|s| s.lines().find(|l| l.starts_with("VmHWM"))
            .and_then(|l| l.split_whitespace().nth(1)).and_then(|n| n.parse::<u64>().ok()))
        .map(|kb| kb * 1024).unwrap_or(0)
}

/// Run `f` cold once, warmup M, then N hot; return (cold_s, min_s, median_s).
fn time_it(warmup: usize, hot: usize, mut f: impl FnMut()) -> (f64, f64, f64) {
    let t = Instant::now(); f(); let cold = t.elapsed().as_secs_f64();
    for _ in 0..warmup { f(); }
    let mut samples: Vec<f64> = (0..hot)
        .map(|_| { let t = Instant::now(); f(); t.elapsed().as_secs_f64() }).collect();
    samples.sort_by(|a, b| a.partial_cmp(b).unwrap());
    let min = *samples.first().unwrap_or(&cold);
    let median = samples.get(samples.len() / 2).copied().unwrap_or(cold);
    (cold, min, median)
}

fn main() {
    let format = arg("--format", "omn");
    let mode = arg("--mode", "parse");
    let warmup: usize = arg("--warmup", "1").parse().unwrap();
    let hot: usize = arg("--hot", "5").parse().unwrap();
    let path = input_path();
    let text = std::fs::read_to_string(&path).expect("read input");
    let bytes = text.len();

    let mut component_count = 0usize;
    let (cold, min, median) = match (format.as_str(), mode.as_str()) {
        ("omn", "parse") => time_it(warmup, hot, || {
            let (o, _): (Set, _) = horned_owl::io::omn::read(
                BufReader::new(text.as_bytes()), ParserConfiguration::default()).expect("omn parse");
            component_count = o.iter().count();
        }),
        ("omn", "render") => {
            let (o, pm): (Set, _) = horned_owl::io::omn::read(
                BufReader::new(text.as_bytes()), ParserConfiguration::default()).expect("omn parse");
            component_count = o.iter().count();
            let amo: Amo = o.into();
            time_it(warmup, hot, || {
                let _ = horned_owl::io::omn::write(Vec::<u8>::new(), &amo, Some(&pm)).expect("omn write");
            })
        }
        other => panic!("unsupported (format,mode) = {other:?} (added in later tasks)"),
    };

    println!("{{\"format\":\"{format}\",\"mode\":\"{mode}\",\
        \"wall_hot_median_s\":{median},\"wall_hot_min_s\":{min},\"wall_cold_s\":{cold},\
        \"peak_rss_bytes\":{},\"component_count\":{component_count},\"bytes\":{bytes}}}",
        peak_rss_bytes());
}
