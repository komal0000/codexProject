from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from collectors import collect_all_live_signals
from nepal_market_lib import default_output_dir, load_json, run_research_pipeline, write_json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the end-to-end Nepal SaaS market research pipeline."
    )
    parser.add_argument("--brief", required=True, help="Research brief JSON file.")
    parser.add_argument("--sources", nargs="*", default=[], help="Raw source JSON/CSV files.")
    parser.add_argument("--live", action="store_true", help="Collect live market signals before running the pipeline.")
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Optional output directory. Defaults to .tmp/nepal_market_research/<timestamp>.",
    )
    parser.add_argument(
        "--export-google",
        action="store_true",
        help="Export generated research tabs and summary to Google Sheets and Docs.",
    )
    parser.add_argument("--credentials", default=None, help="Google service account JSON.")
    parser.add_argument("--drive-folder-id", default=None, help="Optional Drive folder id.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.sources and not args.live:
        raise SystemExit("Provide --sources, --live, or both.")
    output_dir = Path(args.output_dir) if args.output_dir else None
    source_paths = list(args.sources)
    live_signals: list[dict[str, object]] = []
    if args.live:
        brief = load_json(args.brief)
        live_signals = asyncio.run(collect_all_live_signals(brief))
        output_root = output_dir or default_output_dir()
        live_path = write_json(output_root / "live_signals.json", live_signals)
        source_paths = [str(live_path), *source_paths]
        output_dir = output_root
    result = run_research_pipeline(args.brief, source_paths, output_dir)
    if args.live:
        result["live_signals_count"] = len(live_signals)
    if args.export_google:
        export_script = Path(__file__).resolve().parent / "export_google_workspace.py"
        command = [
            sys.executable,
            str(export_script),
            "--tabs",
            result["artifacts"]["research_tabs"],
            "--summary",
            result["artifacts"]["strategy_summary"],
            "--title",
            f"{Path(args.brief).stem}_nepal_market_research",
        ]
        if args.credentials:
            command.extend(["--credentials", args.credentials])
        if args.drive_folder_id:
            command.extend(["--drive-folder-id", args.drive_folder_id])
        completed = subprocess.run(command, check=True, capture_output=True, text=True)
        result["google_export"] = json.loads(completed.stdout)
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
