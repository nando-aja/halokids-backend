from typing import Literal

from pydantic import BaseModel, ConfigDict


VolunteerStatus = Literal[
    "menunggu",
    "disetujui",
    "ditolak",
]


class VolunteerCreate(BaseModel):
    dokumen_identitas: str


class VolunteerResponse(BaseModel):
    id: int
    id_user: int
    dokumen_identitas: str | None
    status: VolunteerStatus

    model_config = ConfigDict(from_attributes=True)
