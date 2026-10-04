from __future__ import annotations

import re
from collections import defaultdict, deque
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from enum import StrEnum
from threading import Lock
from uuid import uuid4

from sqlalchemy.orm import Session

from app.db.models.donation import Donasi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.user import User
from app.services.adoption_eligibility import check_adoption_eligibility
from app.services.public_statistics import get_public_statistics


class Intent(StrEnum):
    ABOUT = "about"
    GREETING = "greeting"
    HELP = "help"
    EMERGENCY = "emergency"
    REPORT = "report"
    TRACK_REPORT = "track_report"
    ADOPTION = "adoption"
    ELIGIBILITY = "eligibility"
    DOCUMENTS = "documents"
    DONATION = "donation"
    VOLUNTEER = "volunteer"
    PANTI = "panti"
    STATISTICS = "statistics"
    PRIVACY = "privacy"
    UNKNOWN = "unknown"


@dataclass
class ChatSession:
    messages: deque[dict[str, str]] = field(default_factory=lambda: deque(maxlen=8))
    last_active: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    last_intent: "Intent | None" = None


class ChatSessionStore:
    """Short-term, in-memory conversation memory. No chat message is persisted to MySQL."""

    def __init__(self, ttl_minutes: int = 30, max_sessions: int = 1000) -> None:
        self.ttl = timedelta(minutes=ttl_minutes)
        self.max_sessions = max_sessions
        self._sessions: dict[str, ChatSession] = {}
        self._lock = Lock()

    def get_or_create(self, session_id: str | None) -> tuple[str, ChatSession]:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            sid = session_id or uuid4().hex
            session = self._sessions.get(sid)
            if session is None:
                if len(self._sessions) >= self.max_sessions:
                    oldest = min(
                        self._sessions,
                        key=lambda key: self._sessions[key].last_active,
                    )
                    self._sessions.pop(oldest, None)
                session = ChatSession()
                self._sessions[sid] = session
            session.last_active = now
            return sid, session

    def _purge(self, now: datetime) -> None:
        expired = [
            sid
            for sid, session in self._sessions.items()
            if now - session.last_active > self.ttl
        ]
        for sid in expired:
            self._sessions.pop(sid, None)


@dataclass
class AgentResult:
    message: str
    intent: Intent
    actions: list[str]
    data: dict | None = None


