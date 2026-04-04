from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path
from statistics import mean
from typing import Any
from urllib.parse import urlparse

REQUIRED_BRIEF_FIELDS = (
    "product_name",
    "product_description",
    "target_customer_guess",
    "pricing_model",
    "competitor_examples",
    "research_goal",
)
REQUIRED_SIGNAL_FIELDS = (
    "source",
    "segment",
    "city",
    "channel",
    "signal_type",
    "confidence",
    "notes",
    "url",
)
SIGNAL_TYPE_ALIASES = {
    "icp": "icp",
    "persona": "icp",
    "competitor": "competitor",
    "competition": "competitor",
    "channel": "channel",
    "distribution": "channel",
    "lead": "lead_source",
    "lead_source": "lead_source",
    "leadsource": "lead_source",
    "prospect": "lead_source",
    "open_question": "open_question",
    "question": "open_question",
    "risk": "open_question",
}
FOCUS_CITY_ALIASES = {
    "kathmandu": "Kathmandu",
    "ktm": "Kathmandu",
    "lalitpur": "Lalitpur",
    "patan": "Lalitpur",
    "pokhara": "Pokhara",
    "urban nepal": "Urban Nepal",
    "nationwide": "Nationwide",
    "nepal": "Nationwide",
}


def ensure_directory(path: Path | str) -> Path:
    directory = Path(path)
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def load_json(path: Path | str) -> Any:
    with Path(path).open("r", encoding="utf-8") as handle:
        return json.load(handle)


def write_json(path: Path | str, payload: Any) -> Path:
    output_path = Path(path)
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, ensure_ascii=True)
        handle.write("\n")
    return output_path


def write_text(path: Path | str, content: str) -> Path:
    output_path = Path(path)
    ensure_directory(output_path.parent)
    with output_path.open("w", encoding="utf-8", newline="\n") as handle:
        handle.write(content)
    return output_path


def write_csv(path: Path | str, rows: list[dict[str, Any]]) -> Path:
    output_path = Path(path)
    ensure_directory(output_path.parent)
    fieldnames = list(rows[0].keys()) if rows else ["empty"]
    with output_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        if rows:
            writer.writerows(rows)
        else:
            writer.writerow({"empty": ""})
    return output_path


def slugify(value: str) -> str:
    normalized = re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_")
    return normalized or "untitled"


