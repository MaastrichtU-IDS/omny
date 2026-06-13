//! Manchester / OWL I/O micro-benchmark. Reads or renders an ontology N times
//! in-process and reports timing + peak RSS as one JSON line.
fn main() {
    // Reference the path-fork (1.4): a type from our crate.
    let _b = horned_owl::model::Build::<std::rc::Rc<str>>::new();
    // Reference fastobo (horned-owl 0.14) so the dual-version link is exercised.
    let _: Result<
        (
            horned_owl_014::ontology::set::SetOntology<std::rc::Rc<str>>,
            _,
        ),
        _,
    > = horned_manchester::from_str::<std::rc::Rc<str>, _, _>("");
    eprintln!("smoke ok");
}
