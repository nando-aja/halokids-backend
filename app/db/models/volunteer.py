from sqlalchemy import Column, Date, Enum, ForeignKey, Integer, String, Text, TIMESTAMP, text
from app.db.database import Base


class Relawan(Base):
    __tablename__ = "relawan"

    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    id_user = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    dokumen_identitas = Column(String(255), nullable=True)
    status = Column(Enum("menunggu", "disetujui", "ditolak", name="status_relawan"), nullable=False, default="menunggu", server_default="menunggu")
    nama = Column(String(150), nullable=True)
    nomor_hp = Column(String(20), nullable=True)
    alamat = Column(Text, nullable=True)
    usia = Column(Integer, nullable=True)
    bidang = Column(String(100), nullable=True)
    panti_tujuan = Column(String(150), nullable=True)
    tanggal = Column(Date, nullable=True)
    sesi_waktu = Column(String(100), nullable=True)
    tujuan_kerelawanan = Column(Text, nullable=True)
    created_at = Column(TIMESTAMP, nullable=True, server_default=text("CURRENT_TIMESTAMP"))
    id_panti = Column(Integer, ForeignKey("panti_asuhan.id", ondelete="SET NULL"), nullable=True, index=True)
