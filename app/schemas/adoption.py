from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


AdoptionStatus = Literal[
    "diajukan",
    "menunggu_tinjauan_manual",
    "diverifikasi",
    "disetujui",
    "ditolak",
]


AdditionalDocumentType = Literal[
    "surat_kesehatan_jiwa",
    "fungsi_reproduksi",
    "surat_penghasilan",
    "pernyataan_resmi",
    "persetujuan_keluarga",
    "dokumen_caa",
    "laporan_sosial",
    "pas_foto",
    "foto_rumah",
    "dokumen_lainnya",
]


class AdoptionBase(BaseModel):
    nama_pemohon: str = Field(min_length=2, max_length=100)
    tanggal_lahir_pemohon: date
    tanggal_pernikahan: date
    dokumen_ktp: str | None = None
    dokumen_kk: str | None = None
    dokumen_pendukung: dict[str, str] | None = None


class AdoptionCreate(AdoptionBase):
    pass


class AdoptionAdditionalDocument(BaseModel):
    jenis_dokumen: AdditionalDocumentType


class AdoptionEligibilityResponse(BaseModel):
    eligible: bool
    usia_pemohon: int
    usia_minimal: int
    usia_maksimal: int
    lama_pernikahan_tahun: int
    lama_pernikahan_bulan: int
    minimal_lama_pernikahan_tahun: int
    errors: list[str] = Field(default_factory=list)


class AdoptionResponse(AdoptionBase):
    id: int
    id_user: int
    hasil_ekstraksi_ai: dict | None = None
    status: AdoptionStatus
    tanggal_pengajuan: datetime

    model_config = ConfigDict(from_attributes=True)
