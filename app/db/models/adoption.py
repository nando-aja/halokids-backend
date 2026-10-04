from sqlalchemy import (
    Column,
    Integer,
    String,
    Date,
    DateTime,
    ForeignKey,
    JSON,
    Enum
)

from sqlalchemy.sql import func

from app.db.database import Base


class PengajuanAdopsi(Base):
    __tablename__ = "pengajuan_adopsi"

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

    nama_pemohon = Column(
        String(100),
        nullable=False
    )

    tanggal_lahir_pemohon = Column(
        Date,
        nullable=False
    )

    tanggal_pernikahan = Column(
        Date,
        nullable=False
    )

    dokumen_ktp = Column(
        String(255),
        nullable=True
    )

    dokumen_kk = Column(
        String(255),
        nullable=True
    )

    dokumen_pendukung = Column(
        JSON,
        nullable=True
    )

    hasil_ekstraksi_ai = Column(
        JSON,
        nullable=True
    )

    status = Column(
        Enum(
            "diajukan",
            "menunggu_tinjauan_manual",
            "diverifikasi",
            "disetujui",
            "ditolak",
            name="status_pengajuan_adopsi"
        ),
        default="diajukan",
        nullable=False
    )

    tanggal_pengajuan = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )