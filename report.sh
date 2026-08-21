#!/bin/bash
# Print the design comparison from results.tsv.  ./report.sh
cd "$(dirname "$0")" && exec python3 report.py "$@"
