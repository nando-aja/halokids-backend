from sqlalchemy import (
    Column,
    Integer,
    String,
    ForeignKey
)

from app.db.database import Base


class WishlistPanti(Base):
    __tablename__ = "wishlist_panti"

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

    nama_barang = Column(
        String(100),
        nullable=False
    )

    jumlah_kebutuhan = Column(
        Integer,
        nullable=False
    )

    jumlah_terpenuhi = Column(
        Integer,
        default=0,
        nullable=False
    )