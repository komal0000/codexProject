from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from nepal_market_lib import load_json

SCOPES = [
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/spreadsheets",
]


def optional_google_imports() -> tuple[Any, Any]:
    try:
        from google.oauth2.service_account import Credentials
        from googleapiclient.discovery import build
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError(
            "Google export requires google-api-python-client and google-auth."
        ) from exc
    return Credentials, build


def tab_to_values(rows: list[dict[str, Any]]) -> list[list[Any]]:
    if not rows:
        return [["empty"], [""]]
    headers = list(rows[0].keys())
    values = [headers]
    for row in rows:
        values.append([row.get(header, "") for header in headers])
    return values


def load_services(credentials_path: str):
    Credentials, build = optional_google_imports()
    credentials = Credentials.from_service_account_file(credentials_path, scopes=SCOPES)
    sheets = build("sheets", "v4", credentials=credentials, cache_discovery=False)
    docs = build("docs", "v1", credentials=credentials, cache_discovery=False)
    drive = build("drive", "v3", credentials=credentials, cache_discovery=False)
    return sheets, docs, drive


def move_file_to_folder(drive_service: Any, file_id: str, folder_id: str) -> None:
    metadata = drive_service.files().get(fileId=file_id, fields="parents").execute()
    previous_parents = ",".join(metadata.get("parents", []))
    drive_service.files().update(
        fileId=file_id,
        addParents=folder_id,
        removeParents=previous_parents,
        fields="id, parents",
    ).execute()


def export_sheet(
    sheets_service: Any,
    drive_service: Any,
    tabs: dict[str, list[dict[str, Any]]],
    title: str,
    folder_id: str | None = None,
) -> dict[str, str]:
    sheet_titles = list(tabs.keys()) or ["Sheet1"]
    create_body = {
        "properties": {"title": title},
        "sheets": [{"properties": {"title": name}} for name in sheet_titles],
    }
    spreadsheet = sheets_service.spreadsheets().create(body=create_body).execute()
    spreadsheet_id = spreadsheet["spreadsheetId"]
    for tab_name, rows in tabs.items():
        sheets_service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=f"'{tab_name}'!A1",
            valueInputOption="RAW",
            body={"values": tab_to_values(rows)},
        ).execute()
    if folder_id:
        move_file_to_folder(drive_service, spreadsheet_id, folder_id)
    return {
        "spreadsheet_id": spreadsheet_id,
        "spreadsheet_url": f"https://docs.google.com/spreadsheets/d/{spreadsheet_id}",
    }


def export_doc(
    docs_service: Any,
    drive_service: Any,
    content: str,
    title: str,
    folder_id: str | None = None,
) -> dict[str, str]:
    document = docs_service.documents().create(body={"title": title}).execute()
    document_id = document["documentId"]
    docs_service.documents().batchUpdate(
        documentId=document_id,
        body={"requests": [{"insertText": {"location": {"index": 1}, "text": content}}]},
    ).execute()
    if folder_id:
        move_file_to_folder(drive_service, document_id, folder_id)
    return {
        "document_id": document_id,
        "document_url": f"https://docs.google.com/document/d/{document_id}",
    }


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Export research tabs and summary into Google Sheets and Google Docs."
    )
    parser.add_argument("--tabs", required=True, help="JSON file containing sheet tabs.")
    parser.add_argument("--summary", required=True, help="Markdown or text summary file.")
    parser.add_argument("--title", required=True, help="Base title for created Google files.")
    parser.add_argument(
        "--credentials",
        default=os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE"),
        help="Path to a Google service account JSON file.",
    )
    parser.add_argument(
        "--drive-folder-id",
        default=os.getenv("GOOGLE_DRIVE_FOLDER_ID"),
        help="Optional Drive folder id for created files.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.credentials:
        raise SystemExit("GOOGLE_SERVICE_ACCOUNT_FILE or --credentials is required.")
    tabs_payload = load_json(args.tabs)
    if not isinstance(tabs_payload, dict):
        raise ValueError("--tabs JSON must contain a tab-name-to-rows mapping.")
    tabs = tabs_payload
    summary_text = Path(args.summary).read_text(encoding="utf-8")
    sheets_service, docs_service, drive_service = load_services(args.credentials)
    sheet_result = export_sheet(
        sheets_service,
        drive_service,
        tabs,
        f"{args.title} - Research",
        folder_id=args.drive_folder_id,
    )
    doc_result = export_doc(
        docs_service,
        drive_service,
        summary_text,
        f"{args.title} - Brief",
        folder_id=args.drive_folder_id,
    )
    print(json.dumps({**sheet_result, **doc_result}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