def normalize_whitespace(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def clip_confidence(value: Any) -> float:
    if isinstance(value, (int, float)):
        numeric = float(value)
    else:
        raw = normalize_whitespace(value)
        numeric = float(raw.rstrip("%")) / 100 if raw.endswith("%") else float(raw or 0.5)
    if numeric > 1:
        numeric = numeric / 100
    return max(0.0, min(1.0, round(numeric, 2)))


def infer_city(text: str) -> str:
    haystack = text.lower()
    for alias, canonical in FOCUS_CITY_ALIASES.items():
        if alias in haystack:
            return canonical
    return "Urban Nepal"


def normalize_city(value: Any, fallback_text: str) -> str:
    if isinstance(value, list):
        for item in value:
            normalized = normalize_city(item, fallback_text)
            if normalized:
                return normalized
    city = normalize_whitespace(value)
    if not city:
        return infer_city(fallback_text)
    return FOCUS_CITY_ALIASES.get(city.lower(), city.title())


def infer_segment(text: str) -> str:
    haystack = text.lower()
    patterns = (
        ("agencies and consultancies", ("agency", "consultancy", "consultant")),
        ("startups and product teams", ("startup", "saas", "product team", "founder")),
        ("smes and local businesses", ("sme", "small business", "local business", "merchant")),
        ("education and training", ("college", "school", "training", "education")),
        ("hospitality and travel", ("hotel", "travel", "tourism", "restaurant")),
        ("ecommerce and retail", ("ecommerce", "e-commerce", "retail", "store")),
        ("b2b services", ("b2b", "operations", "sales team")),
    )
    for segment, keywords in patterns:
        if any(keyword in haystack for keyword in keywords):
            return segment
    return "unspecified urban buyers"


def infer_channel(text: str) -> str:
    haystack = text.lower()
    mapping = (
        ("LinkedIn", ("linkedin",)),
        ("Facebook", ("facebook", "fb group", "meta")),
        ("TikTok", ("tiktok",)),
        ("Instagram", ("instagram",)),
        ("Google Search", ("google search", "search ads", "seo", "search")),
        ("Email Outreach", ("email", "cold outreach", "newsletter")),
        ("Communities", ("community", "forum", "slack", "discord")),
        ("Events", ("meetup", "event", "conference", "webinar")),
        ("Referrals", ("referral", "partner", "word of mouth")),
    )
    for channel, keywords in mapping:
        if any(keyword in haystack for keyword in keywords):
            return channel
    return "Mixed"


def normalize_signal_type(value: Any) -> str:
    signal_type = normalize_whitespace(value).lower()
    if signal_type not in SIGNAL_TYPE_ALIASES:
        raise ValueError(f"Unsupported signal_type '{value}'")
    return SIGNAL_TYPE_ALIASES[signal_type]


def source_from_url(url: str) -> str:
    parsed = urlparse(url)
    return parsed.netloc.lower().removeprefix("www.") or "manual"


def infer_subject(record: dict[str, Any], signal_type: str) -> str:
    subject = normalize_whitespace(
        record.get("subject") or record.get("name") or record.get("title")
    )
    if subject:
        return subject
    defaults = {
        "channel": normalize_whitespace(record.get("channel")) or "Channel signal",
        "competitor": "Unnamed competitor",
        "lead_source": "Lead source",
        "open_question": "Open question",
        "icp": "Buyer signal",
    }
    return defaults[signal_type]


def validate_brief(brief: dict[str, Any]) -> list[str]:
    return [field for field in REQUIRED_BRIEF_FIELDS if not normalize_whitespace(brief.get(field))]


def load_records_from_path(path: Path | str) -> list[dict[str, Any]]:
    input_path = Path(path)
    if input_path.suffix.lower() == ".json":
        payload = load_json(input_path)
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("records"), list):
            return payload["records"]
        raise ValueError(f"JSON file {input_path} must contain a list or {{'records': []}}")
    if input_path.suffix.lower() == ".csv":
        with input_path.open("r", encoding="utf-8", newline="") as handle:
            return list(csv.DictReader(handle))
    raise ValueError(f"Unsupported input file type for {input_path}")


def collect_sources(source_paths: list[Path | str]) -> list[dict[str, Any]]:
    collected: list[dict[str, Any]] = []
    for path in source_paths:
        for record in load_records_from_path(path):
            record_copy = dict(record)
            record_copy.setdefault("_input_file", str(Path(path).name))
            collected.append(record_copy)
    return collected


def normalize_signal(record: dict[str, Any]) -> dict[str, Any]:
    raw_text = " ".join(
        normalize_whitespace(record.get(key))
        for key in ("subject", "name", "title", "segment", "notes", "description", "city", "channel")
    )
    url = normalize_whitespace(record.get("url"))
    signal_type = normalize_signal_type(record.get("signal_type"))
    notes = normalize_whitespace(record.get("notes") or record.get("description"))
    return {
        "source": normalize_whitespace(record.get("source")) or source_from_url(url),
        "subject": infer_subject(record, signal_type),
        "segment": normalize_whitespace(record.get("segment")) or infer_segment(raw_text),
        "city": normalize_city(record.get("city"), f"{raw_text} {url}"),
        "channel": normalize_whitespace(record.get("channel")) or infer_channel(f"{raw_text} {url}"),
        "signal_type": signal_type,
        "confidence": clip_confidence(record.get("confidence", 0.5)),
        "notes": notes or "No supporting notes supplied.",
        "url": url,
    }


