"""sinkronisasi model HaloKids

Revision ID: 4e754c9ff4c4
Revises: 
Create Date: 2026-09-25 10:10:57.195530

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '4e754c9ff4c4'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """
    Migration baseline.

    Membuat tabel HaloKids yang BELUM ada (checkfirst=True). Tabel yang sudah
    ada di database halokids_db tidak diubah dan datanya tidak disentuh,
    sehingga aman dijalankan pada database yang sudah berisi.
    """
    from app.db.database import Base
    from app.db import models  # noqa: F401

    Base.metadata.create_all(bind=op.get_bind(), checkfirst=True)


def downgrade() -> None:
    """
    Sengaja tidak menghapus tabel agar data HaloKids tidak hilang tanpa
    sengaja. Hapus tabel secara manual bila memang diperlukan.
    """
    pass
