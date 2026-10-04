from datetime import datetime

from pydantic import BaseModel, Field, ConfigDict


class NotificationBase(BaseModel):
    judul: str = Field(
        min_length=1,
        max_length=150
    )

    pesan: str = Field(
        min_length=1,
        max_length=255
    )


class NotificationCreate(NotificationBase):
    id_user: int


class NotificationResponse(NotificationBase):
    id: int
    id_user: int
    is_read: bool
    tanggal_buat: datetime

    model_config = ConfigDict(
        from_attributes=True
    )