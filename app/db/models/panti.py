from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey
)

from app.db.database import Base


class PantiAsuhan(Base):
    __tablename__ = "panti_asuhan"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nama_panti = Column(
        String(150),
        nullable=False
    )

    alamat = Column(
        Text,
        nullable=False
    )

    kontak = Column(
        String(50),
        nullable=True
    )

    status_akreditasi = Column(
        String(50),
        nullable=True
    )

    jumlah_anak_asuh = Column(
        Integer,
        nullable=True
    )

    id_admin_pengelola = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        index=True
    )