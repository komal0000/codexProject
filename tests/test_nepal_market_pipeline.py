from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from tools.nepal_market_lib import (
    build_sheet_tabs,
    collect_sources,
    load_json,
    normalize_signals,
    run_research_pipeline,
    validate_signals,
)


ROOT = Path(__file__).resolve().parents[1]
BRIEF_PATH = ROOT / "examples" / "nepal_saas_brief.json"
RAW_SIGNALS_PATH = ROOT / "examples" / "raw_market_signals.json"


class NepalMarketPipelineTests(unittest.TestCase):
    def test_normalize_and_validate_example_signals(self) -> None:
        signals = normalize_signals(collect_sources([RAW_SIGNALS_PATH]))
        report = validate_signals(signals)
        self.assertEqual(report["errors"], [])
        self.assertGreaterEqual(len(signals), 8)
        self.assertEqual(
            {signal["signal_type"] for signal in signals},
            {"channel", "competitor", "icp", "lead_source", "open_question"},
        )

    def test_build_sheet_tabs_contains_expected_tabs(self) -> None:
        tabs = build_sheet_tabs(normalize_signals(collect_sources([RAW_SIGNALS_PATH])))
        self.assertEqual(
            set(tabs.keys()),
            {"ICPs", "Competitors", "Channels", "Lead Sources", "Open Questions"},
        )
        self.assertGreaterEqual(len(tabs["ICPs"]), 1)
        self.assertGreaterEqual(len(tabs["Channels"]), 1)

    def test_pipeline_writes_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            result = run_research_pipeline(BRIEF_PATH, [RAW_SIGNALS_PATH], temp_dir)
            output_dir = Path(result["output_dir"])
            self.assertTrue((output_dir / "raw_collected.json").exists())
            self.assertTrue((output_dir / "normalized_signals.json").exists())
            self.assertTrue((output_dir / "research_tabs.json").exists())
            self.assertTrue((output_dir / "strategy_summary.md").exists())
            tabs_payload = load_json(output_dir / "research_tabs.json")
            self.assertIn("ICPs", tabs_payload)


if __name__ == "__main__":
    unittest.main()
