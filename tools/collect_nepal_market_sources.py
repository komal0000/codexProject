from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import collect_all_live_signals
from nepal_market_lib import collect_sources, load_json, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Collect local and live Nepal market source records into one canonical JSON file."
    )
    parser.add_argument("--inputs", nargs="*", default=[], help="Input JSON or CSV files.")
    parser.add_argument("--brief", default=None, help="Research brief JSON file for live collection.")
    parser.add_argument("--live", action="store_true", help="Fetch live signals from web collectors.")
    parser.add_argument(
        "--output",
        default=".tmp/nepal_market_research/raw_collected.json",
        help="Output JSON path for merged raw records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.inputs and not args.live:
        raise SystemExit("Provide --inputs, --live, or both.")
    if args.live and not args.brief:
        raise SystemExit("--brief is required when --live is used.")
    local_records = collect_sources(args.inputs) if args.inputs else []
    live_records = []
    if args.live:
        brief = load_json(args.brief)
        live_records = asyncio.run(collect_all_live_signals(brief))
    records = [*live_records, *local_records]
    output_path = write_json(args.output, records)
    print(
        json.dumps(
            {
                "live_records": len(live_records),
                "local_records": len(local_records),
                "total": len(records),
                "output": str(Path(output_path)),
            },
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
