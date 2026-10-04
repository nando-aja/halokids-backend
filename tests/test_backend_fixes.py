import io
import os
from decimal import Decimal
from pathlib import Path

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

import pytest
from fastapi.testclient import TestClient
from PIL import Image, ImageDraw, ImageFont
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import hash_password
from app.db.database import Base
from app.db import models  # noqa: F401
from app.db.models.panti import PantiAsuhan
from app.db.models.user import User
from app.main import app
from app.services import ai_service, visit_calendar
from app.services.agentic_chat import HaloKidsPublicAgent, Intent


# ---------- unit: ekstraksi OCR ----------

def test_extract_name_stops_at_next_label():
    text = "NIK : 3578011505850001 Nama : Budi Santoso Tgl Lahir : 15-05-1985"
    assert ai_service.extract_name(text) == "Budi Santoso"
    assert ai_service.extract_name("Nama : BUDI SANTOSO Tempat/Tgl Lahir : Surabaya") == "BUDI SANTOSO"
    assert ai_service.extract_name("Nama : Budi Santoso") == "Budi Santoso"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("500.000", Decimal("500000")),
        ("500.000,00", Decimal("500000.00")),
        ("500,000", Decimal("500000")),
        ("500,000.00", Decimal("500000.00")),
        ("1.250.000", Decimal("1250000")),
        (None, None),
    ],
)
def test_parse_idr_amount(raw, expected):
    assert ai_service.parse_idr_amount(raw) == expected


def test_completeness_report_lists_missing_documents():
    result = ai_service.COTADocumentAgent.check_completeness(
        {"ktp": "a", "kk": "b", "akta_kelahiran": "c", "buku_nikah": "d", "skck": "e", "surat_sehat": "f"}
    )
    assert result["dokumen_awal_lengkap"] is True
    assert "pas_foto" in result["belum_ada"]
    assert "surat_penghasilan" in result["belum_ada"]


# ---------- unit: chatbot ----------

@pytest.fixture()
def agent():
    return HaloKidsPublicAgent()


@pytest.mark.parametrize(
    "message",
    [
        "saya melihat anak dipukuli sekarang",
        "tetangga menganiaya anaknya, anak itu dianiaya",
        "ada anak diperkosa tolong",
        "anak itu diculik",
    ],
)
def test_violence_messages_route_to_emergency(agent, message):
    assert agent.classify(message) is Intent.EMERGENCY


def test_halokids_is_not_a_greeting(agent):
    assert agent.classify("apa itu halokids") is Intent.ABOUT
    assert agent.classify("halo") is Intent.GREETING
    assert agent.classify("hai") is Intent.GREETING


def test_follow_up_uses_session_context(agent):
    db = _memory_db()
    sid, first = agent.handle("bagaimana proses adopsi?", db)
    assert first.intent is Intent.ADOPTION

    _, follow = agent.handle("tolong ceritakan lebih lanjut", db, sid)
    assert follow.intent is Intent.ADOPTION
    assert follow.actions[0] == "memakai konteks percakapan sebelumnya"

    _, no_context = agent.handle("tolong ceritakan lebih lanjut", db)
    assert no_context.intent is Intent.UNKNOWN


def test_unrelated_question_stays_unknown(agent):
    assert agent.classify("siapa presiden indonesia") is Intent.UNKNOWN


def _memory_db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


# ---------- integrasi API ----------

@pytest.fixture()
def client(tmp_path, monkeypatch):
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)

    def override_db():
        db = Session()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    monkeypatch.setattr(visit_calendar, "CALENDAR_FILE", tmp_path / "kalender.json")

    db = Session()
    db.add_all(
        [
            User(nama="Admin", email="admin@x.com", password_hash=hash_password("Admin12345"), peran="admin"),
            User(nama="Pengelola", email="pengelola@x.com", password_hash=hash_password("Panti12345"), peran="pengelola-panti"),
            User(nama="Donatur", email="donatur@x.com", password_hash=hash_password("Donor12345"), peran="masyarakat"),
        ]
    )
    db.commit()
    pengelola = db.query(User).filter(User.email == "pengelola@x.com").first()
    db.add(PantiAsuhan(nama_panti="Panti Harapan", alamat="Surabaya", id_admin_pengelola=pengelola.id))
    db.commit()
    db.close()

    # Bersihkan file unggahan yang dibuat selama test agar storage tetap bersih.
    before = {path for path in Path("storage").rglob("*") if path.is_file()}

    yield TestClient(app)

    app.dependency_overrides.clear()
    for path in Path("storage").rglob("*"):
        if path.is_file() and path not in before:
            path.unlink(missing_ok=True)


def login(client, email, password):
    response = client.post("/api/auth/login", data={"username": email, "password": password})
    assert response.status_code == 200
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def make_png(lines):
    image = Image.new("RGB", (1200, 500), "white")
    draw = ImageDraw.Draw(image)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 34)
    for index, line in enumerate(lines):
        draw.text((30, 30 + index * 60), line, fill="black", font=font)
    buffer = io.BytesIO()
    image.save(buffer, "PNG")
    buffer.seek(0)
    return buffer


