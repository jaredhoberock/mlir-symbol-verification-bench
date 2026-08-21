#!/usr/bin/env python3
"""Properties-dense, symbol-free-bodied shape: LLVM-dialect functions whose ops
all carry native or enum properties (gep rawConstantIndices, icmp predicate,
add/mul overflowFlags, func linkage/CConv/type). Every op feeds the return so
canonicalize erases nothing; ops depend on block args so nothing folds."""
import sys
n = int(sys.argv[1]) if len(sys.argv) > 1 else 10000
print("module {")
for i in range(n):
    print(f"""  llvm.func @f{i}(%a: i64, %b: i64, %p: !llvm.ptr) -> i64 {{
    %g = llvm.getelementptr %p[4] : (!llvm.ptr) -> !llvm.ptr, i64
    %g2 = llvm.getelementptr %g[%a] : (!llvm.ptr, i64) -> !llvm.ptr, i64
    %pi = llvm.ptrtoint %g2 : !llvm.ptr to i64
    %c = llvm.icmp "slt" %a, %b : i64
    %z = llvm.zext %c : i1 to i64
    %s1 = llvm.add %a, %pi : i64
    %s2 = llvm.add %s1, %z : i64
    %s3 = llvm.mul %s2, %b : i64
    llvm.return %s3 : i64
  }}""")
print("}")
