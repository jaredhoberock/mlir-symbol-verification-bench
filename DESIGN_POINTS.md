# Design points

Each row below is one `mlir-opt` build the benchmark compares. Binaries are not
committed (they are hundreds of MB). To reproduce a column: check out the SHA in
an `llvm-project` tree, build `mlir-opt` (Release + assertions, any target set),
then `./bench.sh /path/to/that/mlir-opt <label>`. Use the label in the first
column so the report annotates it.

All measured binaries here were Release+asserts, X86-only, static
(`BUILD_SHARED_LIBS=OFF`), clang++.

| label | built at (llvm-project SHA) | what it is |
|---|---|---|
| `pre-interface` | `9a9b50168182` | Upstream main **after** the SymbolUserTypeInterface revert (#217959): the "before the interface was added" state -- the floor recoveries are measured against. |
| `upstream-main` | `7198b3fd6b3b` | Upstream main **with** the interface (#198435), before the revert: the regression baseline (1.00x in the report). |
| `no-cache` | `1ad1207652c6` | The PR's first two commits only: the per-scope hoisted walker + visited memo + cheap attribute-root enumeration, but **no** containment cache (no provably-free pruning). The floor the cache must beat. |
| `verifier-scoped` | `0c5a63240a91` | The PR's containment cache, but owned **per verifier scope** (a fresh cache in every `detail::verifySymbolTable`). Rebuilt per scope and per verification pass. |
| `context-cache` | `44a568c03f79` | The PR as it stands: the containment cache is owned by the `MLIRContext`, so it amortizes across every symbol-table scope and across the repeated verification passes. |

## Notes on comparability

- `pre-interface` (`9a9b5016`) and `upstream-main` (`7198b3fd`) sit on main tips
  **196 commits apart**. That delta is dominated by the interface revert
  (#217959) but also carries a day of unrelated upstream churn, so the
  `pre-interface -> upstream-main` regression factor is *approximately*, not
  exactly, the interface's cost. It is the honest apples-to-apples the external
  reviewer asked for ("entries for before this interface was added").
- `context-cache` was measured at `44a568c03f79`. Behavior-identity between the
  listed design points was verified during development on a 48-case corpus
  (byte-identical `mlir-opt` outputs); a later restack onto a fresh upstream main
  preserved that behavior, so the numbers still describe the current PR. Within
  this repo the reproducible equivalence check is `bench.sh` itself -- identical
  Ir counts across runs of the same binary are a strong determinism signal.
- `no-cache`, `verifier-scoped`, and `context-cache` share the PR's base; they
  differ only in the cache's presence and ownership.
