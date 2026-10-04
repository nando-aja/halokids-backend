from sqlalchemy import (
    Column,
    Integer,
    String,
    Boolean,
    DateTime,
    ForeignKey
)

from sqlalchemy.sql import func

from app.db.database import Base


class Notifikasi(Base):
    __tablename__ = "notifikasi"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    id_user = Column(
        Integer,
        ForeignKey("users.id"),
        nullable=False,
        index=True
    )

    judul = Column(
        String(150),
        nullable=False
    )

    pesan = Column(
        String(255),
        nullable=False
    )

    is_read = Column(
        Boolean,
        default=False,
        nullable=False
    )

    tanggal_buat = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )