# Checklist Instalasi Final HaloKids Backend

## A. Sebelum menyalin
- Backup folder `HaloKidsBackend`.
- Backup database `halokids_db`.
- Pertahankan folder `storage/` dan data upload lama.
- Pertahankan `.env` lama yang berisi koneksi database/secret.

## B. Salin source
Salin dari paket ini:
- `app/`
- `alembic/`
- `scripts/`
- `tests/`
- `requirements.txt`
- `alembic.ini`
- `.env.example` hanya sebagai referensi.

Jangan salin:
- `venv/`
- `.env.example` menjadi `.env` secara buta
- folder `storage/` paket menimpa storage lama.

## C. Dependency
```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

## D. Database & Alembic
```powershell
alembic current
alembic heads
```

Jika database lama sudah berada pada revision `4e754c9ff4c4`, jalankan:
```powershell
alembic upgrade head
```

Migration baru `50e66424d641` hanya menambah kolom donasi barang. Tidak ada DROP TABLE/DATABASE.

## E. Tesseract
Pasang Tesseract OCR pada Windows. Jika lokasinya tidak terdeteksi otomatis, tambahkan di `.env`:
```env
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

## F. Run
```powershell
uvicorn app.main:app --reload
```
Buka `http://127.0.0.1:8000/docs`.

## G. Smoke test
```powershell
pytest tests
```

Lalu tes manual minimal:
1. Register masyarakat.
2. Login.
3. `GET /api/masyarakat/me`.
4. Cek kelayakan.
5. Upload dokumen.
6. Buat pengajuan.
7. Buat donasi uang.
8. Buat donasi barang dengan `id_wishlist`.
9. Login pengelola panti dan verifikasi donasi barang.
10. Pastikan `jumlah_terpenuhi` wishlist bertambah satu kali.
11. Login admin dan buka dokumen COTA melalui endpoint aman.
12. Tes `/api/public/ai/chat`.
13. Tes `anak dipukuli sekarang` → intent `emergency`.
14. Tes `bagaimana cara melaporkan kekerasan` → intent `report`.
15. Tes `GET /api/public/statistics`.
