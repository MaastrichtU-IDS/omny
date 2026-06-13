# Manchester `io/omn` Performance Report

## Headline

- `horned-omn` read is **11.3× faster than omny** (geomean over 4 ontologies).
- `horned-omn` read is **226.3× faster than OWL-API/ROBOT** (geomean over 4; ROBOT carries docker+JVM overhead — see caveats).
- `horned-omn` vs `fastobo-omn` (other Rust impl): geomean ratio 1.09× (>1 = fastobo slower; fastobo-omn excludes sio/hp which failed).

## hp — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-rdf | 5000.95 | 678.9 | 15.2 | 0.49× |
| owlapi | 10221.24 | 0.0 |  | 1.00× |

## koala — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-owx | 0.33 | 3.9 | 33.1 | 0.00× |
| horned-ofn | 0.64 | 4.8 | 7.9 | 0.00× |
| horned-rdf | 0.89 | 4.3 | 10.0 | 0.00× |
| horned-omn | 2.59 | 4.5 | 3.5 | 0.00× |
| fastobo-omn | 2.95 | 4.4 | 3.0 | 0.00× |
| omny | 21.80 | 42.3 | 0.4 | 0.01× |
| owlapi | 1541.27 | 0.0 |  | 1.00× |

## koala — write

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-ofn | 0.11 | 4.6 | 45.1 |  |
| horned-omn | 0.12 | 4.5 | 76.8 |  |
| horned-owx | 0.18 | 4.0 | 61.8 |  |
| omny | 26.27 | 48.8 |  |  |

## obi-core — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-owx | 186.29 | 46.7 | 74.7 | 0.06× |
| horned-rdf | 430.84 | 91.2 | 23.0 | 0.13× |
| horned-ofn | 623.08 | 151.9 | 9.2 | 0.19× |
| horned-omn | 801.74 | 114.7 | 5.4 | 0.25× |
| fastobo-omn | 848.53 | 117.6 | 5.1 | 0.26× |
| owlapi | 3209.41 | 0.0 |  | 1.00× |
| omny | 10996.86 | 412.3 | 0.4 | 3.43× |

## obi-core — write

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-ofn | 41.73 | 142.7 | 136.8 |  |
| horned-owx | 72.65 | 53.1 | 191.6 |  |
| horned-omn | 713.39 | 105.5 | 6.0 |  |
| omny | 15005.39 | 621.3 |  |  |

## pizza — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-owx | 0.21 | 1.2 | 41.2 | 0.00× |
| horned-omn | 0.49 | 4.5 | 1.8 | 0.00× |
| fastobo-omn | 0.51 | 4.4 | 1.8 | 0.00× |
| horned-ofn | 0.53 | 4.7 | 8.9 | 0.00× |
| omny | 8.38 | 42.0 | 0.1 | 0.01× |
| owlapi | 1526.97 | 0.0 |  | 1.00× |

## pizza — write

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-ofn | 0.02 | 3.8 | 219.6 |  |
| horned-omn | 0.04 | 4.3 | 21.9 |  |
| horned-owx | 0.06 | 4.3 | 140.2 |  |
| omny | 11.01 | 47.5 |  |  |

## sio — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-rdf | 63.59 | 21.3 | 23.3 | 0.03× |
| fastobo-omn | 112.90 | 27.0 | 6.7 | 0.05× |
| owlapi | 2110.75 | 0.0 |  | 1.00× |

## travel — read

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-owx | 0.58 | 3.9 | 38.3 | 0.00× |
| horned-ofn | 1.36 | 5.0 | 8.1 | 0.00× |
| horned-rdf | 1.70 | 4.6 | 10.1 | 0.00× |
| horned-omn | 4.42 | 5.0 | 3.5 | 0.00× |
| fastobo-omn | 4.92 | 4.7 | 3.2 | 0.00× |
| omny | 36.20 | 42.9 | 0.4 | 0.02× |
| owlapi | 1547.95 | 0.0 |  | 1.00× |

## travel — write

| backend | median (ms) | peak RSS (MB) | throughput (MB/s) | ratio vs owlapi |
|---|---|---|---|---|
| horned-ofn | 0.09 | 4.8 | 129.0 |  |
| horned-omn | 0.14 | 4.5 | 109.0 |  |
| horned-owx | 0.23 | 3.9 | 97.2 |  |
| omny | 48.67 | 49.9 |  |  |

## Conformance failures (excluded from timing)

| ontology | mode | backend | error |
|---|---|---|---|
| sio | read | horned-omn | CalledProcessError: Command '['/data/dumontier/pymos/bench/horned-bench/target/release/horned-bench', '--format', 'omn', |
| hp | read | horned-omn | CalledProcessError: Command '['/data/dumontier/pymos/bench/horned-bench/target/release/horned-bench', '--format', 'omn', |
| hp | read | fastobo-omn | CalledProcessError: Command '['/data/dumontier/pymos/bench/horned-bench/target/release/horned-bench', '--format', 'fasto |

## Caveats

- Rust timings are in-process hot medians (cold-start ~2 ms excluded).
- OWL-API via ROBOT docker: hot median carries per-call docker overhead (~1.5 s startup in cold).
- omny is pure-Python; fastobo-omn (horned-owl 0.14) is read-only (no serializer).
- Component counts differ across formats (declaration handling); this measures per-format parse/serialize SPEED, not identical-axiom-set parsing.

