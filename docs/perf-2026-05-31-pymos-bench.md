# Perf snapshot — 2026-05-31, pymos

Host: fsesrv-g1, Linux-5.15.0-97-generic-x86_64-with-glibc2.35, python 3.10.12.
pymos: dbd8ffdd19d4.  CPU count: 32.

## Headline

_TODO: hand-write a one-paragraph summary after reading the tables._

## 1. Parse

| ontology | axioms | bytes | cold (s) | hot median (s) | peak RSS (MB) |
|---|---:|---:|---:|---:|---:|
| pizza | 10 | 897 | 0.034 | 0.079 | 37 |
| koala | 33 | 8952 | 0.089 | 0.089 | 38 |
| travel | 57 | 15634 | 0.133 | 0.140 | 38 |

## 2. Render

| ontology | bytes emitted | cold (s) | hot median (s) | idempotent? |
|---|---:|---:|---:|:---:|
| pizza | 1427 | 0.221 | 0.042 | yes |
| koala | 7964 | 0.283 | 0.168 | yes |
| travel | 13656 | 0.383 | 0.192 | yes |

## 3. Query — summary (median hot across relations × targets)

| ontology | backend | reasoner | median hot (s) | cells |
|---|---|---|---:|---:|
| koala | owlready2_mem | none | 0.146 | 18 |
| koala | owlready2_mem | owlrl | 0.151 | 18 |
| koala | pyoxigraph_mem | none | 0.104 | 36 |
| koala | pyoxigraph_mem | owlrl | 0.090 | 36 |
| pizza | owlready2_mem | none | 0.092 | 18 |
| pizza | owlready2_mem | owlrl | 0.088 | 18 |
| pizza | pyoxigraph_mem | none | 0.039 | 36 |
| pizza | pyoxigraph_mem | owlrl | 0.035 | 36 |
| travel | owlready2_mem | none | 0.230 | 18 |
| travel | owlready2_mem | owlrl | 0.224 | 18 |
| travel | pyoxigraph_mem | none | 0.165 | 36 |
| travel | pyoxigraph_mem | owlrl | 0.161 | 36 |

## 4. Wrapper startup floors

| wrapper | floor (s) |
|---|---:|
| owlrl | 0.34 |

## 5. Coverage

- Total cells: 438
- Skipped (structurally n/a): 108
- Errored: 0
