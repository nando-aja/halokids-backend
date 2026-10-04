from pydantic import BaseModel, ConfigDict, Field


class PantiBase(BaseModel):
    nama_panti: str = Field(min_length=2, max_length=150)
    alamat: str = Field(min_length=5)
    kontak: str | None = Field(default=None, max_length=50)
    status_akreditasi: str | None = Field(default=None, max_length=50)
    jumlah_anak_asuh: int | None = Field(default=None, ge=0)
    id_admin_pengelola: int | None = None


class PantiCreate(PantiBase):
    pass


class PantiUpdate(BaseModel):
    nama_panti: str | None = Field(default=None, min_length=2, max_length=150)
    alamat: str | None = Field(default=None, min_length=5)
    kontak: str | None = Field(default=None, max_length=50)
    status_akreditasi: str | None = Field(default=None, max_length=50)
    jumlah_anak_asuh: int | None = Field(default=None, ge=0)
    id_admin_pengelola: int | None = None


class PantiResponse(PantiBase):
    id: int

    model_config = ConfigDict(from_attributes=True)