def test_visit_calendar_admin_crud_and_public_read(client):
    admin = login(client, "admin@x.com", "Admin12345")

    created = client.post(
        "/api/admin/kalender-kunjungan",
        headers=admin,
        json={"id_panti": 1, "judul": "Open House Panti Harapan", "tanggal": "2099-01-15", "jam_mulai": "09:00"},
    )
    assert created.status_code == 201
    event_id = created.json()["id"]

    public = client.get("/api/public/kalender-kunjungan", params={"hanya_mendatang": True})
    assert public.status_code == 200
    assert [item["judul"] for item in public.json()] == ["Open House Panti Harapan"]

    updated = client.put(f"/api/admin/kalender-kunjungan/{event_id}", headers=admin, json={"lokasi": "Aula panti"})
    assert updated.status_code == 200 and updated.json()["lokasi"] == "Aula panti"

    assert client.post(
        "/api/admin/kalender-kunjungan", headers=admin,
        json={"id_panti": 999, "judul": "Panti tidak ada", "tanggal": "2099-01-15"},
    ).status_code == 404

    assert client.delete(f"/api/admin/kalender-kunjungan/{event_id}", headers=admin).status_code == 200
    assert client.get("/api/public/kalender-kunjungan").json() == []


def test_calendar_requires_admin(client):
    donor = login(client, "donatur@x.com", "Donor12345")
    body = {"judul": "Tidak boleh", "tanggal": "2099-01-15"}
    assert client.post("/api/admin/kalender-kunjungan", json=body).status_code == 401
    assert client.post("/api/admin/kalender-kunjungan", headers=donor, json=body).status_code == 403


def test_private_folders_are_not_public(client):
    assert client.get("/api/public/files/ktp/apa-saja.png").status_code == 404
    assert client.get("/api/public/files/bukti_transfer/apa-saja.png").status_code == 404
    assert client.get("/api/public/files/laporan_dana/..%2F..%2F.env").status_code in (400, 404)


def test_supervision_report_listed_per_panti(client):
    admin = login(client, "admin@x.com", "Admin12345")
    upload = client.post(
        "/api/admin/panti/1/laporan-pengawasan",
        headers=admin,
        files={"file": ("laporan.png", make_png(["Laporan pengawasan"]), "image/png")},
    )
    assert upload.status_code == 200
    stored_path = upload.json()["file_laporan"]

    listing = client.get("/api/public/panti/1/laporan-pengawasan")
    assert listing.status_code == 200
    assert [item["file"] for item in listing.json()] == [stored_path]

    filename = stored_path.split("/")[-1]
    download = client.get(f"/api/public/files/laporan_pengawasan/{filename}")
    assert download.status_code == 200

    # file milik panti lain tidak muncul
    assert client.get("/api/public/panti/2/laporan-pengawasan").status_code == 404
    os.remove(stored_path)


def test_donation_flow_amount_check_files_and_notifications(client):
    donor = login(client, "donatur@x.com", "Donor12345")
    pengelola = login(client, "pengelola@x.com", "Panti12345")
    admin = login(client, "admin@x.com", "Admin12345")

    proof = client.post(
        "/api/upload/bukti-transfer",
        headers=donor,
        files={"file": ("bukti.png", make_png(["Transfer BERHASIL", "Rp 500.000", "Ref: TRX12345"]), "image/png")},
    )
    assert proof.status_code == 200
    proof_path = proof.json()["bukti_transfer"]

    # nominal donasi cocok dengan bukti
    ok = client.post(
        "/api/masyarakat/donasi", headers=donor,
        json={"id_panti": 1, "jenis_donasi": "uang", "jumlah_nominal": "500000", "bukti_transfer": proof_path},
    )
    assert ok.status_code == 201
    ok_id = ok.json()["id"]

    # nominal donasi berbeda dari bukti -> pengelola diberi tanda cek manual
    mismatch = client.post(
        "/api/masyarakat/donasi", headers=donor,
        json={"id_panti": 1, "jenis_donasi": "uang", "jumlah_nominal": "900000", "bukti_transfer": proof_path},
    )
    assert mismatch.status_code == 201
    mismatch_id = mismatch.json()["id"]

    notifications = client.get("/api/panti/notifikasi", headers=pengelola)
    assert notifications.status_code == 200
    messages = [item["pesan"] for item in notifications.json()]
    assert any("dicek manual" in message for message in messages)
    assert any("dicek manual" not in message for message in messages)

    ai_ok = client.post(f"/api/panti/donasi/{ok_id}/analisis-bukti-ai", headers=pengelola).json()
    assert ai_ok["nominal_donasi_cocok"] is True and ai_ok["requires_manual_review"] is False

    ai_bad = client.post(f"/api/admin/donasi/{mismatch_id}/analisis-bukti-ai", headers=admin).json()
    assert ai_bad["nominal_donasi_cocok"] is False
    assert ai_bad["requires_manual_review"] is True

    # pengelola & admin dapat membuka bukti, donatur lain / publik tidak
    assert client.get(f"/api/panti/donasi/{ok_id}/bukti", headers=pengelola).status_code == 200
    assert client.get("/api/admin/files", headers=admin, params={"path": proof_path}).status_code == 200
    assert client.get("/api/admin/files", headers=admin, params={"path": "../.env"}).status_code == 400
    assert client.get("/api/admin/files", params={"path": proof_path}).status_code == 401
    assert client.get("/api/admin/files", headers=donor, params={"path": proof_path}).status_code == 403

    # notifikasi pengelola bisa ditandai dibaca
    first_id = notifications.json()[0]["id"]
    assert client.patch(f"/api/panti/notifikasi/{first_id}/read", headers=pengelola).json()["is_read"] is True
    assert client.patch("/api/panti/notifikasi/read-all", headers=pengelola).json()["diperbarui"] >= 1
    assert client.patch("/api/panti/notifikasi/999999/read", headers=pengelola).status_code == 404

    os.remove(proof_path)


