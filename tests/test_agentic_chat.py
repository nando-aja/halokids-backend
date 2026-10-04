import os
from datetime import date

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.database import Base
from app.db.models.donation import Donasi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.user import User
from app.services.agentic_chat import HaloKidsPublicAgent, Intent


def make_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


def test_classify_ticket_and_topics():
    agent = HaloKidsPublicAgent()
    assert agent.classify("cek tiket HK-20261004-ABC12345") is Intent.TRACK_REPORT
    assert agent.classify("apa syarat dokumen cota") is Intent.DOCUMENTS
    assert agent.classify("saya mau donasi") is Intent.DONATION


def test_extract_dates_and_eligibility():
    agent = HaloKidsPublicAgent()
    dates = agent.extract_entities("Lahir 15/05/1985 dan menikah 20/08/2019")['dates']
    assert dates == [date(1985, 5, 15), date(2019, 8, 20)]


def test_panti_tool_reads_database():
    db = make_db()
    db.add(PantiAsuhan(
        nama_panti="Panti Harapan",
        alamat="Surabaya",
        kontak="08123456789",
        status_akreditasi="Terakreditasi",
        jumlah_anak_asuh=20,
    ))
    db.commit()

    agent = HaloKidsPublicAgent()
    sid, result = agent.handle("cari panti di Surabaya", db)

    assert sid
    assert result.intent is Intent.PANTI
    assert result.data["jumlah"] == 1
    assert result.data["items"][0]["nama_panti"] == "Panti Harapan"


def test_ticket_tool_only_returns_status():
    db = make_db()
    db.add(LaporanPengaduan(
        id_user=None,
        kode_tiket="HK-20261004-ABC12345",
        isi_laporan="Contoh laporan yang cukup panjang untuk pengujian.",
        jenis_laporan="kekerasan",
        status="diproses",
    ))
    db.commit()

    agent = HaloKidsPublicAgent()
    _, result = agent.handle("cek HK-20261004-ABC12345", db)

    assert result.intent is Intent.TRACK_REPORT
    assert result.data["status"] == "diproses"
    assert "isi_laporan" not in result.data
