from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field


RoleType = Literal[
    "masyarakat",
    "pengelola-panti",
    "admin",
]


class UserBase(BaseModel):
    nama: str = Field(min_length=2, max_length=100)
    email: EmailStr
    no_hp: str | None = Field(default=None, max_length=20)


class UserCreate(UserBase):
    password: str = Field(min_length=8, max_length=128)


class UserUpdate(BaseModel):
    nama: str | None = Field(default=None, min_length=2, max_length=100)
    no_hp: str | None = Field(default=None, max_length=20)


class UserRoleUpdate(BaseModel):
    peran: RoleType


class UserResponse(UserBase):
    id: int
    peran: RoleType
    tanggal_daftar: datetime

    model_config = ConfigDict(from_attributes=True)