def dedupe_signals(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    deduped: dict[tuple[str, str, str, str], dict[str, Any]] = {}
    for signal in signals:
        key = (
            signal["signal_type"],
            signal["subject"].lower(),
            signal["city"].lower(),
            (signal["url"] or signal["source"]).lower(),
        )
        existing = deduped.get(key)
        if existing is None or signal["confidence"] > existing["confidence"]:
            deduped[key] = signal
    return list(deduped.values())


def normalize_signals(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    normalized = [normalize_signal(record) for record in records]
    return sorted(dedupe_signals(normalized), key=lambda item: (item["signal_type"], item["subject"]))


def validate_signals(signals: list[dict[str, Any]]) -> dict[str, list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    duplicate_counter: Counter[tuple[str, str, str]] = Counter()
    allowed_cities = {"Kathmandu", "Lalitpur", "Pokhara", "Urban Nepal", "Nationwide"}
    for index, signal in enumerate(signals, start=1):
        for field in REQUIRED_SIGNAL_FIELDS:
            if field not in signal:
                errors.append(f"Row {index}: missing field '{field}'")
            elif field != "url" and signal[field] in ("", None):
                errors.append(f"Row {index}: empty required field '{field}'")
        confidence = signal.get("confidence")
        if not isinstance(confidence, (int, float)) or not 0 <= confidence <= 1:
            errors.append(f"Row {index}: confidence must be between 0 and 1")
        duplicate_counter[(signal["signal_type"], signal["subject"], signal["city"])] += 1
        if signal["city"] not in allowed_cities:
            warnings.append(f"Row {index}: non-default city '{signal['city']}' kept as-is")
    for key, count in duplicate_counter.items():
        if count > 1:
            warnings.append(
                f"Duplicate signal cluster detected for type={key[0]}, subject={key[1]}, city={key[2]}"
            )
    return {"errors": errors, "warnings": sorted(set(warnings))}


def summarize_notes(signals: list[dict[str, Any]], limit: int = 2) -> str:
    snippets = []
    for signal in sorted(signals, key=lambda item: item["confidence"], reverse=True)[:limit]:
        snippets.append(signal["notes"])
    return " | ".join(snippets)


def build_icp_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        if signal["signal_type"] == "icp":
            grouped[(signal["segment"], signal["city"])].append(signal)
    rows = []
    for (segment, city), items in sorted(grouped.items()):
        channels = sorted({signal["channel"] for signal in items if signal["channel"] != "Mixed"})
        rows.append(
            {
                "segment": segment,
                "city": city,
                "evidence_count": len(items),
                "avg_confidence": round(mean(signal["confidence"] for signal in items), 2),
                "suggested_channels": ", ".join(channels) or "Mixed",
                "evidence_summary": summarize_notes(items),
            }
        )
    return rows


def build_competitor_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "competitor": signal["subject"],
            "city": signal["city"],
            "channel": signal["channel"],
            "confidence": signal["confidence"],
            "source": signal["source"],
            "url": signal["url"],
            "notes": signal["notes"],
        }
        for signal in signals
        if signal["signal_type"] == "competitor"
    ]


def build_channel_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: defaultdict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for signal in signals:
        if signal["signal_type"] == "channel":
            grouped[(signal["channel"], signal["city"])].append(signal)
    rows = []
    for (channel, city), items in sorted(grouped.items()):
        rows.append(
            {
                "channel": channel,
                "city": city,
                "supporting_signals": len(items),
                "avg_confidence": round(mean(signal["confidence"] for signal in items), 2),
                "segments_seen": ", ".join(sorted({signal["segment"] for signal in items})),
                "supporting_sources": ", ".join(sorted({signal["source"] for signal in items})),
                "rationale": summarize_notes(items),
            }
        )
    return rows


def build_lead_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "lead_source": signal["subject"],
            "segment": signal["segment"],
            "city": signal["city"],
            "channel": signal["channel"],
            "confidence": signal["confidence"],
            "source": signal["source"],
            "url": signal["url"],
            "notes": signal["notes"],
        }
        for signal in signals
        if signal["signal_type"] == "lead_source"
    ]


def build_open_question_rows(signals: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "question": signal["subject"],
            "city": signal["city"],
            "confidence": signal["confidence"],
            "source": signal["source"],
            "url": signal["url"],
            "notes": signal["notes"],
        }
        for signal in signals
        if signal["signal_type"] == "open_question"
    ]


def build_sheet_tabs(signals: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "ICPs": build_icp_rows(signals),
        "Competitors": build_competitor_rows(signals),
        "Channels": build_channel_rows(signals),
        "Lead Sources": build_lead_rows(signals),
        "Open Questions": build_open_question_rows(signals),
    }


def summary_lines_from_rows(rows: list[dict[str, Any]], label_key: str, score_key: str | None = None) -> list[str]:
    if not rows:
        return ["- No validated signals yet."]
    ranked = sorted(rows, key=lambda item: item.get(score_key or label_key, 0), reverse=True)
    return ["- " + normalize_whitespace(row.get(label_key)) for row in ranked[:3]]


