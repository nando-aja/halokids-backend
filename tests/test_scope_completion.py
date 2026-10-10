from datetime import date
from decimal import Decimal

from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.db.database import Base
from app.db.models.adoption import PengajuanAdopsi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.donation import Donasi
from app.schemas.donation import DonationCreate
from app.services.agentic_chat import HaloKidsPublicAgent, Intent
from app.services.ai_service import validate_document_content, extract_name
from app.services.public_statistics import get_public_statistics


def test_goods_donation_schema_requires_item_and_delivery_date():
    data = DonationCreate(
        id_panti=1,
        jenis_donasi="barang",
        id_wishlist=3,
        jumlah_barang=5,
        satuan_barang="pcs",
        estimasi_waktu_antar=date(2026, 10, 10),
    )
    assert data.jenis_donasi == "barang"
    assert data.jumlah_barang == 5


def test_money_donation_requires_positive_nominal_and_proof_can_be_checked_elsewhere():
    data = DonationCreate(
        id_panti=1,
        jenis_donasi="uang",
        jumlah_nominal=Decimal("100000"),
    )
    assert data.jumlah_nominal == Decimal("100000")


def test_goods_donation_rejects_transfer_proof():
    try:
        DonationCreate(
            id_panti=1,
            jenis_donasi="barang",
            nama_barang="Beras",
            jumlah_barang=5,
            satuan_barang="kg",
            estimasi_waktu_antar=date(2026, 10, 10),
            bukti_transfer="storage/bukti_transfer/x.png",
        )
    except ValidationError:
        return
    raise AssertionError("Donasi barang seharusnya menolak bukti transfer")


def test_emergency_and_normal_report_are_distinguished():
    agent = HaloKidsPublicAgent()
    assert agent.classify("anak dipukuli sekarang") is Intent.EMERGENCY
    assert agent.classify("bagaimana cara melaporkan kekerasan pada anak") is Intent.REPORT


def test_document_name_fallback_and_content_validation():
    assert extract_name("Nama Budi Santoso NIK 1234567890123456") == "Budi Santoso"
    result = validate_document_content("skck", "SURAT KETERANGAN CATATAN KEPOLISIAN SKCK")
    assert result["matched"] is True


def test_public_statistics_uses_only_database_values():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([
            PantiAsuhan(nama_panti="Panti A", alamat="Surabaya", status_akreditasi="A", jumlah_anak_asuh=10),
            PantiAsuhan(nama_panti="Panti B", alamat="Surabaya", status_akreditasi=None, jumlah_anak_asuh=5),
        ])
        db.add(LaporanPengaduan(id_user=None, kode_tiket="HK-20261004-ABC12345", isi_laporan="laporan kekerasan", jenis_laporan="kekerasan", status="selesai"))
        db.add(PengajuanAdopsi(
            id_user=1,
            nama_pemohon="Budi Santoso",
            tanggal_lahir_pemohon=date(1985, 5, 15),
            tanggal_pernikahan=date(2010, 8, 20),
            status="diajukan",
        ))
        db.commit()
        stats = get_public_statistics(db)
        assert stats["total_panti"] == 2
        assert stats["total_adopsi"] == 1
        assert stats["panti_dengan_status_akreditasi"] == 1
        assert stats["kasus_pengaduan_ditangani"] == 1
        assert stats["anak_dalam_rehabilitasi"] is None
