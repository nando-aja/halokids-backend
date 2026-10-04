from datetime import date, datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


DonationType = Literal["uang", "barang"]
DonationStatus = Literal["menunggu", "terverifikasi", "ditolak"]


class DonationCreate(BaseModel):
    id_panti: int
    jenis_donasi: DonationType
    jumlah_nominal: Decimal | None = Field(default=None, ge=0)
    bukti_transfer: str | None = None
    estimasi_waktu_antar: date | None = None

    # Hanya digunakan untuk donasi barang.
    id_wishlist: int | None = None
    nama_barang: str | None = Field(default=None, min_length=2, max_length=150)
    jumlah_barang: int | None = Field(default=None, gt=0)
    satuan_barang: str | None = Field(default=None, max_length=30)

    @model_validator(mode="after")
    def validate_by_type(self):
        if self.jenis_donasi == "uang":
            if self.jumlah_nominal is None or self.jumlah_nominal <= 0:
                raise ValueError("jumlah_nominal wajib lebih dari 0 untuk donasi uang")
            if any((self.id_wishlist, self.nama_barang, self.jumlah_barang, self.satuan_barang)):
                raise ValueError("Detail barang hanya boleh digunakan untuk donasi barang")
        else:
            if self.bukti_transfer:
                raise ValueError("Bukti transfer tidak digunakan untuk donasi barang")
            if self.jumlah_barang is None or self.jumlah_barang <= 0:
                raise ValueError("jumlah_barang wajib lebih dari 0 untuk donasi barang")
            if not self.satuan_barang:
                raise ValueError("satuan_barang wajib diisi untuk donasi barang")
            if not self.estimasi_waktu_antar:
                raise ValueError("estimasi_waktu_antar wajib untuk donasi barang")
            if self.id_wishlist is None and not self.nama_barang:
                raise ValueError("Pilih wishlist atau isi nama_barang untuk donasi barang")
            if self.id_wishlist is not None and self.nama_barang:
                # Nama dari wishlist menjadi sumber kebenaran ketika wishlist dipilih.
                raise ValueError("Jangan isi nama_barang jika menggunakan id_wishlist")

        return self


class DonationResponse(BaseModel):
    id: int
    id_user: int
    id_panti: int
    jenis_donasi: DonationType
    jumlah_nominal: Decimal
    id_wishlist: int | None
    nama_barang: str | None
    jumlah_barang: int | None
    satuan_barang: str | None
    bukti_transfer: str | None
    estimasi_waktu_antar: date | None
    status_verifikasi: DonationStatus
    tanggal_donasi: datetime

    model_config = ConfigDict(from_attributes=True)
