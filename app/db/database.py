from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.core.config import settings

# Membuat engine koneksi ke database
engine = create_engine(settings.DATABASE_URL)

# Membuat session yang akan digunakan di setiap request (Dependency)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Base class untuk semua model tabel kita nanti
Base = declarative_base()