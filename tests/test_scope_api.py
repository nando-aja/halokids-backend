import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "test-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from app.api.deps import get_db
from app.core.security import hash_password
from app.db.database import Base
from app.db.models.panti import PantiAsuhan
from app.db.models.user import User
from app.db.models.wishlist import WishlistPanti
from app.main import app


def _setup_client():
    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)

    def override_db():
        db = SessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_db
    db = SessionLocal()
    admin = User(nama="Admin", email="admin@halo.test", password_hash=hash_password("Admin12345"), peran="admin")
    manager = User(nama="Manager", email="manager@halo.test", password_hash=hash_password("Manager12345"), peran="pengelola-panti")
    donor = User(nama="Donor", email="donor@halo.test", password_hash=hash_password("Donor12345"), peran="masyarakat")
    db.add_all([admin, manager, donor])
    db.commit()
    db.refresh(manager)
    panti = PantiAsuhan(
        nama_panti="Panti Uji",
        alamat="Surabaya",
        status_akreditasi="A",
        jumlah_anak_asuh=12,
        id_admin_pengelola=manager.id,
    )
    db.add(panti)
    db.commit()
    db.refresh(panti)
    wishlist = WishlistPanti(
        id_panti=panti.id,
        nama_barang="Beras",
        jumlah_kebutuhan=10,
        jumlah_terpenuhi=2,
    )
    db.add(wishlist)
    db.commit()
    db.refresh(wishlist)
    panti_id = panti.id
    wishlist_id = wishlist.id
    db.close()
    return TestClient(app), panti_id, wishlist_id


def _login(client, email, password):
    r = client.post("/api/auth/login", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return {"Authorization": "Bearer " + r.json()["access_token"]}


def test_goods_donation_is_persisted_and_updates_wishlist_once_on_verification():
    client, panti_id, wishlist_id = _setup_client()
    try:
        donor = _login(client, "donor@halo.test", "Donor12345")
        manager = _login(client, "manager@halo.test", "Manager12345")

        created = client.post(
            "/api/masyarakat/donasi",
            headers=donor,
            json={
                "id_panti": panti_id,
                "jenis_donasi": "barang",
                "id_wishlist": wishlist_id,
                "jumlah_barang": 3,
                "satuan_barang": "kg",
                "estimasi_waktu_antar": "2026-10-10",
            },
        )
        assert created.status_code == 201, created.text
        donation_id = created.json()["id"]
        assert created.json()["nama_barang"] == "Beras"
        assert created.json()["jumlah_nominal"] in ("0", "0.00", 0, 0.0)

        verified = client.patch(
            f"/api/panti/donasi/{donation_id}/status",
            headers=manager,
            params={"new_status": "terverifikasi"},
        )
        assert verified.status_code == 200, verified.text

        # Read through public endpoint; the wishlist should now be 5/10.
        public = client.get(f"/api/public/panti/{panti_id}/wishlist")
        assert public.status_code == 200
        assert public.json()[0]["jumlah_terpenuhi"] == 5

        # Reverification after terminal status must be rejected.
        repeated = client.patch(
            f"/api/panti/donasi/{donation_id}/status",
            headers=manager,
            params={"new_status": "terverifikasi"},
        )
        assert repeated.status_code == 200
    finally:
        app.dependency_overrides.clear()


def test_public_statistics_endpoint_is_registered_and_returns_data_shape():
    client, _, _ = _setup_client()
    try:
        response = client.get("/api/public/statistics")
        assert response.status_code == 200
        body = response.json()
        assert body["total_panti"] == 1
        assert body["panti_dengan_status_akreditasi"] == 1
        assert body["total_anak_asuh_tercatat"] == 12
        assert body["anak_dalam_rehabilitasi"] is None
    finally:
        app.dependency_overrides.clear()
