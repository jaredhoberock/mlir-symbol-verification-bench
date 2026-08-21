#!/usr/bin/env python3
"""Scope-heavy discriminator for the containment-cache ownership question.

Many symbol-table scopes (nested builtin.module ops), each holding functions
whose signature types are drawn from ONE shared type pool, so the same uniqued
types recur across scopes. A context-owned containment cache fills each uniqued
type once for the whole module and hits thereafter -- across scopes and across
the repeated verification passes; a scope-owned cache is instantiated fresh in
every verifySymbolTable call, so it refills the pool for every scope on every
pass. Inert under -canonicalize.
"""
import argparse


def build_type_pool(n):
    scalars = ["i1", "i8", "i16", "i32", "i64", "f16", "f32", "f64", "bf16"]
    pool, seen = [], set()

    def add(t):
        if t not in seen:
            seen.add(t)
            pool.append(t)

    for s in scalars:
        add(s)
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
            s2 = scalars[(i + round_no) % len(scalars)]
            add(f"tuple<{s}, {s2}>")
            add(f"tuple<{s}, memref<{d0}x{s2}>>")
            add(f"({s}) -> {s2}")
            if len(pool) >= n:
                break
    return pool[:n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scopes", type=int, default=640)
    ap.add_argument("--funcs-per-scope", type=int, default=32)
    ap.add_argument("--sig-width", type=int, default=6)
    ap.add_argument("--types", type=int, default=300)
    ap.add_argument("--attrs-per-op", type=int, default=2)
    ap.add_argument("--symbol-density", type=float, default=0.02)
    args = ap.parse_args()

    pool = build_type_pool(args.types)
    P = len(pool)
    W = args.sig_width
    F = args.funcs_per_scope
    sym_stride = max(1, int(round(1.0 / args.symbol_density))) \
        if args.symbol_density > 0 else 0

    out = ["module {"]
    g = 0  # global function index, slides the pool window across scopes
    for s in range(args.scopes):
        out.append("  module {")
        for local in range(F):
            base = (g * W) % P
            sig = [pool[(base + j) % P] for j in range(W)]
            params = ", ".join(f"%a{j}: {sig[j]}" for j in range(W))
            attrs = [f"tag{k} = {g * 7 + k} : i64"
                     for k in range(args.attrs_per_op)]
            if sym_stride and (g % sym_stride == 0):
                attrs.append(f"ref = @s{s}_f{(local * 3 + 1) % F}")
            attr_str = (" attributes {" + ", ".join(attrs) + "}") if attrs else ""
            results = ", ".join(sig)
            vals = ", ".join(f"%a{j}" for j in range(W))
            out.append(
                f"    func.func @s{s}_f{local}({params}) -> ({results}){attr_str} {{")
            out.append(f"      return {vals} : {results}")
            out.append("    }")
            g += 1
        out.append("  }")
    out.append("}")
    print("\n".join(out))


if __name__ == "__main__":
    main()
