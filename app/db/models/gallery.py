from sqlalchemy import (
    Column,
    Integer,
    String,
    Text,
    ForeignKey
)

from app.db.database import Base


class GaleriPanti(Base):
    __tablename__ = "galeri_panti"

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

    foto = Column(
        String(255),
        nullable=False
    )

    deskripsi = Column(
        Text,
        nullable=True
    )