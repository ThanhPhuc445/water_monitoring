"""
CLI utility to label a CSV dataset using strict WHO-based rules.

Usage (Windows cmd):
  python -m sensor_analysis.label_dataset --input sensor_analysis/water_potability.csv --output sensor_analysis/water_potability_labeled.csv

The script auto-detects columns for pH, TDS/Solids, and Turbidity, and appends:
- label (clean/dirty)
- is_clean (bool)
- reasons (string)
- confidence (0..1)
"""
from __future__ import annotations

import argparse
import os
import sys
import pandas as pd

from .labeler import label_dataframe, LabelConfig


def main(argv=None):
    parser = argparse.ArgumentParser(description="Label water quality dataset (strict WHO rules)")
    parser.add_argument("--input", required=True, help="Input CSV file path")
    parser.add_argument("--output", required=True, help="Output CSV file path")
    parser.add_argument("--allow-borderline-clean", action="store_true", help="If set, treat borderline (TDS 500-1000 mg/L, NTU 1-5) as clean")
    args = parser.parse_args(argv)

    cfg = LabelConfig(strict=not args.allow_borderline_clean)

    if not os.path.exists(args.input):
        print(f"Input file not found: {args.input}", file=sys.stderr)
        return 2

    df = pd.read_csv(args.input)
    labeled = label_dataframe(df, cfg)
    # Ensure deterministic column order: original + new
    for col in ["label", "is_clean", "reasons", "confidence"]:
        if col not in labeled.columns:
            labeled[col] = None

    labeled.to_csv(args.output, index=False)
    print(f"Wrote labeled dataset to: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
