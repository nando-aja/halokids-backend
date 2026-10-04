from __future__ import annotations

import re
from decimal import Decimal
from difflib import SequenceMatcher
from pathlib import Path

from sqlalchemy.orm import Session

from app.db.models.adoption import PengajuanAdopsi
from app.services.storage import get_storage_absolute_path

try:
    import pymupdf as fitz
except ImportError:  # pragma: no cover
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from PIL import Image
except ImportError:  # pragma: no cover
    Image = None

try:
    import pytesseract
except ImportError:  # pragma: no cover
    pytesseract = None


def configure_tesseract() -> None:
    """Gunakan TESSERACT_CMD atau lokasi instalasi Windows yang umum."""
    if pytesseract is None:
        return

    import os

    configured = os.getenv("TESSERACT_CMD")
    if configured and Path(configured).is_file():
        pytesseract.pytesseract.tesseract_cmd = configured
        return

    candidates = [
        Path(os.environ.get("PROGRAMFILES", "C:/Program Files")) / "Tesseract-OCR" / "tesseract.exe",
        Path(os.environ.get("PROGRAMFILES(X86)", "C:/Program Files (x86)")) / "Tesseract-OCR" / "tesseract.exe",
    ]
    for candidate in candidates:
        if candidate.is_file():
            pytesseract.pytesseract.tesseract_cmd = str(candidate)
            return


configure_tesseract()


DATE_PATTERNS = [
    r"\b(\d{1,2})[\-/](\d{1,2})[\-/](\d{4})\b",
    r"\b(\d{4})[\-/](\d{1,2})[\-/](\d{1,2})\b",
]

NIK_PATTERN = re.compile(r"\b\d{16}\b")
PHONE_PATTERN = re.compile(r"\b(?:\+62|62|0)8\d{8,13}\b")

# Dokumen berupa foto (tidak berisi teks) tidak dianggap anomali bila OCR tidak
# menemukan teks, karena memang tidak ada teks yang diharapkan.
PHOTO_DOCUMENT_TYPES = {"pas_foto", "foto_rumah"}

# Daftar kelengkapan dokumen COTA menurut PRD (Modul B).
EXPECTED_INITIAL_DOCUMENTS = [
    "ktp",
    "kk",
    "akta_kelahiran",
    "buku_nikah",
    "skck",
    "surat_sehat",
]
EXPECTED_ADDITIONAL_DOCUMENTS = [
    "surat_kesehatan_jiwa",
    "fungsi_reproduksi",
    "surat_penghasilan",
    "pernyataan_resmi",
    "pas_foto",
    "foto_rumah",
]

# Label yang biasa muncul setelah kolom "Nama" pada KTP/KK hasil OCR.
NAME_STOP_LABELS = (
    "nik|tempat|tgl|tanggal|lahir|jenis|kelamin|gol|golongan|alamat|rt|rw|"
    "rt/rw|kel|desa|kecamatan|agama|status|perkawinan|pekerjaan|"
    "kewarganegaraan|berlaku|kota|provinsi"
)


DOCUMENT_CONTENT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "ktp": ("kartu tanda penduduk", "nik", "kewarganegaraan", "status perkawinan"),
    "kk": ("kartu keluarga", "kepala keluarga", "nomor kartu keluarga", "nik"),
    "akta_kelahiran": ("akta kelahiran", "kutipan akta kelahiran", "tempat lahir", "tanggal lahir"),
    "buku_nikah": ("buku nikah", "suami", "istri", "akad nikah", "kementerian agama"),
    "skck": ("surat keterangan catatan kepolisian", "skck", "kepolisian"),
    "surat_sehat": ("surat keterangan sehat", "surat sehat", "sehat jasmani", "sehat rohani", "bebas narkoba", "puskesmas", "rumah sakit"),
    "surat_kesehatan_jiwa": ("kesehatan jiwa", "sehat jiwa", "psikiater", "psikolog"),
    "fungsi_reproduksi": ("fungsi reproduksi", "reproduksi", "dokter"),
    "surat_penghasilan": ("penghasilan", "gaji", "pendapatan", "slip gaji"),
    "pernyataan_resmi": ("surat pernyataan", "pernyataan", "materai"),
}


class COTADocumentAgent:
    """Single-agent orchestrator untuk OCR, ekstraksi, matching, dan review manual."""

    name = "HaloKids Single-Agent Document Assistant"

    def run(
        self,
        document_paths: dict[str, str],
        db: Session | None = None,
        adoption: PengajuanAdopsi | None = None,
    ) -> dict:
        results: dict[str, dict] = {}
        anomalies: list[str] = []
        actions: list[str] = [
            "membaca berkas",
            "mengekstraksi teks",
            "menstrukturkan hasil ke JSON",
            "mencocokkan hasil dengan data pengajuan",
            "menentukan apakah perlu tinjauan manual",
        ]

        for document_type, relative_path in document_paths.items():
            try:
                absolute_path = get_storage_absolute_path(relative_path)
            except Exception:
                anomalies.append(
                    f"Path dokumen tidak valid: {document_type}"
                )
                continue

            if not absolute_path.is_file():
                anomalies.append(
                    f"File tidak ditemukan: {document_type}"
                )
                continue

            text, extraction_method, ocr_error = extract_text(absolute_path)
            structured = build_structured_result(
                text=text,
                file_path=relative_path,
                document_type=document_type,
                extraction_method=extraction_method,
            )

            content_validation = validate_document_content(
                document_type=document_type,
                text=text,
            )
            structured["content_validation"] = content_validation
            results[document_type] = structured

            if (
                not structured["text_found"]
                and document_type not in PHOTO_DOCUMENT_TYPES
            ):
                if ocr_error:
                    anomalies.append(
                        f"OCR/ekstraksi gagal pada dokumen {document_type}: {ocr_error}"
                    )
                else:
                    anomalies.append(
                        f"Teks tidak berhasil diekstraksi dari dokumen: {document_type}"
                    )

            if (
                document_type in DOCUMENT_CONTENT_KEYWORDS
                and document_type not in PHOTO_DOCUMENT_TYPES
                and not content_validation["matched"]
                and structured["text_found"]
            ):
                anomalies.append(
                    f"Isi dokumen {document_type} tidak cukup sesuai dengan karakteristik dokumen yang diharapkan."
                )

            if document_type == "ktp" and structured["nik_terdeteksi"] is None:
                anomalies.append(
                    "NIK 16 digit tidak terdeteksi pada dokumen KTP."
                )

        if adoption is not None:
            compare_result = self.match_with_database(
                results=results,
                adoption=adoption,
            )
            anomalies.extend(compare_result["anomalies"])
        else:
            compare_result = {
                "name_match": None,
                "birth_date_match": None,
                "anomalies": [],
            }

        return {
            "agent": self.name,
            "mode": "local_ocr_nlp",
            "documents_checked": len(document_paths),
            "steps": actions,
            "documents": results,
            "database_matching": compare_result,
            "kelengkapan_dokumen": self.check_completeness(document_paths),
            "anomalies": _unique(anomalies),
            "requires_manual_review": bool(anomalies),
        }

    @staticmethod
    def check_completeness(document_paths: dict[str, str]) -> dict:
        """
        Rekap kelengkapan dokumen COTA. Dokumen tambahan yang belum ada
        hanya menjadi informasi bagi admin (bukan anomali), karena pemohon
        dapat melengkapinya setelah pengajuan awal.
        """
        uploaded = {key for key, value in document_paths.items() if value}
        expected = EXPECTED_INITIAL_DOCUMENTS + EXPECTED_ADDITIONAL_DOCUMENTS
        return {
            "sudah_ada": [key for key in expected if key in uploaded],
            "belum_ada": [key for key in expected if key not in uploaded],
            "dokumen_awal_lengkap": all(
                key in uploaded for key in EXPECTED_INITIAL_DOCUMENTS
            ),
        }

    def match_with_database(
        self,
        results: dict[str, dict],
        adoption: PengajuanAdopsi,
    ) -> dict:
        anomalies: list[str] = []
        name_match: bool | None = None
        birth_date_match: bool | None = None

        ktp = results.get("ktp")
        if ktp:
            extracted_name = ktp.get("nama_terdeteksi")
            extracted_birth_date = ktp.get("tanggal_lahir_terdeteksi")

            if extracted_name:
                name_match = similar_text(
                    extracted_name,
                    adoption.nama_pemohon,
                ) >= 0.80
                if not name_match:
                    anomalies.append(
                        "Nama pada KTP tidak cukup cocok dengan nama pemohon."
                    )
            elif ktp.get("text_found"):
                anomalies.append(
                    "Nama pada KTP tidak terbaca oleh OCR; perlu dicek manual."
                )

            if extracted_birth_date:
                birth_date_match = extracted_birth_date == adoption.tanggal_lahir_pemohon.isoformat()
                if not birth_date_match:
                    anomalies.append(
                        "Tanggal lahir pada KTP tidak cocok dengan data pengajuan."
                    )

        return {
            "name_match": name_match,
            "birth_date_match": birth_date_match,
            "anomalies": anomalies,
        }


