from __future__ import annotations

import argparse
import json
from pathlib import Path

from nepal_market_lib import collect_sources, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect local Nepal market source records into one canonical JSON file."
    )
    parser.add_argument("--inputs", nargs="+", required=True, help="Input JSON or CSV files.")
    parser.add_argument(
        "--output",
        default=".tmp/nepal_market_research/raw_collected.json",
        help="Output JSON path for merged raw records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    records = collect_sources(args.inputs)
    output_path = write_json(args.output, records)
    print(json.dumps({"records": len(records), "output": str(Path(output_path))}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
