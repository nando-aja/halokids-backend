"""Lengkapi data donasi barang.

Revision ID: 50e66424d641
Revises: 4e754c9ff4c4
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "50e66424d641"
down_revision: Union[str, Sequence[str], None] = "4e754c9ff4c4"
branch_labels = None
depends_on = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    return {column["name"] for column in inspector.get_columns(table_name)}


def upgrade() -> None:
    bind = op.get_bind()
    existing = _column_names(bind, "donasi")

    if "id_wishlist" not in existing:
        op.add_column(
            "donasi",
            sa.Column("id_wishlist", sa.Integer(), nullable=True),
        )

    if "nama_barang" not in existing:
        op.add_column(
            "donasi",
            sa.Column("nama_barang", sa.String(length=150), nullable=True),
        )

    if "jumlah_barang" not in existing:
        op.add_column(
            "donasi",
            sa.Column("jumlah_barang", sa.Integer(), nullable=True),
        )

    if "satuan_barang" not in existing:
        op.add_column(
            "donasi",
            sa.Column("satuan_barang", sa.String(length=30), nullable=True),
        )

    inspector = sa.inspect(bind)
    existing_indexes = {
        index.get("name")
        for index in inspector.get_indexes("donasi")
        if index.get("name")
    }

    if "ix_donasi_id_wishlist" not in existing_indexes:
        op.create_index(
            "ix_donasi_id_wishlist",
            "donasi",
            ["id_wishlist"],
        )

    inspector = sa.inspect(bind)
    has_wishlist_fk = any(
        fk.get("referred_table") == "wishlist_panti"
        and fk.get("constrained_columns") == ["id_wishlist"]
        for fk in inspector.get_foreign_keys("donasi")
    )

    if not has_wishlist_fk:
        op.create_foreign_key(
            "fk_donasi_id_wishlist",
            "donasi",
            "wishlist_panti",
            ["id_wishlist"],
            ["id"],
        )


def downgrade() -> None:
    # Tidak melakukan drop kolom otomatis agar data donasi tidak hilang.
    pass
