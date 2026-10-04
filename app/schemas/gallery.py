from pydantic import BaseModel, Field, ConfigDict


class GalleryBase(BaseModel):
    id_panti: int

    foto: str = Field(
        min_length=1,
        max_length=255
    )

    deskripsi: str | None = None


class GalleryCreate(GalleryBase):
    pass


class GalleryResponse(GalleryBase):
    id: int

    model_config = ConfigDict(
        from_attributes=True
    )