def test_donation_rejects_other_private_files_as_proof(client):
    donor = login(client, "donatur@x.com", "Donor12345")
    ktp = client.post(
        "/api/upload/ktp-adopsi", headers=donor,
        files={
            "ktp": ("k.png", make_png(["Nama : Budi"]), "image/png"),
            "kk": ("kk.png", make_png(["KK"]), "image/png"),
        },
    ).json()

    response = client.post(
        "/api/masyarakat/donasi", headers=donor,
        json={"id_panti": 1, "jenis_donasi": "uang", "jumlah_nominal": "100000", "bukti_transfer": ktp["dokumen_ktp"]},
    )
    assert response.status_code == 422

    for path in (ktp["dokumen_ktp"], ktp["dokumen_kk"]):
        os.remove(path)


def test_adoption_with_correct_data_no_false_name_anomaly_and_photos_not_flagged(client):
    donor = login(client, "donatur@x.com", "Donor12345")
    ktp = client.post(
        "/api/upload/ktp-adopsi", headers=donor,
        files={
            "ktp": ("k.png", make_png(["NIK : 3578011505850001", "Nama : Budi Santoso", "Tgl Lahir : 15-05-1985"]), "image/png"),
            "kk": ("kk.png", make_png(["KARTU KELUARGA"]), "image/png"),
        },
    ).json()
    awal = client.post(
        "/api/upload/dokumen-awal-adopsi", headers=donor,
        files={name: (name + ".png", make_png([name.replace("_", " ")]), "image/png")
               for name in ["akta_kelahiran", "buku_nikah", "skck", "surat_sehat"]},
    ).json()

    photo = Image.new("RGB", (400, 400), (200, 150, 100))
    buffer = io.BytesIO()
    photo.save(buffer, "PNG")
    buffer.seek(0)
    foto = client.post(
        "/api/upload/dokumen-tambahan-adopsi", headers=donor,
        params={"jenis_dokumen": "pas_foto"},
        files={"file": ("foto.png", buffer, "image/png")},
    ).json()

    docs = dict(awal["dokumen_pendukung"])
    docs["pas_foto"] = foto["file"]

    response = client.post(
        "/api/masyarakat/pengajuan-adopsi", headers=donor,
        json={
            "nama_pemohon": "Budi Santoso",
            "tanggal_lahir_pemohon": "1985-05-15",
            "tanggal_pernikahan": "2015-08-20",
            "dokumen_ktp": ktp["dokumen_ktp"],
            "dokumen_kk": ktp["dokumen_kk"],
            "dokumen_pendukung": docs,
        },
    )
    assert response.status_code == 201, response.text
    body = response.json()
    result = body["hasil_ekstraksi_ai"]

    assert result["database_matching"]["name_match"] is True
    assert result["anomalies"] == []
    assert body["status"] == "diajukan"
    assert "surat_penghasilan" in result["kelengkapan_dokumen"]["belum_ada"]
    assert "pas_foto" in result["kelengkapan_dokumen"]["sudah_ada"]

    for path in [ktp["dokumen_ktp"], ktp["dokumen_kk"], foto["file"], *awal["dokumen_pendukung"].values()]:
        os.remove(path)


def test_admin_notifications_can_be_marked_read(client):
    admin = login(client, "admin@x.com", "Admin12345")
    client.post("/api/public/pengaduan", json={"isi_laporan": "Ada dugaan panti ilegal di dekat rumah.", "jenis_laporan": "panti_ilegal"})

    notifications = client.get("/api/admin/notifikasi", headers=admin).json()
    assert len(notifications) == 1 and notifications[0]["is_read"] is False

    read = client.patch(f"/api/admin/notifikasi/{notifications[0]['id']}/read", headers=admin)
    assert read.status_code == 200 and read.json()["is_read"] is True
    assert client.patch("/api/admin/notifikasi/read-all", headers=admin).json()["diperbarui"] == 0
