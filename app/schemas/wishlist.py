from pydantic import BaseModel, ConfigDict, Field


class WishlistCreate(BaseModel):
    nama_barang: str = Field(min_length=2, max_length=100)
    jumlah_kebutuhan: int = Field(gt=0)


class WishlistUpdate(BaseModel):
    nama_barang: str | None = Field(default=None, min_length=2, max_length=100)
    jumlah_kebutuhan: int | None = Field(default=None, gt=0)
    jumlah_terpenuhi: int | None = Field(default=None, ge=0)


class WishlistResponse(BaseModel):
    id: int
    id_panti: int
    nama_barang: str
    jumlah_kebutuhan: int
    jumlah_terpenuhi: int

    model_config = ConfigDict(from_attributes=True)
