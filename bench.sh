#!/bin/bash
# Measure one mlir-opt build on all shapes and append to results.tsv. Point it
# at any mlir-opt; run it once per design point you want to compare.
#   ./bench.sh /path/to/mlir-opt [label]
# Wall clock (median of 7 iters, threading disabled) is taken on all shapes;
# steady-state Ir/pass (callgrind) on all shapes except large-500k, where
# callgrind is a ~10-minute pole and wall already tells the story.
set -u
cd "$(dirname "$0")"
MO="${1:?usage: ./bench.sh /path/to/mlir-opt [label]}"
LABEL="${2:-$(basename "$MO" | sed 's/^mlir-opt-//')}"
ITERS=7; IR_SKIP="large-500k"
command -v "$MO" >/dev/null 2>&1 || [ -x "$MO" ] || { echo "not an executable: $MO"; exit 1; }
[ -f shapes/wide-signatures-40k.mlir ] || { echo "run ./generate.sh first"; exit 1; }
command -v valgrind >/dev/null || { echo "valgrind not found (needed for Ir/pass)"; exit 1; }
LEDGER=results.tsv
[ -f "$LEDGER" ] || printf 'date\tlabel\tshape\tmetric\tN\traw\tspread\tnote\n' > "$LEDGER"
DATE=$(date -u +%Y-%m-%dT%H:%M:%SZ)
pipe(){ python3 -c "print('builtin.module('+','.join(['canonicalize']*$1)+')')"; }
emit(){ printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$DATE" "$LABEL" "$1" "$2" "$3" "$4" "$5" "$6" >> "$LEDGER"; }
nhi(){ awk -F'\t' -v n="$1" '$1==n{print $5}' shapes.txt; }
nlo(){ awk -F'\t' -v n="$1" '$1==n{print $4}' shapes.txt; }
SHAPES=$(grep -v '^#' shapes.txt | cut -f1)
[ -n "${SHAPES_ONLY:-}" ] && SHAPES="$SHAPES_ONLY"   # measure a subset: SHAPES_ONLY="a b" ./bench.sh ...
echo "== '$LABEL'  ($MO) =="
for s in $SHAPES; do
  h=$(nhi "$s"); pp=$(pipe "$h"); ws=""; rs=""
  for i in $(seq 1 $ITERS); do
    o=$(/usr/bin/time -v "$MO" "shapes/$s.mlir" -mlir-disable-threading -pass-pipeline="$pp" -o /dev/null 2>&1 >/dev/null)
    t=$(printf '%s\n' "$o" | sed -n 's/.*wall clock.*: //p')
    ws="$ws $(python3 -c "p='$t'.split(':');print(float(p[0])*60+float(p[1]) if len(p)==2 else float(p[0]))")"
    rs="$rs $(printf '%s\n' "$o" | sed -n 's/.*Maximum resident set size (kbytes): //p')"
  done
  read med mn mx <<<"$(python3 -c "import statistics as S;v=[float(x) for x in '$ws'.split()];print(f'{S.median(v):.4f} {min(v):.4f} {max(v):.4f}')")"
  rss=$(python3 -c "import statistics as S;v=[int(x) for x in '$rs'.split()];print(f'{S.median(v)/1024:.1f}')")
  emit "$s" wall_s "$h" "$med" "$mn..$mx" "iters=$ITERS"
  emit "$s" maxrss_mb "$h" "$rss" "" "iters=$ITERS"
  printf '  %-20s wall %ss  [%s..%s]  rss %sMB\n' "$s" "$med" "$mn" "$mx" "$rss"
done
JOBS=$(mktemp); IRR=$(mktemp)
for s in $SHAPES; do case " $IR_SKIP " in *" $s "*) continue;; esac; echo "$s $(nlo "$s")"; echo "$s $(nhi "$s")"; done > "$JOBS"
irrun(){ s="$1"; n="$2"; cg="/tmp/irb_${s}_${n}.$$.cg"
  valgrind --tool=callgrind --cache-sim=no --branch-sim=no --callgrind-out-file="$cg" \
    "$MO" "shapes/$s.mlir" -mlir-disable-threading \
    -pass-pipeline="$(python3 -c "print('builtin.module('+','.join(['canonicalize']*$n)+')')")" \
    -o /dev/null >/dev/null 2>/dev/null
  echo "$s	$n	$(grep '^summary:' "$cg" | awk '{print $2}')"; rm -f "$cg"; }
export -f irrun; export MO
xargs -P 8 -L1 bash -c 'irrun "$@"' _ < "$JOBS" > "$IRR"
for s in $SHAPES; do
  case " $IR_SKIP " in *" $s "*) printf '  %-20s ir/pass (skipped: callgrind pole; see wall)\n' "$s"; continue;; esac
  l=$(nlo "$s"); h=$(nhi "$s")
  lo=$(awk -F'\t' -v s="$s" -v n="$l" '$1==s&&$2==n{print $3}' "$IRR")
  hi=$(awk -F'\t' -v s="$s" -v n="$h" '$1==s&&$2==n{print $3}' "$IRR")
  ppv=$(python3 -c "print(int(round(($hi-$lo)/($h-$l))))")
  emit "$s" ir_per_pass "$l:$h" "$ppv" "" "callgrind"
  printf '  %-20s ir/pass %s\n' "$s" "$ppv"
done
rm -f "$JOBS" "$IRR"
echo "appended to $LEDGER   ->   ./report.sh for the comparison"
