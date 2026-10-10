from pydantic import BaseModel, Field


class PublicStatisticsResponse(BaseModel):
    total_panti: int = Field(ge=0)
    total_adopsi: int = Field(ge=0)
    total_relawan: int = Field(ge=0)
    panti_dengan_status_akreditasi: int = Field(ge=0)
    persentase_panti_dengan_status_akreditasi: float = Field(ge=0, le=100)
    total_pengaduan: int = Field(ge=0)
    kasus_pengaduan_ditangani: int = Field(ge=0)
    total_donasi: int = Field(ge=0)
    total_nominal_donasi_uang: str
    total_anak_asuh_tercatat: int = Field(ge=0)
    anak_dalam_rehabilitasi: int | None = None
    rata_rata_respons_jam: float | None = None
    catatan: list[str] = Field(default_factory=list)
