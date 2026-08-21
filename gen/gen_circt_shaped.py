#!/usr/bin/env python3
"""Synthesize a CIRCT-shaped module that stresses SymbolTable verification.

Reproducer harness for llvm/llvm-project#212354. The symbol-table verifier
(as reshaped by #198435) walks the operand, result, and block-argument types
of every operation, plus the operation's attribute roots, once per verification
pass -- and a whole verification pass runs after every IR-mutating pass. The
cache design under review answers "may this type/attr transitively contain a
SymbolRefAttr?" with a hash probe into a per-context map for each such type
occurrence; the storage-bit design answers it with a bit read from storage the
walk already touches. The instruction-count gap between the two therefore grows
with the number of type occurrences the verifier meets, not with wall time.

The published 8000-empty-function reproducer -- a different artifact from this
repo's dictionary-heavy shape (shapes/published_repro.mlir, whose functions carry
large distinct attribute dictionaries) -- cannot see the gap: empty bodies carry
no operand/result/block-argument types, so almost every function shares the one
uniqued ()->() function type -- a single hot cache bucket, no real type-root
traffic. This generator instead gives each function a rich signature (and,
optionally, a rich body) whose types are drawn from a large pool of distinct
parameterized types, so each verification pass performs many distinct-type
containment probes.

Knobs, each isolating one driver of the effect:
  --funcs        number of functions (op-count / occurrence-count scale)
  --sig-width    params == results per function; each contributes a
                 block-argument type occurrence and a return-operand type
                 occurrence per pass (type-root traffic per op)
  --body-ops     extra in-body ops (unrealized_conversion_cast chains) that
                 add operand+result type occurrences without changing symbols
  --types        size of the distinct-type pool (type diversity: spreads the
                 containment map across many buckets)
  --attrs-per-op count of small discardable attributes per function (modest,
                 realistic attribute roots -- never a giant dictionary)
  --symbol-density  fraction of functions carrying a SymbolRefAttr use
                 (CIRCT-ish sparsity: symbols exist, most attrs hold none)

The IR is built to be inert under -canonicalize: bare signature threading and
side-effecting-free casts that canonicalize leaves in place, so every pass in a
repeated pipeline re-verifies the same structure.
"""
import argparse


def build_type_pool(n):
    """Return a list of n distinct MLIR type spellings of varied shape.

    The pool mixes scalars, 1-D/2-D memrefs, vectors, tuples (which nest other
    pool types, giving the verifier real sub-element structure to walk), and
    function types. Ordering interleaves the families so a contiguous slice of
    the pool -- what one function draws -- is itself diverse.
    """
    scalars = ["i1", "i8", "i16", "i32", "i64", "f16", "f32", "f64", "bf16"]
    pool = []
    seen = set()

    def add(t):
        if t not in seen:
            seen.add(t)
            pool.append(t)

    # Scalars first so the smallest slices are still valid, varied types.
    for s in scalars:
        add(s)

    # Families generated in interleaved rounds so the pool stays diverse as it
    # grows; each round widens shape parameters.
    dim = 1
    round_no = 0
    while len(pool) < n:
        round_no += 1
        for i, s in enumerate(scalars):
            d0 = (round_no * 3 + i) % 64 + 1
            d1 = (round_no * 5 + i) % 32 + 1
            add(f"memref<{d0}x{s}>")
            add(f"memref<{d0}x{d1}x{s}>")
            add(f"vector<{d0}x{s}>")
            add(f"memref<?x{s}>")
            # Tuples nest two other scalars -> sub-elements for the walk.
            s2 = scalars[(i + round_no) % len(scalars)]
            add(f"tuple<{s}, {s2}>")
            add(f"tuple<{s}, memref<{d0}x{s2}>>")
            # Function types as first-class types.
            add(f"({s}) -> {s2}")
            if len(pool) >= n:
                break
        dim += 1

    return pool[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--funcs", type=int, default=20000)
    ap.add_argument("--sig-width", type=int, default=6,
                    help="params == results per function")
    ap.add_argument("--body-ops", type=int, default=0,
                    help="extra cast ops per function body")
    ap.add_argument("--types", type=int, default=1400,
                    help="distinct-type pool size")
    ap.add_argument("--attrs-per-op", type=int, default=2)
    ap.add_argument("--symbol-density", type=float, default=0.02,
                    help="fraction of functions bearing a SymbolRefAttr")
    args = ap.parse_args()

    pool = build_type_pool(args.types)
    P = len(pool)
    W = args.sig_width

    out = ["module {"]
    sym_stride = max(1, int(round(1.0 / args.symbol_density))) \
        if args.symbol_density > 0 else 0

    for i in range(args.funcs):
        # Draw W types for the signature from a per-function window into the
        # pool, so different functions exercise different regions of it while
        # neighbours overlap (realistic reuse).
        base = (i * W) % P
        sig = [pool[(base + j) % P] for j in range(W)]
        params = ", ".join(f"%a{j}: {sig[j]}" for j in range(W))

        # Small, realistic attribute roots.
        attrs = [f'tag{k} = {i * 7 + k} : i64' for k in range(args.attrs_per_op)]
        # Sparse symbol use: reference some other existing function by name.
        if sym_stride and (i % sym_stride == 0):
            attrs.append(f"ref = @fn{(i * 3 + 1) % args.funcs}")
        attr_str = (" attributes {" + ", ".join(attrs) + "}") if attrs else ""

        # Body casts thread each signature slot's current value forward: each is
        # a cast of a live value to a fresh pool type, and its result is either
        # cast again or returned, so the ops survive DCE and -canonicalize
        # leaves them in place (no identity round-trips). Each adds an operand
        # and a result type occurrence the verifier walks every pass.
        vals = [f"%a{j}" for j in range(W)]
        val_types = list(sig)
        casts = []
        for b in range(args.body_ops if W > 0 else 0):
            slot = b % W
            dst_ty = pool[(base + W + 1 + b) % P]
            casts.append(
                f"    %c{b} = builtin.unrealized_conversion_cast "
                f"{vals[slot]} : {val_types[slot]} to {dst_ty}")
            vals[slot] = f"%c{b}"
            val_types[slot] = dst_ty

        # The result signature reflects the final (possibly cast) value types.
        results = ", ".join(val_types)
        out.append(f"  func.func @fn{i}({params}) -> ({results}){attr_str} {{")
        out.extend(casts)
        if W > 0:
            out.append("    return " +
                       ", ".join(vals) + " : " + ", ".join(val_types))
        else:
            out.append("    return")
        out.append("  }")

    out.append("}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
