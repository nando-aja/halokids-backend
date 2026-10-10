from datetime import date, datetime
from typing import Literal
from pydantic import BaseModel, ConfigDict, Field

VolunteerStatus = Literal["menunggu", "disetujui", "ditolak"]


class VolunteerCreate(BaseModel):
    dokumen_identitas: str
    nama: str = Field(min_length=2, max_length=150)
    nomor_hp: str = Field(min_length=6, max_length=20)
    alamat: str = Field(min_length=3)
    usia: int = Field(ge=17, le=80)
    bidang: str = Field(min_length=2, max_length=100)
    panti_tujuan: str | None = Field(default=None, max_length=150)
    id_panti: int | None = Field(default=None, ge=1)
    tanggal: date | None = None
    sesi_waktu: str | None = Field(default=None, max_length=100)
    tujuan_kerelawanan: str | None = None


class VolunteerUpdate(BaseModel):
    nama: str | None = Field(default=None, min_length=2, max_length=150)
    nomor_hp: str | None = Field(default=None, min_length=6, max_length=20)
    alamat: str | None = None
    usia: int | None = Field(default=None, ge=17, le=80)
    bidang: str | None = Field(default=None, max_length=100)
    panti_tujuan: str | None = Field(default=None, max_length=150)
    id_panti: int | None = Field(default=None, ge=1)
    tanggal: date | None = None
    sesi_waktu: str | None = Field(default=None, max_length=100)
    tujuan_kerelawanan: str | None = None


class VolunteerResponse(BaseModel):
    id: int
    id_user: int
    dokumen_identitas: str | None = None
    status: VolunteerStatus
    nama: str | None = None
    nomor_hp: str | None = None
    alamat: str | None = None
    usia: int | None = None
    bidang: str | None = None
    panti_tujuan: str | None = None
    tanggal: date | None = None
    sesi_waktu: str | None = None
    tujuan_kerelawanan: str | None = None
    created_at: datetime | None = None
    id_panti: int | None = None
    model_config = ConfigDict(from_attributes=True)
