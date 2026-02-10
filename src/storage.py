import csv
import os
from dataclasses import dataclass
from typing import Any

try:
    import gspread
    from google.oauth2.service_account import Credentials
except Exception:
    gspread = None
    Credentials = None


def _parse_csv(path: str) -> list[dict[str, Any]]:
    with open(path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: str, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    with open(path, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        writer.writeheader()
        writer.writerows(rows)


@dataclass
class SheetConfig:
    sheet_id: str
    tab_name: str


class GoogleSheetClient:
    def __init__(self, service_account_json: str) -> None:
        if gspread is None or Credentials is None:
            raise RuntimeError("Google Sheets dependencies not installed.")
        scopes = [
            "https://www.googleapis.com/auth/spreadsheets",
            "https://www.googleapis.com/auth/drive",
        ]
        creds = Credentials.from_service_account_file(service_account_json, scopes=scopes)
        self.client = gspread.authorize(creds)

    def read(self, cfg: SheetConfig) -> list[dict[str, Any]]:
        ws = self.client.open_by_key(cfg.sheet_id).worksheet(cfg.tab_name)
        return ws.get_all_records()

    def write(self, cfg: SheetConfig, rows: list[dict[str, Any]]) -> None:
        if not rows:
            return
        ws = self.client.open_by_key(cfg.sheet_id).worksheet(cfg.tab_name)
        headers = list(rows[0].keys())
        values = [headers] + [[row.get(h, "") for h in headers] for row in rows]
        ws.clear()
        ws.update(values)


class DataStore:
    def __init__(self) -> None:
        self._pilot_csv = "pilot_roster.csv"
        self._drone_csv = "drone_fleet.csv"
        self._mission_csv = "missions.csv"

        self._gs_json = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")
        self._pilot_sheet_id = os.getenv("PILOT_SHEET_ID")
        self._pilot_sheet_tab = os.getenv("PILOT_SHEET_TAB")
        self._drone_sheet_id = os.getenv("DRONE_SHEET_ID")
        self._drone_sheet_tab = os.getenv("DRONE_SHEET_TAB")

        self._gs_client = None
        if self._gs_json and self._pilot_sheet_id and self._pilot_sheet_tab:
            self._gs_client = GoogleSheetClient(self._gs_json)

    def _pilot_cfg(self) -> SheetConfig | None:
        if self._pilot_sheet_id and self._pilot_sheet_tab:
            return SheetConfig(self._pilot_sheet_id, self._pilot_sheet_tab)
        return None

    def _drone_cfg(self) -> SheetConfig | None:
        if self._drone_sheet_id and self._drone_sheet_tab:
            return SheetConfig(self._drone_sheet_id, self._drone_sheet_tab)
        return None

    def get_pilots(self) -> list[dict[str, Any]]:
        if self._gs_client and self._pilot_cfg():
            return self._gs_client.read(self._pilot_cfg())
        return _parse_csv(self._pilot_csv)

    def get_drones(self) -> list[dict[str, Any]]:
        if self._gs_client and self._drone_cfg():
            return self._gs_client.read(self._drone_cfg())
        return _parse_csv(self._drone_csv)

    def get_missions(self) -> list[dict[str, Any]]:
        return _parse_csv(self._mission_csv)

    def update_pilots(self, pilots: list[dict[str, Any]]) -> None:
        if self._gs_client and self._pilot_cfg():
            self._gs_client.write(self._pilot_cfg(), pilots)
        _write_csv(self._pilot_csv, pilots)

    def update_drones(self, drones: list[dict[str, Any]]) -> None:
        if self._gs_client and self._drone_cfg():
            self._gs_client.write(self._drone_cfg(), drones)
        _write_csv(self._drone_csv, drones)

    def update_missions(self, missions: list[dict[str, Any]]) -> None:
        _write_csv(self._mission_csv, missions)
