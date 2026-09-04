# mlir-symbol-verification-bench

A reproducible benchmark for MLIR symbol-table verification cost
(llvm/llvm-project#212354). It measures how long `mlir-opt` spends re-verifying
symbol uses across a repeated pass pipeline, on shapes that each isolate one
real cost driver, and compares design points (with/without the
`SymbolUserTypeInterface`, and different placements of a containment cache).

## Quickstart (three commands)

    ./generate.sh                     # write the benchmark shapes (deterministic, ~seconds, no mlir-opt)
    ./bench.sh /path/to/mlir-opt      # measure one mlir-opt build; prints its numbers, appends to results.tsv
    ./report.sh                       # print the comparison across everything measured so far

Run `./bench.sh` once per design point you want to compare (see
`DESIGN_POINTS.md` for what to build and label each). To measure a subset of
shapes, set `SHAPES_ONLY="wide-struct-reuse" ./bench.sh ...`. Example:

    ./bench.sh ~/llvm/build-A/bin/mlir-opt context-cache
    ./bench.sh ~/llvm/build-B/bin/mlir-opt pre-interface
    ./report.sh

## What is measured

Two metrics, both lower-is-better, reported per shape:

- **WALL** -- end-to-end `mlir-opt` wall clock on an `N`-times-repeated
  `canonicalize` pipeline (each pass re-runs full verification), threading
  disabled, as the **median of 7 iterations** with the min..max spread and peak
  RSS. This is what ships.
- **Ir/pass** -- retired instructions per verification pass, counted
  deterministically with callgrind at two pass counts `N_lo`/`N_hi`:
  `(Ir(N_hi) - Ir(N_lo)) / (N_hi - N_lo)`. This isolates the steady state (after
  the first pass warms any cache) and is scheduling-independent.

`report.sh` shows each shape's design points relative to the `upstream-main`
baseline (1.00x). When a `pre-interface` column is present it adds the reviewer's
line: `pre-interface -> upstream-main (regression factor) -> context-cache`, with
the recovery fraction `(main - design) / (main - pre-interface)`.

These are synthetic microbenchmarks measured on one machine: the absolute numbers
are machine-specific; the cross-design ratios are the story.

## Requirements

- `python3`, `valgrind` (for Ir/pass), `/usr/bin/time` (GNU time, for wall/RSS).
- One or more `mlir-opt` builds to point `bench.sh` at (`DESIGN_POINTS.md`).

## Shapes

See `shapes.txt`; each row pins a generator (in `gen/`) and its parameters, the
pass counts, and the phenomenon it isolates -- wide signatures, CIRCT-scale,
nested symbol-table scopes, properties-dense ops, and a distinct-per-op-dictionary
regression repro. That last shape (`shapes/published_repro.mlir`) is a
4000-function distinct-per-op-dictionary input modeled on the PR's 8000-function
reproducer -- half scale to keep the checkout small; it reproduces the same cost
driver, not the PR's absolute published timings. `./generate.sh` reproduces the
generated shapes byte-for-byte and checks each against the pinned
`shapes/CHECKSUMS`.

## Repository contents

    generate.sh      regenerate + checksum-verify all shapes (deterministic)
    bench.sh         measure one mlir-opt on all shapes -> results.tsv
    report.sh        render the comparison
    shapes.txt       shape manifest (generator, params, pass counts, phenomenon)
    gen/             deterministic shape generators
    shapes/          the static published repro + pinned checksums
    DESIGN_POINTS.md how to build/label each design point
    results.tsv      the ledger (every bench.sh run appends; report reads it)
    REPORT.md        a rendered snapshot of the current comparison + machine notes

Ir on the ~500k-op shape is skipped by `bench.sh` (callgrind there is a
~10-minute pole); its wall row carries the story. Nothing is silently capped --
the report says so.

## License

Apache License v2.0 with LLVM Exceptions (see `LICENSE`), matching LLVM/MLIR.
