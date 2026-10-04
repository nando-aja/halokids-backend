from sqlalchemy import (
    Column,
    Integer,
    String,
    DateTime,
    ForeignKey
)

from sqlalchemy.sql import func

from app.db.database import Base


class LaporanDana(Base):
    __tablename__ = "laporan_dana"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    id_panti = Column(
        Integer,
        ForeignKey("panti_asuhan.id"),
        nullable=False,
        index=True
    )

    file_laporan = Column(
        String(255),
        nullable=False
    )

    tanggal_unggah = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )