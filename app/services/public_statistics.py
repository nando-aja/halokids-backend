from __future__ import annotations

from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models.adoption import PengajuanAdopsi
from app.db.models.donation import Donasi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.volunteer import Relawan


def get_public_statistics(db: Session) -> dict:
    total_panti = db.query(func.count(PantiAsuhan.id)).scalar() or 0
    total_adoptions = db.query(func.count(PengajuanAdopsi.id)).scalar() or 0
    accredited = (
        db.query(func.count(PantiAsuhan.id))
        .filter(
            PantiAsuhan.status_akreditasi.isnot(None),
            PantiAsuhan.status_akreditasi != "",
        )
        .scalar()
        or 0
    )

    total_reports = db.query(func.count(LaporanPengaduan.id)).scalar() or 0
    handled_reports = (
        db.query(func.count(LaporanPengaduan.id))
        .filter(LaporanPengaduan.status.in_(["diproses", "selesai"]))
        .scalar()
        or 0
    )

    total_donations = db.query(func.count(Donasi.id)).scalar() or 0
    total_volunteers = db.query(func.count(Relawan.id)).scalar() or 0
    total_money = (
        db.query(func.coalesce(func.sum(Donasi.jumlah_nominal), 0))
        .filter(
            Donasi.jenis_donasi == "uang",
            Donasi.status_verifikasi == "terverifikasi",
        )
        .scalar()
        or 0
    )

    children = (
        db.query(func.coalesce(func.sum(PantiAsuhan.jumlah_anak_asuh), 0))
        .scalar()
        or 0
    )

    percentage = round((accredited / total_panti) * 100, 2) if total_panti else 0.0

    return {
        "total_panti": int(total_panti),
        "total_adopsi": int(total_adoptions),
        "total_relawan": int(total_volunteers),
        "panti_dengan_status_akreditasi": int(accredited),
        "persentase_panti_dengan_status_akreditasi": percentage,
        "total_pengaduan": int(total_reports),
        "kasus_pengaduan_ditangani": int(handled_reports),
        "total_donasi": int(total_donations),
        "total_nominal_donasi_uang": str(Decimal(str(total_money))),
        "total_anak_asuh_tercatat": int(children),
        "anak_dalam_rehabilitasi": None,
        "rata_rata_respons_jam": None,
        "catatan": [
            "Total adopsi menghitung seluruh pengajuan adopsi, termasuk yang masih diproses atau ditolak.",
            "Persentase dihitung dari panti yang memiliki status akreditasi pada database.",
            "Kasus ditangani berarti status pengaduan diproses atau selesai.",
            "Nominal donasi hanya menjumlahkan donasi uang yang sudah terverifikasi.",
            "Data anak dalam rehabilitasi dan rata-rata waktu respons belum tersedia pada schema inti.",
        ],
    }
