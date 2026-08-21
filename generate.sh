#!/bin/bash
# Generate every benchmark shape deterministically and verify byte-identity
# against the pinned checksums. No mlir-opt needed; ~1 minute.
#   ./generate.sh
set -u
cd "$(dirname "$0")"
ok=1
while IFS=$'\t' read -r name gen params nlo nhi rest; do
  case "$name" in ''|\#*) continue;; esac
  f="shapes/$name.mlir"
  if [ "$gen" = STATIC ]; then cp "shapes/$params" "$f"
  else python3 "gen/$gen" $params > "$f"; fi
  sha=$(sha256sum "$f" | cut -d' ' -f1)
  pin=$(awk -F'\t' -v n="$name" '$1==n{print $2}' shapes/CHECKSUMS)
  if   [ -z "$pin" ];        then echo "  $name  generated (unpinned)"
  elif [ "$pin" = "$sha" ];  then echo "  $name  ok"
  else echo "  $name  CHECKSUM MISMATCH (want ${pin:0:12}, got ${sha:0:12})"; ok=0; fi
done < <(grep -v '^#' shapes.txt)
[ "$ok" = 1 ] && echo "shapes ready." || { echo "regeneration did not reproduce pinned bytes"; exit 1; }
