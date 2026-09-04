#!/usr/bin/env python3
"""Wide-aggregate reuse shape: one LLVM-dialect function over a single very wide
struct type alias, used by every op in the body. Each of `chains` passes reads a
field, adds a scalar, and inserts it into a running aggregate, so the same
uniqued struct type stands at three positions of every op. Isolates the cost of
re-walking one wide type per use: a verifier that walks a type's sub-elements
at each occurrence pays width * uses; one that remembers the type pays width
once. Modeled on the reproducer posted on llvm/llvm-project#212354
(one 4096-field struct, four chains) and reproduces its cost driver."""
import argparse
p = argparse.ArgumentParser()
p.add_argument("--width", type=int, default=4096)
p.add_argument("--chains", type=int, default=4)
a = p.parse_args()
W, C = a.width, a.chains
print("!aggregate = !llvm.struct<(" + ", ".join(["i32"] * W) + ")>")
print("module {")
print("  llvm.func @reproducer(%input: !aggregate, %delta: i32) -> !aggregate {")
src = "%input"
for c in range(C):
    print(f"    %empty_{c} = llvm.mlir.undef : !aggregate")
    acc = f"%empty_{c}"
    for i in range(W):
        print(f"    %field_{c}_{i} = llvm.extractvalue {src}[{i}] : !aggregate")
        print(f"    %sum_{c}_{i} = llvm.add %field_{c}_{i}, %delta : i32")
        print(f"    %result_{c}_{i} = llvm.insertvalue %sum_{c}_{i}, {acc}[{i}] : !aggregate")
        acc = f"%result_{c}_{i}"
    src = acc
print(f"    llvm.return {src} : !aggregate")
print("  }")
print("}")
