from sqlalchemy import (
    Column,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    Numeric,
    String,
)
from sqlalchemy.sql import func

from app.db.database import Base


class Donasi(Base):
    __tablename__ = "donasi"

    id = Column(Integer, primary_key=True, index=True)

    id_user = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True,
    )

    id_panti = Column(
        Integer,
        ForeignKey("panti_asuhan.id"),
        nullable=False,
        index=True,
    )

    jenis_donasi = Column(
        Enum("uang", "barang", name="jenis_donasi"),
        nullable=False,
    )

    # Untuk donasi uang, nilai nominal harus > 0.
    # Untuk donasi barang, backend menyimpan 0 agar schema database lama
    # tetap kompatibel tanpa membuat nominal palsu.
    jumlah_nominal = Column(Numeric(15, 2), nullable=False, default=0)

    # Tambahan untuk melengkapi alur donasi barang tanpa menambah tabel baru.
    id_wishlist = Column(
        Integer,
        ForeignKey("wishlist_panti.id", name="fk_donasi_id_wishlist"),
        nullable=True,
        index=True,
    )
    nama_barang = Column(String(150), nullable=True)
    jumlah_barang = Column(Integer, nullable=True)
    satuan_barang = Column(String(30), nullable=True)

    bukti_transfer = Column(String(255), nullable=True)

    estimasi_waktu_antar = Column(Date, nullable=True)

    status_verifikasi = Column(
        Enum(
            "menunggu",
            "terverifikasi",
            "ditolak",
            name="status_verifikasi_donasi",
        ),
        default="menunggu",
        nullable=False,
    )

    tanggal_donasi = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
