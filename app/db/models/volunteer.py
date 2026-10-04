from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey,
    Enum
)

from app.db.database import Base


class Relawan(Base):
    __tablename__ = "relawan"

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

    dokumen_identitas = Column(
        String(255),
        nullable=True
    )

    status = Column(
        Enum(
            "menunggu",
            "disetujui",
            "ditolak",
            name="status_relawan"
        ),
        default="menunggu",
        nullable=False
    )