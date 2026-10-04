from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.core.security import (
    hash_password,
    verify_password,
    create_access_token
)
from app.db.models.user import User
from app.schemas.user import UserCreate, UserResponse
from app.schemas.auth import TokenResponse


router = APIRouter()


# ==========================================
# REGISTER
# ==========================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED
)
def register(
    user_data: UserCreate,
    db: Session = Depends(get_db)
):
    """
    Mendaftarkan user baru.

    User yang mendaftar melalui endpoint publik
    otomatis memiliki role 'masyarakat'.
    """

    # Cek email sudah terdaftar atau belum
    existing_user = db.query(User).filter(
        User.email == user_data.email
    ).first()

    if existing_user:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Email sudah terdaftar"
        )

    # Buat user baru
    new_user = User(
        nama=user_data.nama,
        email=user_data.email,
        no_hp=user_data.no_hp,
        password_hash=hash_password(user_data.password),
        peran="masyarakat"
    )

    db.add(new_user)
    db.commit()
    db.refresh(new_user)

    return new_user


# ==========================================
# LOGIN
# ==========================================

@router.post(
    "/login",
    response_model=TokenResponse
)
def login(
    form_data: OAuth2PasswordRequestForm = Depends(),
    db: Session = Depends(get_db)
):
    """
    Login menggunakan email dan password.

    Pada Swagger, kolom 'username' diisi dengan email.
    """

    user = db.query(User).filter(
        User.email == form_data.username
    ).first()

    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    if not verify_password(
        form_data.password,
        user.password_hash
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Email atau password salah",
            headers={
                "WWW-Authenticate": "Bearer"
            }
        )

    access_token = create_access_token(
        data={
            "sub": str(user.id),
            "role": user.peran
        }
    )

    return {
        "access_token": access_token,
        "token_type": "bearer"
    }