from sqlalchemy import Column, Integer, String, DateTime, Enum
from sqlalchemy.sql import func

from app.db.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(
        Integer,
        primary_key=True,
        index=True
    )

    nama = Column(
        String(100),
        nullable=False
    )

    email = Column(
        String(100),
        unique=True,
        index=True,
        nullable=False
    )

    no_hp = Column(
        String(20),
        nullable=True
    )

    password_hash = Column(
        String(255),
        nullable=False
    )

    peran = Column(
        Enum(
            "masyarakat",
            "pengelola-panti",
            "admin",
            name="user_role"
        ),
        default="masyarakat",
        nullable=False
    )

    tanggal_daftar = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False
    )