from datetime import date

from pydantic import BaseModel, Field


class VisitEventBase(BaseModel):
    id_panti: int | None = None
    judul: str = Field(min_length=3, max_length=150)
    tanggal: date
    jam_mulai: str | None = Field(default=None, max_length=5, pattern=r"^\d{2}:\d{2}$")
    jam_selesai: str | None = Field(default=None, max_length=5, pattern=r"^\d{2}:\d{2}$")
    lokasi: str | None = Field(default=None, max_length=255)
    deskripsi: str | None = Field(default=None, max_length=1000)


class VisitEventCreate(VisitEventBase):
    pass


class VisitEventUpdate(BaseModel):
    id_panti: int | None = None
    judul: str | None = Field(default=None, min_length=3, max_length=150)
    tanggal: date | None = None
    jam_mulai: str | None = Field(default=None, max_length=5, pattern=r"^\d{2}:\d{2}$")
    jam_selesai: str | None = Field(default=None, max_length=5, pattern=r"^\d{2}:\d{2}$")
    lokasi: str | None = Field(default=None, max_length=255)
    deskripsi: str | None = Field(default=None, max_length=1000)


class VisitEventResponse(VisitEventBase):
    id: int