class HaloKidsPublicAgent:
    """
    Custom deterministic agentic AI for the public HaloKids portal.

    No external AI/LLM/API is used. The agent performs:
    1. intent detection,
    2. entity extraction,
    3. tool selection,
    4. database/tool execution,
    5. response generation.
    """

    name = "HaloKids Custom Agentic AI"

    # Kata kerja yang menandakan anak sedang/telah mengalami kekerasan fisik,
    # seksual, atau eksploitasi. Bila muncul, agent memprioritaskan jalur darurat.
    VIOLENCE_WORDS: tuple[str, ...] = (
        "dipukul", "dipukuli", "dianiaya", "disiksa", "diperkosa",
        "dilecehkan", "dicabuli", "diraba", "diculik", "dikurung", "dibunuh",
        "dilukai", "ditendang", "ditampar", "dijual", "diperdagangkan",
        "dipaksa bekerja", "berdarah", "pemukulan", "penganiayaan", "pelecehan", "pemerkosaan", "penculikan",
        "kekerasan", "penelantaran", "perundungan", "bullying",
    )
    URGENCY_PATTERN = re.compile(
        r"\b(sekarang|saat ini|sedang|lagi|barusan|baru saja|segera|tolong|darurat)\b",
        re.I,
    )
    INFORMATIONAL_REPORT_PATTERN = re.compile(
        r"\b(bagaimana|gimana|cara|apa|syarat|proses|panduan|untuk apa|bolehkah|apakah)\b",
        re.I,
    )
    FOLLOW_UP_PATTERN = re.compile(
        r"\b(lebih lanjut|lanjut|lanjutkan|detail|rinci|jelaskan lagi|apa lagi|"
        r"terus|kalau begitu|kalau gitu|itu tadi|selanjutnya|berikutnya|"
        r"maksudnya|contohnya)\b",
        re.I,
    )

    INTENT_KEYWORDS: dict[Intent, tuple[str, ...]] = {
        Intent.ABOUT: (
            "apa itu halokids", "tentang halokids", "halokids itu", "apa itu halo kids",
            "apa itu portal ini", "web ini untuk apa", "siapa kamu", "kamu siapa",
        ),
        Intent.EMERGENCY: (
            "darurat", "bahaya", "diselamatkan", "ancaman", "kekerasan sekarang",
            "butuh bantuan sekarang", "segera lapor", "sapa 129",
        ),
        Intent.TRACK_REPORT: (
            "lacak tiket", "cek tiket", "status tiket", "status laporan",
            "nomor tiket", "kode tiket", "cek laporan",
        ),
        Intent.ELIGIBILITY: (
            "layak adopsi", "kelayakan adopsi", "cek kelayakan", "boleh adopsi",
            "umur untuk adopsi", "usia adopsi", "lama menikah", "berapa tahun menikah",
        ),
        Intent.DOCUMENTS: (
            "dokumen", "berkas", "syarat dokumen", "dokumen cota", "berkas adopsi",
            "ktp", "kk", "buku nikah", "skck", "surat sehat", "akta kelahiran",
        ),
        Intent.ADOPTION: (
            "adopsi", "orang tua angkat", "cota", "pengajuan adopsi", "proses adopsi",
        ),
        Intent.REPORT: (
            "lapor", "pengaduan", "kekerasan", "eksploitasi", "panti ilegal",
            "buat laporan", "cara melapor",
        ),
        Intent.DONATION: (
            "donasi", "donasi uang", "donasi barang", "transfer", "bukti transfer",
            "sumbangan", "bantuan panti",
        ),
        Intent.VOLUNTEER: (
            "relawan", "volunteer", "jadi relawan", "daftar relawan",
        ),
        Intent.PANTI: (
            "panti", "panti asuhan", "direktori panti", "panti terakreditasi",
            "lkasa", "panti resmi",
        ),
        Intent.STATISTICS: (
            "statistik", "jumlah kasus", "jumlah panti", "transparansi", "data publik",
            "berapa panti", "berapa laporan", "berapa donasi",
        ),
        Intent.PRIVACY: (
            "privasi", "rahasia", "kerahasiaan", "aman tidak", "data saya",
            "identitas pelapor", "data pribadi",
        ),
        Intent.HELP: (
            "bantuan", "help", "bisa apa", "fitur", "layanan apa", "cara menggunakan",
        ),
        Intent.GREETING: (
            "halo", "hai", "hi", "selamat pagi", "selamat siang", "selamat sore",
            "selamat malam", "permisi",
        ),
    }

    def __init__(self, store: ChatSessionStore | None = None) -> None:
        self.store = store or ChatSessionStore()

    def handle(
        self,
        message: str,
        db: Session,
        session_id: str | None = None,
    ) -> tuple[str, AgentResult]:
        cleaned = self._sanitize(message)
        sid, session = self.store.get_or_create(session_id)
        intent = self.classify(cleaned)
        used_context = False

        # Pesan lanjutan ("jelaskan lebih lanjut", "terus bagaimana?") tidak
        # memuat topik sendiri. Pakai topik terakhir dari memori sesi.
        if (
            intent is Intent.UNKNOWN
            and session.last_intent is not None
            and session.last_intent not in (Intent.UNKNOWN, Intent.GREETING)
            and self.FOLLOW_UP_PATTERN.search(cleaned)
        ):
            intent = session.last_intent
            used_context = True

        entities = self.extract_entities(cleaned)
        result = self.route(intent, cleaned, entities, db)

        if used_context:
            result.actions.insert(0, "memakai konteks percakapan sebelumnya")

        session.messages.append({"role": "user", "content": cleaned})
        session.messages.append({"role": "assistant", "content": result.message})
        session.last_intent = result.intent
        session.last_active = datetime.now(timezone.utc)

        return sid, result

    @staticmethod
    def _sanitize(message: str) -> str:
        message = " ".join(message.strip().split())
        if not message:
            raise ValueError("Pesan tidak boleh kosong.")
        return message[:1000]

    def classify(self, message: str) -> Intent:
        text = message.lower()
        if self._extract_ticket(text):
            return Intent.TRACK_REPORT

        if self._is_emergency(text):
            return Intent.EMERGENCY

        scores: dict[Intent, int] = defaultdict(int)
        for intent, keywords in self.INTENT_KEYWORDS.items():
            for keyword in keywords:
                if self._contains_keyword(text, keyword):
                    scores[intent] += max(1, len(keyword.split()))

        if not scores:
            return Intent.UNKNOWN

        # Emergency and ticket tracking have priority over general intents.
        if scores.get(Intent.EMERGENCY, 0) > 0:
            return Intent.EMERGENCY
        if scores.get(Intent.TRACK_REPORT, 0) > 0:
            return Intent.TRACK_REPORT

        # Use deterministic tie-breaking by specificity/priority.
        priority = [
            Intent.ABOUT,
            Intent.ELIGIBILITY,
            Intent.DOCUMENTS,
            Intent.ADOPTION,
            Intent.REPORT,
            Intent.DONATION,
            Intent.PANTI,
            Intent.VOLUNTEER,
            Intent.STATISTICS,
            Intent.PRIVACY,
            Intent.HELP,
            Intent.GREETING,
        ]
        best_score = max(scores.values())
        for intent in priority:
            if scores.get(intent, 0) == best_score:
                return intent
        return Intent.UNKNOWN

    @staticmethod
    def _contains_keyword(text: str, keyword: str) -> bool:
        """
        Kata pendek (<= 4 huruf, mis. "halo", "hai", "kk") harus cocok sebagai
        kata utuh agar "halokids" tidak terbaca sebagai sapaan. Kata yang lebih
        panjang boleh cocok sebagian agar imbuhan ("melapor", "pelaporan")
        tetap terdeteksi.
        """
        if len(keyword) <= 4:
            return re.search(rf"(?<![a-z0-9]){re.escape(keyword)}(?![a-z0-9])", text) is not None
        return keyword in text

    def _is_emergency(self, text: str) -> bool:
        """
        Bedakan laporan umum dengan kejadian yang sedang/baru saja terjadi.
        Kekerasan tanpa penanda urgensi tetap masuk jalur pengaduan biasa;
        kekerasan + urgensi diarahkan ke jalur darurat.
        """
        if any(self._contains_keyword(text, kw) for kw in (
            "sapa 129",
            "112",
            "butuh bantuan sekarang",
            "dalam bahaya",
            "sedang dianiaya",
            "sedang dipukul",
            "sedang diperkosa",
            "sedang disiksa",
            "tolong segera",
        )):
            return True

        has_violence = any(self._contains_keyword(text, word) for word in self.VIOLENCE_WORDS)
        has_urgency = self.URGENCY_PATTERN.search(text) is not None
        informational = self.INFORMATIONAL_REPORT_PATTERN.search(text) is not None
        mentions_child_or_victim = self._contains_keyword(text, "anak") or self._contains_keyword(text, "korban")
        explicit_emergency_phrase = any(
            phrase in text
            for phrase in (
                "anak dipukuli",
                "anak dianiaya",
                "anak disiksa",
                "anak diperkosa",
                "anak diculik",
                "anak dalam bahaya",
                "anak terancam",
            )
        )

        # Pertanyaan informasional murni seperti "bagaimana cara melaporkan
        # kekerasan pada anak" tidak boleh dipaksa menjadi emergency.
        if has_violence and informational and not has_urgency and not explicit_emergency_phrase:
            return False

        # Kasus nyata yang menyebut anak/korban langsung diarahkan ke triase
        # darurat, meskipun pengguna tidak menulis kata "sekarang".
        return has_violence and (
            has_urgency
            or explicit_emergency_phrase
            or mentions_child_or_victim and not informational
        )

    @staticmethod
    def extract_entities(message: str) -> dict:
        return {
            "ticket": HaloKidsPublicAgent._extract_ticket(message),
            "dates": HaloKidsPublicAgent._extract_dates(message),
            "wilayah": HaloKidsPublicAgent._extract_region(message),
            "panti_keyword": HaloKidsPublicAgent._extract_panti_keyword(message),
        }

    @staticmethod
    def _extract_ticket(message: str) -> str | None:
        match = re.search(r"\bHK-\d{8}-[A-Fa-f0-9]{8}\b", message, re.I)
        return match.group(0).upper() if match else None

    @staticmethod
    def _extract_dates(message: str) -> list[date]:
        matches = re.findall(
            r"\b(\d{1,2})[/-](\d{1,2})[/-](\d{4})\b"
            r"|\b(\d{4})[/-](\d{1,2})[/-](\d{1,2})\b",
            message,
        )
        result: list[date] = []
        for day, month, year, iso_year, iso_month, iso_day in matches:
            try:
                if iso_year:
                    parsed = date(int(iso_year), int(iso_month), int(iso_day))
                else:
                    parsed = date(int(year), int(month), int(day))
            except ValueError:
                continue
            if parsed not in result:
                result.append(parsed)
        return result[:4]

    @staticmethod
    def _extract_region(message: str) -> str | None:
        patterns = [
            r"(?:di|wilayah|daerah|kecamatan|kabupaten|kota)\s+([A-Za-z][A-Za-z .'-]{1,50}?)(?=\s+(?:yang|untuk|dengan|dan|atau)|[?.!,]|$)",
        ]
        for pattern in patterns:
            match = re.search(pattern, message, re.I)
            if match:
                value = match.group(1).strip(" .,!?\n")
                stop_words = {
                    "untuk", "yang", "dan", "atau", "dengan", "itu", "dong", "saja",
                }
                words = value.split()
                while words and words[-1].lower() in stop_words:
                    words.pop()
                return " ".join(words) if words else None
        return None

    @staticmethod
    def _extract_panti_keyword(message: str) -> str | None:
        named_match = re.search(
            r"(?:panti(?: asuhan)?\s+bernama|nama panti)\s+(.+?)(?:\?|$)",
            message,
            re.I,
        )
        if named_match:
            return named_match.group(1).strip(" .,!?")[:80]

        simple_match = re.search(
            r"(?:panti(?: asuhan)?)\s+([A-Za-z][A-Za-z0-9 .'-]{2,80})\s*$",
            message,
            re.I,
        )
        if simple_match:
            value = simple_match.group(1).strip(" .,!?")
            if not value.lower().startswith(("di ", "di")):
                return value
        return None

    def route(
        self,
        intent: Intent,
        message: str,
        entities: dict,
        db: Session,
    ) -> AgentResult:
        if intent is Intent.ABOUT:
            return AgentResult(
                "HaloKids adalah sistem informasi pelindungan anak dan panti asuhan milik Dinas Sosial. Lewat portal ini kamu dapat melapor kasus kekerasan atau eksploitasi anak (boleh anonim), mengajukan adopsi resmi (COTA), melihat direktori panti, berdonasi, dan mendaftar sebagai relawan.",
                intent,
                ["mendeteksi pertanyaan tentang HaloKids", "menampilkan ringkasan layanan"],
                {"layanan": ["pengaduan", "adopsi/COTA", "direktori panti", "donasi", "relawan"]},
            )

        if intent is Intent.GREETING:
            return AgentResult(
                "Halo! Saya HaloKids AI. Saya bisa membantu menjelaskan layanan pengaduan, adopsi/COTA, direktori panti, donasi, relawan, serta cara melacak tiket laporan. Apa yang ingin kamu ketahui?",
                intent,
                ["mendeteksi sapaan", "menampilkan kemampuan agen"],
            )

        if intent is Intent.HELP:
            return AgentResult(
                "Saya bisa membantu: (1) menjelaskan cara melapor, (2) melacak status tiket, (3) menjelaskan proses dan kelayakan awal adopsi, (4) mencari informasi panti, (5) menjelaskan donasi dan relawan, serta (6) menjelaskan privasi pelapor.",
                intent,
                ["mendeteksi permintaan bantuan", "menampilkan daftar layanan"],
            )

        if intent is Intent.EMERGENCY:
            return AgentResult(
                "Jika anak sedang dalam bahaya atau membutuhkan pertolongan segera, hubungi SAPA 129 (layanan pengaduan kekerasan terhadap anak) atau nomor darurat 112, dan gunakan tombol Lapor Kilat di portal. Jika ada yang terluka, utamakan keselamatan dan minta bantuan petugas atau tenaga medis terdekat. Setelah situasi aman, kamu juga dapat membuat laporan di portal (boleh anonim) agar Dinas Sosial dapat menindaklanjuti. Saya hanya memberi informasi dan tidak menggantikan petugas darurat.",
                intent,
                ["mendeteksi konteks darurat", "mengarahkan ke jalur bantuan cepat"],
                {"hotline": "SAPA 129", "nomor_darurat": "112", "action": "Lapor Kilat"},
            )

        if intent is Intent.TRACK_REPORT:
            return self._track_report(entities["ticket"], db)

        if intent is Intent.ELIGIBILITY:
            return self._eligibility(entities["dates"])

        if intent is Intent.DOCUMENTS:
            return AgentResult(
                "Untuk tahap awal pengajuan COTA pada web HaloKids, siapkan KTP, KK, akta kelahiran, buku nikah, SKCK, dan surat sehat. Dokumen tambahan dapat diminta atau dilengkapi pada tahap berikutnya. Keputusan akhir pengangkatan anak tetap melalui proses verifikasi manusia/Admin Dinsos.",
                intent,
                ["mendeteksi pertanyaan dokumen", "mengambil daftar dokumen tahap awal"],
                {
                    "dokumen_awal": [
                        "KTP",
                        "KK",
                        "Akta kelahiran",
                        "Buku nikah",
                        "SKCK",
                        "Surat sehat",
                    ]
                },
            )

        if intent is Intent.ADOPTION:
            return AgentResult(
                "Alur awal adopsi di HaloKids: buat akun masyarakat → isi data pemohon → cek kelayakan awal → unggah dokumen yang diminta → kirim pengajuan → dokumen dibantu dianalisis sistem → Admin Dinsos melakukan verifikasi dan menentukan status pengajuan.",
                intent,
                ["mendeteksi topik adopsi", "menyusun alur proses adopsi"],
                {"catatan": "AI adalah alat bantu; keputusan final tetap pada Admin Dinsos."},
            )

        if intent is Intent.REPORT:
            return AgentResult(
                "Pengaduan dapat dikirim melalui portal dan dapat dilakukan secara anonim. Setelah laporan tersimpan, sistem memberikan kode tiket untuk pelacakan. Laporan yang terkait akun login dapat menerima notifikasi ketika status berubah.",
                intent,
                ["mendeteksi topik pengaduan", "menjelaskan alur tiket"],
                {
                    "jenis": ["kekerasan", "eksploitasi", "panti ilegal", "lainnya"],
                    "status": ["baru", "diproses", "selesai"],
                },
            )

        if intent is Intent.DONATION:
            return self._donation_info(db)

        if intent is Intent.PANTI:
            return self._search_panti(db, entities["wilayah"], entities["panti_keyword"])

        if intent is Intent.VOLUNTEER:
            return AgentResult(
                "Untuk menjadi relawan, pengguna masyarakat mendaftar melalui portal dan mengunggah dokumen identitas. Pendaftaran kemudian menunggu verifikasi Admin Dinsos sebelum statusnya berubah menjadi disetujui atau ditolak.",
                intent,
                ["mendeteksi topik relawan", "menjelaskan proses pendaftaran relawan"],
                {"status": ["menunggu", "disetujui", "ditolak"]},
            )

        if intent is Intent.STATISTICS:
            return self._statistics(db)

        if intent is Intent.PRIVACY:
            return AgentResult(
                "HaloKids menyediakan alur pengaduan yang dapat dilakukan tanpa login. Untuk laporan yang dibuat anonim, sistem menyimpan id_user sebagai kosong dan pelapor menggunakan kode tiket untuk melacak status. Jangan kirim NIK, foto KTP, KK, password, atau data sangat sensitif melalui chatbot.",
                intent,
                ["mendeteksi pertanyaan privasi", "menjelaskan batas data chatbot"],
            )

        return AgentResult(
            "Saya belum memahami pertanyaan itu. Coba tanyakan tentang pengaduan, lacak tiket, adopsi/COTA, dokumen, direktori panti, donasi, relawan, atau privasi pelapor.",
            Intent.UNKNOWN,
            ["mendeteksi intent tidak dikenal", "memberikan opsi topik yang didukung"],
        )

    def _eligibility(self, dates: list[date]) -> AgentResult:
        if len(dates) < 2:
            return AgentResult(
                "Saya bisa membantu menghitung kelayakan awal berdasarkan tanggal lahir pemohon dan tanggal pernikahan. Kirim dua tanggal, misalnya: `15/05/1985 dan 20/08/2019`. Jangan kirim NIK atau dokumen pribadi ke chatbot.",
                Intent.ELIGIBILITY,
                ["mendeteksi permintaan cek kelayakan", "menunggu dua tanggal yang dibutuhkan"],
            )

        result = check_adoption_eligibility(
            birth_date=dates[0],
            marriage_date=dates[1],
        )
        if result["eligible"]:
            message = (
                f"Hasil filter kelayakan awal: memenuhi. Usia pemohon {result['usia_pemohon']} tahun "
                f"dan lama pernikahan {result['lama_pernikahan_tahun']} tahun {result['lama_pernikahan_bulan']} bulan. "
                "Ini hanya filter awal, bukan persetujuan adopsi."
            )
        else:
            errors = "; ".join(result["errors"]) or "belum memenuhi filter awal"
            message = (
                f"Hasil filter kelayakan awal: belum memenuhi. Usia pemohon {result['usia_pemohon']} tahun "
                f"dan lama pernikahan {result['lama_pernikahan_tahun']} tahun {result['lama_pernikahan_bulan']} bulan. "
                f"Catatan: {errors}"
            )
        return AgentResult(
            message,
            Intent.ELIGIBILITY,
            ["mengekstrak dua tanggal", "memanggil tool kelayakan adopsi", "menyusun hasil terstruktur"],
            result,
        )

    @staticmethod
    def _track_report(ticket: str | None, db: Session) -> AgentResult:
        if not ticket:
            return AgentResult(
                "Kirim kode tiket laporan, misalnya `HK-20261004-ABC12345`, agar saya bisa mengecek statusnya.",
                Intent.TRACK_REPORT,
                ["mendeteksi kebutuhan pelacakan tiket", "menunggu kode tiket"],
            )

        report = (
            db.query(LaporanPengaduan)
            .filter(LaporanPengaduan.kode_tiket == ticket)
            .first()
        )
        if report is None:
            return AgentResult(
                "Kode tiket tidak ditemukan. Pastikan kode tiket diketik sesuai yang diberikan sistem.",
                Intent.TRACK_REPORT,
                ["mencari tiket di database", "menghasilkan status tidak ditemukan"],
                {"kode_tiket": ticket, "ditemukan": False},
            )

        status_label = {
            "baru": "baru",
            "diproses": "sedang diproses",
            "selesai": "selesai",
        }.get(report.status, report.status)
        return AgentResult(
            f"Tiket {report.kode_tiket} ditemukan. Status laporan saat ini: **{status_label}**.",
            Intent.TRACK_REPORT,
            ["mencari tiket di database", "mengambil status laporan", "tidak menampilkan isi laporan"],
            {"kode_tiket": report.kode_tiket, "status": report.status, "tanggal_lapor": report.tanggal_lapor},
        )

    @staticmethod
    def _search_panti(
        db: Session,
        wilayah: str | None,
        panti_keyword: str | None,
    ) -> AgentResult:
        query = db.query(PantiAsuhan)
        filters = []
        if wilayah:
            filters.append(PantiAsuhan.alamat.ilike(f"%{wilayah}%"))
        if panti_keyword:
            filters.append(PantiAsuhan.nama_panti.ilike(f"%{panti_keyword}%"))
        for condition in filters:
            query = query.filter(condition)

        items = query.order_by(PantiAsuhan.id.desc()).limit(5).all()
        if not items:
            return AgentResult(
                "Belum ada data panti yang cocok dengan pencarian tersebut di database HaloKids.",
                Intent.PANTI,
                ["membangun filter direktori panti", "mencari panti pada database", "menghasilkan empty state"],
                {"jumlah": 0, "items": []},
            )

        data = [
            {
                "id": item.id,
                "nama_panti": item.nama_panti,
                "alamat": item.alamat,
                "kontak": item.kontak,
                "status_akreditasi": item.status_akreditasi,
                "jumlah_anak_asuh": item.jumlah_anak_asuh,
            }
            for item in items
        ]
        joined = "; ".join(
            f"{item['nama_panti']} ({item['alamat']})"
            for item in data
        )
        message = f"Saya menemukan {len(items)} data panti yang cocok: {joined}."
        return AgentResult(
            message,
            Intent.PANTI,
            ["mengekstrak filter wilayah/nama", "query direktori panti", "memformat hasil database"],
            {"jumlah": len(data), "items": data},
        )

    @staticmethod
    def _donation_info(db: Session) -> AgentResult:
        panti_count = db.query(PantiAsuhan).count()
        return AgentResult(
            "HaloKids mendukung donasi uang dan barang. Untuk donasi uang, bukti transfer diperlukan agar dapat diverifikasi. Untuk donasi barang, pengguna memilih/menuliskan barang, jumlah dan satuannya, serta estimasi waktu antar. Jika barang berasal dari wishlist panti, backend juga dapat mencatat keterkaitan dengan kebutuhan tersebut. Status donasi dapat dipantau melalui riwayat akun setelah login.",
            Intent.DONATION,
            ["mendeteksi topik donasi", "mengambil informasi aturan donasi", "menghitung jumlah panti untuk konteks"],
            {"jumlah_panti_terdaftar": panti_count, "jenis_donasi": ["uang", "barang"]},
        )

    @staticmethod
    def _statistics(db: Session) -> AgentResult:
        stats = get_public_statistics(db)
        return AgentResult(
            "Berikut statistik HaloKids yang dapat dihitung langsung dari database. Angka ini adalah data tercatat di sistem, bukan klaim statistik nasional.",
            Intent.STATISTICS,
            [
                "mengambil statistik publik dari database",
                "menghitung status akreditasi panti",
                "menghitung pengaduan yang ditangani",
                "menghitung donasi uang terverifikasi",
            ],
            stats,
        )


AGENT = HaloKidsPublicAgent()