AGENT = COTADocumentAgent()


def extract_text(path: Path) -> tuple[str, str, str | None]:
    suffix = path.suffix.lower()

    if suffix == ".pdf":
        if fitz is None:
            return "", "unavailable", "PyMuPDF belum terpasang"

        try:
            with fitz.open(path) as document:
                text = "\n".join(
                    page.get_text("text")
                    for page in document
                ).strip()

                if text:
                    return text, "pdf_text", None

                if pytesseract is None or Image is None:
                    return "", "pdf_text_empty", "Tesseract/Pillow belum tersedia untuk OCR PDF scan"

                ocr_pages: list[str] = []
                for page in document:
                    pixmap = page.get_pixmap(
                        matrix=fitz.Matrix(2, 2),
                        alpha=False,
                    )
                    image = Image.frombytes(
                        "RGB",
                        [pixmap.width, pixmap.height],
                        pixmap.samples,
                    )
                    ocr_pages.append(
                        pytesseract.image_to_string(image)
                    )

                ocr_text = "\n".join(ocr_pages).strip()
                return ocr_text, "pdf_ocr", None
        except Exception as exc:
            return "", "pdf_error", str(exc)

    if suffix in {".jpg", ".jpeg", ".png"}:
        if pytesseract is None or Image is None:
            return "", "image_ocr_unavailable", "Tesseract/Pillow belum tersedia"

        try:
            text = pytesseract.image_to_string(
                Image.open(path)
            ).strip()
            return text, "image_ocr", None
        except Exception as exc:
            return "", "image_ocr_error", str(exc)

    return "", "unsupported", "Format file tidak didukung"


def build_structured_result(
    text: str,
    file_path: str,
    document_type: str = "dokumen",
    extraction_method: str = "unknown",
) -> dict:
    normalized = normalize_text(text)
    return {
        "document_type": document_type,
        "file": file_path,
        "extraction_method": extraction_method,
        "text_found": bool(normalized),
        "nama_terdeteksi": extract_name(normalized),
        "nik_terdeteksi": extract_nik(normalized),
        "tanggal_lahir_terdeteksi": extract_birth_date(normalized),
        "tanggal_terdeteksi": extract_dates(normalized),
        "nominal_terdeteksi": extract_money(normalized),
        "nomor_referensi_terdeteksi": extract_reference(normalized),
        "panjang_teks": len(normalized),
        "ringkasan_teks": normalized[:500],
    }


