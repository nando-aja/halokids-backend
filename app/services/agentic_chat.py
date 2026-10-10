from __future__ import annotations

import re
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import Any
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan


class Intent(Enum):
    GREETING = "greeting"
    ABOUT = "about"
    DOCUMENTS = "documents"
    DONATION = "donation"
    ADOPTION = "adoption"
    REPORT = "report"
    TRACK_REPORT = "track_report"
    PANTI = "panti"
    EMERGENCY = "emergency"
    UNKNOWN = "unknown"


@dataclass
class AgentResult:
    intent: Intent
    data: dict[str, Any] = field(default_factory=dict)
    actions: list[str] = field(default_factory=list)


class HaloKidsPublicAgent:
    """Kompatibilitas legacy untuk modul chatbot publik.

    Fitur endpoint chatbot tidak lagi diregistrasikan pada FastAPI, tetapi modul
    ini tetap dipertahankan agar kode lama dan pengujian yang mengimpor service
    tidak gagal di import time.
    """

    _emergency_keywords = (
        "dipukuli",
        "dianiaya",
        "diculik",
        "diperkosa",
        "dibunuh",
        "disiksa",
        "dicabuli",
        "ditelantarkan",
        "menganiaya",
        "membunuh",
        "menyakiti",
        "dibakar",
        "diancam",
        "kekerasan",
    )

    _report_keywords = (
        "lapor",
        "pengaduan",
        "kekerasan",
        "korban",
        "laporan",
        "penipuan",
        "pelecehan",
        "pencabulan",
        "melaporkan",
    )

    _donation_keywords = (
        "donasi",
        "donatur",
        "sumbangan",
        "bersedekah",
        "mau berdonasi",
    )

    _documents_keywords = (
        "dokumen",
        "syarat",
        "cota",
        "adopsi",
        "pengajuan adopsi",
        "persyaratan",
        "dokumen cota",
    )

    _panti_keywords = (
        "panti",
        "cari panti",
        "lokasi panti",
        "panti asuhan",
        "panti di",
    )

    def __init__(self) -> None:
        self._session_context: dict[str, Intent] = {}

    def classify(self, message: str) -> Intent:
        text = " ".join((message or "").lower().split())
        if not text:
            return Intent.UNKNOWN

        report_howto = (
            "cara melaporkan" in text
            or "bagaimana melaporkan" in text
            or "bagaimana cara melaporkan" in text
            or "cara lapor" in text
            or "melaporkan kekerasan" in text
        )
        if report_howto:
            return Intent.REPORT

        if self._contains_any(text, self._emergency_keywords):
            return Intent.EMERGENCY

        if "halokids" in text or "apa itu halokids" in text:
            return Intent.ABOUT

        if any(keyword in text for keyword in ("halo", "hai", "hi", "hello")):
            return Intent.GREETING

        if re.search(r"\b(?:cek|lihat|status|cari|tracking)\b.*\b(?:tiket|laporan)\b|hk-\d{8}-[a-z0-9]+", text, re.I):
            return Intent.TRACK_REPORT

        if self._contains_any(text, self._donation_keywords):
            return Intent.DONATION

        if "adopsi" in text or "proses adopsi" in text or "bagaimana proses adopsi" in text:
            return Intent.ADOPTION

        if self._contains_any(text, self._documents_keywords):
            return Intent.DOCUMENTS

        if self._contains_any(text, self._report_keywords):
            return Intent.REPORT

        if self._contains_any(text, self._panti_keywords):
            return Intent.PANTI

        return Intent.UNKNOWN

    def extract_entities(self, message: str) -> dict[str, list[date] | list[str]]:
        dates: list[date] = []
        for match in re.finditer(
            r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b|\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b",
            message,
        ):
            parts = [g for g in match.groups() if g is not None]
            if len(parts) == 3:
                if len(str(parts[2])) == 4:
                    day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                else:
                    year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                try:
                    dates.append(date(year, month, day))
                except ValueError:
                    continue
        return {"dates": dates}

    def handle(self, message: str, db: Session | None = None, session_id: str | None = None):
        if session_id is None:
            session_id = uuid4().hex

        previous_intent = self._session_context.get(session_id)
        followup = previous_intent is not None and self._looks_like_follow_up(message)

        if followup:
            intent = previous_intent
            actions = ["memakai konteks percakapan sebelumnya"]
        else:
            intent = self.classify(message)
            actions = []

        self._session_context[session_id] = intent

        if intent == Intent.TRACK_REPORT:
            ticket = self._extract_ticket(message)
            if ticket is None and db is not None:
                ticket = self._find_ticket_in_db(db, message)
            if ticket is not None:
                record = self._load_report_status(db, ticket) if db is not None else None
                if record is not None:
                    return session_id, AgentResult(intent=intent, data={"status": record.status}, actions=actions)
                return session_id, AgentResult(intent=intent, data={"status": "tidak_ditemukan"}, actions=actions)
            return session_id, AgentResult(intent=intent, data={"status": "tidak_ditemukan"}, actions=actions)

        if intent == Intent.PANTI:
            location = self._extract_location_hint(message)
            rows = self._query_panti(db, location) if db is not None else []
            items = [
                {
                    "id": row.id,
                    "nama_panti": row.nama_panti,
                    "alamat": row.alamat,
                    "kontak": row.kontak,
                    "status_akreditasi": row.status_akreditasi,
                }
                for row in rows
            ]
            return session_id, AgentResult(
                intent=intent,
                data={"jumlah": len(items), "items": items},
                actions=actions,
            )

        if intent == Intent.DOCUMENTS:
            return session_id, AgentResult(
                intent=intent,
                data={"dokumen": ["ktp", "kk", "akta_kelahiran", "surat_penghasilan", "persetujuan_keluarga"]},
                actions=actions,
            )

        if intent == Intent.ADOPTION:
            return session_id, AgentResult(
                intent=intent,
                data={"message": "Proses adopsi dimulai dengan dokumen awal dan tinjauan admin."},
                actions=actions,
            )

        if intent == Intent.DONATION:
            return session_id, AgentResult(
                intent=intent,
                data={"message": "Anda dapat memilih donasi uang atau barang sesuai kebutuhan panti."},
                actions=actions,
            )

        return session_id, AgentResult(
            intent=intent,
            data={"message": "Permintaan tidak dikenali."},
            actions=actions,
        )

    def _looks_like_follow_up(self, message: str) -> bool:
        text = message.lower()
        return any(keyword in text for keyword in ("lanjut", "terus", "lebih lanjut", "jelaskan", "ceritakan", "tolong"))

    def _extract_ticket(self, message: str) -> str | None:
        match = re.search(r"\bHK-\d{8}-[A-Z0-9]+\b", message, re.I)
        if match:
            return match.group(0).upper()
        return None

    def _find_ticket_in_db(self, db: Session, message: str) -> str | None:
        ticket = self._extract_ticket(message)
        if ticket is not None:
            return ticket
        match = re.search(r"\b[A-Z]{2}-\d{8}-[A-Z0-9]+\b", message, re.I)
        if match:
            return match.group(0).upper()
        return None

    def _load_report_status(self, db: Session, ticket: str) -> LaporanPengaduan | None:
        return db.query(LaporanPengaduan).filter(LaporanPengaduan.kode_tiket == ticket).first()

    def _extract_location_hint(self, message: str) -> str | None:
        text = message.lower()

        patterns = [
            r"\bdi\s+([a-zA-Z][a-zA-Z\s]+?)(?:\b|$)",
            r"\blokasi\s+([a-zA-Z][a-zA-Z\s]+?)(?:\b|$)",
            r"\b(?:surabaya|jakarta|bandung|malang|semarang)\b",
        ]

        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                value = match.group(1).strip() if match.lastindex else match.group(0).strip()
                if value and value not in {"di", "lokasi"}:
                    return value

        return None

    def _query_panti(self, db: Session | None, location: str | None) -> list[PantiAsuhan]:
        if db is None:
            return []
        query = db.query(PantiAsuhan)
        if location:
            query = query.filter(PantiAsuhan.alamat.ilike(f"%{location}%"))
        return query.order_by(PantiAsuhan.id.asc()).all()

    @staticmethod
    def _contains_any(text: str, keywords: Iterable[str]) -> bool:
        return any(keyword in text for keyword in keywords)


__all__ = ["HaloKidsPublicAgent", "Intent", "AgentResult"]
