#!/usr/bin/env python3
"""Render results.tsv as a per-shape design comparison (lower is better).
Wall clock first (what ships), steady-state Ir/pass second. Known design labels
are annotated and, when the 'before the interface' floor is present, each shape
gains the reviewer's line: pre-interface -> with-interface main (regression
factor) -> the designs, with a recovery fraction against the floor.
"""
import csv, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
LED = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "results.tsv")
# canonical display order + one-line role; unknown labels are appended
ROLE = {
 "pre-interface":   "before SymbolUserTypeInterface (upstream main post-revert #217959)",
 "upstream-main":   "with the interface = the #198435 regression (baseline)",
 "no-cache":        "PR walker only, no containment cache",
 "verifier-scoped": "containment cache owned per verifier scope",
 "context-cache":   "containment cache owned by MLIRContext (the PR)",
}
ORDER = ["pre-interface", "upstream-main", "no-cache", "verifier-scoped", "context-cache"]
BASELINE = "upstream-main"   # the with-interface regression; ratios are relative to it

def shapes():
    out = []
    for ln in open(os.path.join(HERE, "shapes.txt")):
        if ln.startswith("#") or not ln.strip(): continue
        p = ln.rstrip("\n").split("\t"); out.append((p[0], p[3], p[4], p[5]))
    return out

def load():
    latest = {}
    for r in csv.DictReader(open(LED), delimiter="\t"):
        k = (r["shape"], r["metric"], r["label"])
        if k not in latest or r["date"] > latest[k]["date"]: latest[k] = r
    return latest

def order_labels(present):
    return [l for l in ORDER if l in present] + sorted(present - set(ORDER))

def table(latest, shape, metric, unit, scale, dec):
    vals = {l: latest[(shape, metric, l)] for (s, m, l) in latest if s == shape and m == metric}
    if not vals: return
    labels = order_labels(set(vals))
    base = float(vals[BASELINE]["raw"]) if BASELINE in vals else max(float(v["raw"]) for v in vals.values())
    N = next(iter(vals.values()))["N"]
    print(f"\n  {metric.split('_')[0].upper()}  (N={N}; lower is better)")
    for l in labels:
        v = float(vals[l]["raw"]); sp = vals[l]["spread"]
        rel = f"{v/base:5.2f}x" if base else "  -  "
        tag = ROLE.get(l, "(custom design point)")
        spr = f"  [{sp}]" if sp else ""
        print(f"    {l:<16} {v/scale:9.{dec}f} {unit}  {rel}  {tag}{spr}")
    # reviewer line
    if {"pre-interface", "upstream-main", "context-cache"} <= set(vals):
        X = float(vals["pre-interface"]["raw"]); Y = float(vals["upstream-main"]["raw"])
        Z = float(vals["context-cache"]["raw"])
        fac = Y / X if X else float("nan"); rec = (Y - Z) / (Y - X) * 100 if (Y - X) else float("nan")
        band = "in the 2-3x band" if 2.0 <= fac <= 3.0 else ("BELOW 2x" if fac < 2 else "ABOVE 3x")
        print(f"    reviewer: pre-interface {X/scale:.{dec}f}{unit} -> main {Y/scale:.{dec}f}{unit} "
              f"= {fac:.2f}x regression ({band}) -> context-cache {Z/scale:.{dec}f}{unit}; "
              f"recovery vs floor = {rec:.0f}%")

def main():
    latest = load()
    print("=" * 78)
    print("MLIR symbol-table verification -- design comparison (lower is better)")
    print("WALL is end-to-end mlir-opt time (what ships); Ir/pass is steady-state")
    print("retired instructions per verification pass. Threading disabled throughout.")
    print("=" * 78)
    for name, nlo, nhi, pheno in shapes():
        has = any((name, m, l) in latest for m in ("wall_s", "ir_per_pass") for l in ROLE)
        if not has and not any(k[0] == name for k in latest): continue
        print(f"\n### {name}\n  {pheno}")
        table(latest, name, "wall_s", "s", 1.0, 3)
        rss = {l: latest.get((name, "maxrss_mb", l)) for l in order_labels({k[2] for k in latest if k[0]==name and k[1]=="maxrss_mb"})}
        if any(rss.values()):
            print("  MaxRSS: " + "  ".join(f"{l}={float(r['raw']):.0f}MB" for l, r in rss.items() if r))
        table(latest, name, "ir_per_pass", "M", 1e6, 1)
    print("\n" + "=" * 78)
    print("Every number traces to a row in results.tsv. Ir on large-500k is omitted")
    print("(callgrind ~10-min pole); its story is in the wall row.")

if __name__ == "__main__":
    main()