def validate_document_content(document_type: str, text: str) -> dict:
    """Validasi semantik ringan berbasis kata kunci; tidak menggantikan review manusia."""
    keywords = DOCUMENT_CONTENT_KEYWORDS.get(document_type)
    if not keywords:
        return {
            "matched": True,
            "expected_keywords": [],
            "matched_keywords": [],
            "message": "Tidak ada validator isi khusus untuk tipe dokumen ini.",
        }

    lowered = normalized_lower(text)
    matched_keywords = [keyword for keyword in keywords if keyword in lowered]
    # Threshold konservatif: satu atau dua istilah yang relevan sudah cukup untuk
    # melewati validator heuristik, tetapi hasil tetap ditampilkan sebagai alat bantu.
    minimum_hits = 1
    matched = len(matched_keywords) >= minimum_hits

    return {
        "matched": matched,
        "expected_keywords": list(keywords),
        "matched_keywords": matched_keywords,
        "message": (
            "Karakteristik teks cukup sesuai."
            if matched
            else "Karakteristik teks tidak cukup sesuai; arahkan ke review manual."
        ),
    }


def analyze_adoption_documents(
    document_paths: dict[str, str],
    db: Session | None = None,
    adoption: PengajuanAdopsi | None = None,
) -> dict:
    return AGENT.run(
        document_paths=document_paths,
        db=db,
        adoption=adoption,
    )


def parse_idr_amount(value: str | None) -> Decimal | None:
    """
    Mengubah teks nominal hasil OCR menjadi angka.
    Mendukung "500.000", "500.000,00", "500,000", dan "500,000.00".
    """
    if not value:
        return None

    cleaned = re.sub(r"[^0-9.,]", "", value).strip(".,")
    if not cleaned:
        return None

    has_dot = "." in cleaned
    has_comma = "," in cleaned

    if has_dot and has_comma:
        decimal_sep = "." if cleaned.rfind(".") > cleaned.rfind(",") else ","
        thousand_sep = "," if decimal_sep == "." else "."
        cleaned = cleaned.replace(thousand_sep, "").replace(decimal_sep, ".")
    elif has_dot or has_comma:
        sep = "." if has_dot else ","
        parts = cleaned.split(sep)
        if len(parts) > 2 or len(parts[-1]) == 3:
            cleaned = "".join(parts)
        else:
            cleaned = ".".join(parts)

    try:
        return Decimal(cleaned)
    except Exception:
        return None


def analyze_transfer_proof(
    file_path: str,
    expected_amount: Decimal | int | float | None = None,
) -> dict:
    absolute_path = get_storage_absolute_path(file_path)

    if not absolute_path.is_file():
        return {
            "agent": AGENT.name,
            "document_type": "bukti_transfer",
            "file": file_path,
            "requires_manual_review": True,
            "anomalies": ["File bukti transfer tidak ditemukan."],
        }

    text, method, error = extract_text(absolute_path)
    structured = build_structured_result(
        text=text,
        file_path=file_path,
        document_type="bukti_transfer",
        extraction_method=method,
    )

    anomalies: list[str] = []
    lower = normalized_lower(text)

    transfer_keywords = [
        "transfer",
        "berhasil",
        "success",
        "sukses",
        "dibayar",
        "payment",
    ]

    if not any(keyword in lower for keyword in transfer_keywords):
        anomalies.append(
            "Kata kunci transaksi transfer tidak cukup jelas pada bukti."
        )

    if not structured["text_found"]:
        anomalies.append(
            error or "Teks bukti transfer tidak berhasil diekstraksi."
        )

    nominal_match: bool | None = None
    detected_amount = parse_idr_amount(structured["nominal_terdeteksi"])

    if expected_amount is not None and structured["text_found"]:
        expected = Decimal(str(expected_amount))
        if detected_amount is None:
            anomalies.append(
                "Nominal pada bukti transfer tidak terbaca; "
                "tidak dapat dicocokkan dengan nominal donasi."
            )
        else:
            nominal_match = abs(detected_amount - expected) < Decimal("0.5")
            if not nominal_match:
                anomalies.append(
                    f"Nominal pada bukti transfer ({detected_amount:,.0f}) "
                    f"tidak sama dengan nominal donasi ({expected:,.0f})."
                )

    return {
        "agent": AGENT.name,
        "document_type": "bukti_transfer",
        "file": file_path,
        "steps": [
            "membaca bukti transfer",
            "OCR/ekstraksi teks",
            "ekstraksi nominal/tanggal/referensi",
            "mencocokkan nominal dengan data donasi (bila tersedia)",
            "cek anomali dasar",
            "bila anomali, serahkan ke verifikasi manual",
        ],
        "structured": structured,
        "nominal_terdeteksi_angka": (
            str(detected_amount) if detected_amount is not None else None
        ),
        "nominal_donasi_cocok": nominal_match,
        "anomalies": _unique(anomalies),
        "requires_manual_review": bool(anomalies),
    }


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def normalized_lower(text: str) -> str:
    return normalize_text(text).lower()


