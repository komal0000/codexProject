from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nepal_market_lib import load_records_from_path, validate_signals, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Validate normalized Nepal market research signals."
    )
    parser.add_argument("--input", required=True, help="Normalized JSON or CSV file.")
    parser.add_argument(
        "--output",
        default=".tmp/nepal_market_research/validation_report.json",
        help="Output JSON path for validation results.",
    )
    parser.add_argument("--strict", action="store_true", help="Exit non-zero on warnings.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    signals = load_records_from_path(args.input)
    report = validate_signals(signals)
    output_path = write_json(args.output, report)
    print(json.dumps({"output": str(Path(output_path)), **report}, indent=2))
    if report["errors"]:
        return 1
    if args.strict and report["warnings"]:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