def render_strategy_summary(brief: dict[str, Any], tabs: dict[str, list[dict[str, Any]]]) -> str:
    product_name = brief["product_name"]
    lines = [
        f"# {product_name} Nepal Urban GTM Brief",
        "",
        f"Goal: {brief['research_goal']}",
        f"Product: {brief['product_description']}",
        f"Target customer hypothesis: {brief['target_customer_guess']}",
        f"Pricing model: {brief['pricing_model']}",
        f"Named competitors: {', '.join(brief['competitor_examples'])}",
        "",
        "## Recommended ICPs",
    ]
    if tabs["ICPs"]:
        for row in tabs["ICPs"][:3]:
            lines.append(
                f"- {row['segment']} in {row['city']} via {row['suggested_channels']} "
                f"(confidence {row['avg_confidence']}, evidence {row['evidence_count']})"
            )
    else:
        lines.append("- No ICP rows were generated.")
    lines.extend(["", "## Candidate Channels"])
    if tabs["Channels"]:
        for row in sorted(tabs["Channels"], key=lambda item: item["avg_confidence"], reverse=True)[:4]:
            lines.append(
                f"- {row['channel']} in {row['city']} for {row['segments_seen']} "
                f"(confidence {row['avg_confidence']})"
            )
    else:
        lines.append("- No channel signals were generated.")
    lines.extend(["", "## Competitors To Watch"])
    lines.extend(summary_lines_from_rows(tabs["Competitors"], "competitor", "confidence"))
    lines.extend(["", "## Lead Sources"])
    lines.extend(summary_lines_from_rows(tabs["Lead Sources"], "lead_source", "confidence"))
    lines.extend(["", "## Open Questions"])
    lines.extend(summary_lines_from_rows(tabs["Open Questions"], "question", "confidence"))
    lines.extend(
        [
            "",
            "## Next Actions",
            "- Review the highest-confidence ICP and channel rows before launching campaigns.",
            "- Replace example rows with live-source findings and re-run the pipeline.",
            "- Export validated tabs to Google Sheets and Docs for team review.",
            "",
        ]
    )
    return "\n".join(lines)


def write_tabs_to_csv(output_dir: Path | str, tabs: dict[str, list[dict[str, Any]]]) -> dict[str, str]:
    base_dir = ensure_directory(output_dir)
    written = {}
    for tab_name, rows in tabs.items():
        output_path = base_dir / f"{slugify(tab_name)}.csv"
        write_csv(output_path, rows)
        written[tab_name] = str(output_path)
    return written


def default_output_dir(base_dir: Path | str = ".tmp") -> Path:
    timestamp = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    return ensure_directory(Path(base_dir) / "nepal_market_research" / timestamp)


def run_research_pipeline(
    brief_path: Path | str,
    source_paths: list[Path | str],
    output_dir: Path | str | None = None,
) -> dict[str, Any]:
    brief = load_json(brief_path)
    missing_fields = validate_brief(brief)
    if missing_fields:
        raise ValueError(f"Brief is missing required fields: {', '.join(missing_fields)}")
    output_root = Path(output_dir) if output_dir else default_output_dir()
    ensure_directory(output_root)
    raw_records = collect_sources(source_paths)
    normalized_signals = normalize_signals(raw_records)
    validation = validate_signals(normalized_signals)
    if validation["errors"]:
        raise ValueError("Validation failed:\n" + "\n".join(validation["errors"]))
    tabs = build_sheet_tabs(normalized_signals)
    summary = render_strategy_summary(brief, tabs)
    raw_path = write_json(output_root / "raw_collected.json", raw_records)
    normalized_path = write_json(output_root / "normalized_signals.json", normalized_signals)
    validation_path = write_json(output_root / "validation_report.json", validation)
    tabs_path = write_json(output_root / "research_tabs.json", tabs)
    csv_paths = write_tabs_to_csv(output_root / "csv", tabs)
    summary_path = write_text(output_root / "strategy_summary.md", summary)
    return {
        "brief_path": str(Path(brief_path)),
        "source_paths": [str(Path(path)) for path in source_paths],
        "output_dir": str(output_root),
        "artifacts": {
            "raw_collected": str(raw_path),
            "normalized_signals": str(normalized_path),
            "validation_report": str(validation_path),
            "research_tabs": str(tabs_path),
            "strategy_summary": str(summary_path),
            "csv_tabs": csv_paths,
        },
        "validation": validation,
        "tabs": tabs,
        "summary": summary,
    }