def extract_nik(text: str) -> str | None:
    compact = re.sub(r"[^0-9]", " ", text)
    match = NIK_PATTERN.search(compact)
    return match.group(0) if match else None


def extract_dates(text: str) -> list[str]:
    dates: list[str] = []

    for pattern in DATE_PATTERNS:
        for match in re.findall(pattern, text):
            if len(match[0]) == 4:
                year, month, day = map(int, match)
            else:
                day, month, year = map(int, match)

            if 1 <= month <= 12 and 1 <= day <= 31:
                dates.append(
                    f"{year:04d}-{month:02d}-{day:02d}"
                )

    return _unique(dates)[:10]


def extract_birth_date(text: str) -> str | None:
    patterns = [
        r"(?:tanggal lahir|tempat/tgl lahir|lahir)\s*[:\-]?\s*([^,;|]+)",
        r"(?:tgl\.\s*lahir)\s*[:\-]?\s*([^,;|]+)",
    ]

    candidates: list[str] = []
    for pattern in patterns:
        candidates.extend(re.findall(pattern, text, flags=re.I))

    for candidate in candidates:
        found = extract_dates(candidate)
        if found:
            return found[0]

    dates = extract_dates(text)
    return dates[0] if dates else None


def extract_name(text: str) -> str | None:
    """Ekstraksi nama yang toleran terhadap hasil OCR berformat label/non-label."""
    patterns = [
        (
            r"\b(?:nama lengkap|nama pemohon|nama)\s*[:\-]\s*"
            r"([A-Za-z][A-Za-z .'\-]{2,99}?)"
            rf"(?=\s+(?:{NAME_STOP_LABELS})\b|[^A-Za-z .'\-]|$)"
        ),
        (
            r"\b(?:nama lengkap|nama pemohon|nama)\s+"
            r"([A-Za-z][A-Za-z .'\-]{2,99}?)"
            rf"(?=\s+(?:{NAME_STOP_LABELS})\b|$)"
        ),
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            value = normalize_text(match.group(1)).strip(" -:;,")
            if value:
                return value[:100]

    return None


def extract_money(text: str) -> str | None:
    patterns = [
        r"(?:rp|idr)\s*([0-9][0-9\.,]*)",
        r"(?:nominal|jumlah|total)\s*[:\-]?\s*(?:rp|idr)?\s*([0-9][0-9\.,]*)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1)

    return None


def extract_reference(text: str) -> str | None:
    patterns = [
        r"(?:ref(?:erence)?|kode transaksi|no transaksi|transaction id)\s*[:\-]\s*([A-Za-z0-9\-_/]+)",
    ]

    for pattern in patterns:
        match = re.search(pattern, text, flags=re.I)
        if match:
            return match.group(1)

    phone = PHONE_PATTERN.search(text)
    return phone.group(0) if phone else None


def similar_text(left: str, right: str) -> float:
    left_normalized = " ".join(left.lower().split())
    right_normalized = " ".join(right.lower().split())
    return SequenceMatcher(
        None,
        left_normalized,
        right_normalized,
    ).ratio()


def _unique(values: list[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()

    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)

    return result
