# Nepal SaaS Market Research Workflow

## Objective
Produce a Nepal-focused market research pack for a SaaS or digital product. The workflow is urban-first: Kathmandu, Lalitpur, and Pokhara, with English-dominant digital channels prioritized for faster validation.

## Required Inputs
- `product_name`
- `product_description`
- `target_customer_guess`
- `pricing_model`
- `competitor_examples`
- `research_goal`
- one or more local raw source files in JSON or CSV

Use [`examples/nepal_saas_brief.json`](../examples/nepal_saas_brief.json) as the baseline brief shape. Raw source files must contain rows that can map to:
- `source`
- `subject` or `name`
- `signal_type`
- `notes`
- optional `segment`, `city`, `channel`, `confidence`, `url`

## Tools
1. `tools/collect_nepal_market_sources.py`
2. `tools/normalize_nepal_market_data.py`
3. `tools/validate_research_rows.py`
4. `tools/run_nepal_market_research.py`
5. `tools/export_google_workspace.py`

## Default Run Sequence
1. Confirm the brief has all required fields.
2. Merge one or more raw source files into one canonical dataset.
3. Normalize rows into the standard schema.
4. Validate required fields, confidence values, and duplicate clusters.
5. Build research tabs:
   - `ICPs`
   - `Competitors`
   - `Channels`
   - `Lead Sources`
   - `Open Questions`
6. Generate a strategy summary in Markdown.
7. Export the tabs and summary to Google Sheets and Docs when credentials are available.

## Example Command
```powershell
python tools/run_nepal_market_research.py `
  --brief examples/nepal_saas_brief.json `
  --sources examples/raw_market_signals.json
```

Add `--export-google --credentials path\to\service_account.json` once Google access is configured.

## Expected Outputs
- `.tmp/nepal_market_research/<timestamp>/raw_collected.json`
- `.tmp/nepal_market_research/<timestamp>/normalized_signals.json`
- `.tmp/nepal_market_research/<timestamp>/validation_report.json`
- `.tmp/nepal_market_research/<timestamp>/research_tabs.json`
- `.tmp/nepal_market_research/<timestamp>/csv/*.csv`
- `.tmp/nepal_market_research/<timestamp>/strategy_summary.md`
- optional Google Sheet id/url and Google Doc id/url

## Failure Handling
- If the brief is missing required fields, stop and fix the brief first.
- If normalization fails on an unknown `signal_type`, update the input row or extend the signal type mapping intentionally.
- If validation returns errors, do not export. Fix the source rows and re-run.
- If Google export fails because of missing credentials or libraries, keep the local outputs and resolve configuration before re-running export.

## Review Checklist
- ICP rows represent real Nepal buyer segments rather than generic global personas.
- Channel recommendations are supported by concrete source notes.
- Competitors and lead sources include URLs where available.
- Open questions capture gaps that still need manual or live-source validation.
