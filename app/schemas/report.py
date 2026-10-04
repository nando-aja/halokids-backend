from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


ReportStatus = Literal[
    "baru",
    "diproses",
    "selesai",
]


ReportType = Literal[
    "kekerasan",
    "eksploitasi",
    "panti_ilegal",
    "lainnya",
]


class ReportCreate(BaseModel):
    isi_laporan: str = Field(min_length=10)
    jenis_laporan: ReportType


class ReportResponse(BaseModel):
    id: int
    id_user: int | None
    kode_tiket: str
    isi_laporan: str
    jenis_laporan: str
    status: ReportStatus
    tanggal_lapor: datetime

    model_config = ConfigDict(from_attributes=True)


class PublicReportStatus(BaseModel):
    kode_tiket: str
    status: ReportStatus
    tanggal_lapor: datetime

    model_config = ConfigDict(from_attributes=True)
