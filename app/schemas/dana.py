from datetime import datetime

from pydantic import BaseModel, ConfigDict


class DanaBase(BaseModel):
    id_panti: int
    file_laporan: str


class DanaCreate(DanaBase):
    pass


class DanaResponse(DanaBase):
    id: int
    tanggal_unggah: datetime

    model_config = ConfigDict(
        from_attributes=True
    )