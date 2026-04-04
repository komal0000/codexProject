from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

from nepal_market_lib import run_research_pipeline


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the end-to-end Nepal SaaS market research pipeline."
    )
    parser.add_argument("--brief", required=True, help="Research brief JSON file.")
    parser.add_argument("--sources", nargs="+", required=True, help="Raw source JSON/CSV files.")
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
    result = run_research_pipeline(args.brief, args.sources, args.output_dir)
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
