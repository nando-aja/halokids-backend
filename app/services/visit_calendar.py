"""
Kalender kunjungan / open house panti asuhan (PRD Modul E).

PRD menyebut kalender ini "dikelola statis oleh admin". Agar 10 tabel MySQL
yang sudah ada tidak perlu diubah, data disimpan sebagai file JSON di
storage/kalender_kunjungan.json. Penulisan bersifat atomik (file sementara
lalu os.replace) dan dilindungi lock agar aman untuk beberapa request.
"""
from __future__ import annotations

import json
import os
from datetime import date
from threading import Lock

from app.services.storage import STORAGE_DIR

CALENDAR_FILE = STORAGE_DIR / "kalender_kunjungan.json"
_lock = Lock()


def _read_all() -> list[dict]:
    if not CALENDAR_FILE.is_file():
        return []
    try:
        data = json.loads(CALENDAR_FILE.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return []
    return data if isinstance(data, list) else []


def _write_all(items: list[dict]) -> None:
    CALENDAR_FILE.parent.mkdir(parents=True, exist_ok=True)
    temp_file = CALENDAR_FILE.with_suffix(".json.tmp")
    temp_file.write_text(
        json.dumps(items, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    os.replace(temp_file, CALENDAR_FILE)


def _serialize(values: dict) -> dict:
    result = dict(values)
    if isinstance(result.get("tanggal"), date):
        result["tanggal"] = result["tanggal"].isoformat()
    return result


def list_events(
    panti_id: int | None = None,
    upcoming_only: bool = False,
) -> list[dict]:
    with _lock:
        items = _read_all()

    if panti_id is not None:
        items = [item for item in items if item.get("id_panti") == panti_id]

    if upcoming_only:
        today = date.today().isoformat()
        items = [item for item in items if item.get("tanggal", "") >= today]

    return sorted(items, key=lambda item: (item.get("tanggal", ""), item.get("jam_mulai") or ""))


def get_event(event_id: int) -> dict | None:
    with _lock:
        for item in _read_all():
            if item.get("id") == event_id:
                return item
    return None


def create_event(values: dict) -> dict:
    with _lock:
        items = _read_all()
        new_id = max((item.get("id", 0) for item in items), default=0) + 1
        event = {"id": new_id, **_serialize(values)}
        items.append(event)
        _write_all(items)
        return event


def update_event(event_id: int, changes: dict) -> dict | None:
    with _lock:
        items = _read_all()
        for item in items:
            if item.get("id") == event_id:
                item.update(_serialize(changes))
                _write_all(items)
                return item
    return None


def delete_event(event_id: int) -> bool:
    with _lock:
        items = _read_all()
        remaining = [item for item in items if item.get("id") != event_id]
        if len(remaining) == len(items):
            return False
        _write_all(remaining)
        return True
