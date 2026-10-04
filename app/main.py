from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api.routes import admin, ai, auth, masyarakat, panti, public, upload
from app.core.config import settings
from app.db.database import engine


app = FastAPI(
    title="HaloKids API",
    description="Backend untuk Sistem Informasi Pelindungan Anak dan Panti Asuhan",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/auth", tags=["Authentication"])
app.include_router(public.router, prefix="/api/public", tags=["Public"])
app.include_router(ai.router, prefix="/api/public/ai", tags=["Public AI Agent"])
app.include_router(masyarakat.router, prefix="/api/masyarakat", tags=["Masyarakat"])
app.include_router(panti.router, prefix="/api/panti", tags=["Pengelola Panti"])
app.include_router(admin.router, prefix="/api/admin", tags=["Admin Dinsos"])
app.include_router(upload.router, prefix="/api/upload", tags=["Upload Berkas"])


@app.get("/")
def read_root() -> dict[str, str]:
    return {
        "message": "HaloKids API berhasil berjalan",
        "docs": "/docs",
        "ai_chat": "/api/public/ai/chat",
    }


@app.get("/cek-db")
def check_db() -> dict[str, str]:
    try:
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        return {
            "database": "connected",
            "message": "Koneksi MySQL berhasil",
        }
    except Exception as exc:
        return {
            "database": "error",
            "message": "Koneksi MySQL gagal",
            "detail": str(exc),
        }
