# Checklist Instalasi Final HaloKids Backend

## A. Sebelum Menyalin

- Backup folder `HaloKidsBackend`.
- Backup database `halokids_db`.
- Pertahankan folder `storage/` dan data upload lama.
- Pertahankan file `.env` lama yang berisi konfigurasi database dan secret.
- Pastikan source code chatbot sudah dihapus sesuai prosedur penghapusan fitur.

## B. Salin Source Code

Salin atau perbarui file project yang diperlukan:

- `app/`
- `alembic/`
- `scripts/`
- `tests/`
- `requirements.txt`
- `alembic.ini`
- `.env.example` hanya sebagai referensi konfigurasi.

Jangan menyalin:

- `venv/`
- `.env.example` menjadi `.env` secara langsung tanpa memeriksa konfigurasi.
- Folder `storage/` dari paket hingga menimpa file upload lama.

Pastikan file route chatbot, schema chatbot, dan service chatbot sudah dihapus atau tidak lagi digunakan.

## C. Dependency

Aktifkan virtual environment melalui PowerShell:

```powershell
.\venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Jika terdapat dependency yang hanya digunakan oleh chatbot, periksa apakah dependency tersebut masih dibutuhkan modul lain sebelum menghapusnya dari `requirements.txt`.

## D. Database dan Alembic

Jalankan:

```powershell
alembic current
alembic heads
```

Jika database lama sudah berada pada revision `4e754c9ff4c4`, jalankan migration sesuai kondisi database:

```powershell
alembic upgrade head
```

Migration `50e66424d641` terkait penambahan kolom donasi barang. Pastikan status migration sesuai sebelum menjalankannya. Jangan menjalankan `DROP TABLE` atau `DROP DATABASE`.

## E. Tesseract OCR

Pasang Tesseract OCR pada Windows.

Jika lokasi executable tidak terdeteksi otomatis, tambahkan ke `.env`:

```env
TESSERACT_CMD=C:/Program Files/Tesseract-OCR/tesseract.exe
```

Pastikan proses OCR tetap berfungsi setelah chatbot dihapus.

## F. Jalankan Backend

```powershell
uvicorn app.main:app --reload
```

Buka dokumentasi API:

`http://127.0.0.1:8000/docs`

Pastikan server berjalan tanpa error dan endpoint chatbot sudah tidak terdaftar.

## G. Pengujian Otomatis

```powershell
pytest tests
```

Jika ada pengujian yang khusus memerlukan chatbot, hapus atau sesuaikan pengujian tersebut. Jangan menghapus pengujian OCR, autentikasi, adopsi, donasi, atau fitur lainnya.

## H. Smoke Test Manual

1. Registrasi pengguna masyarakat.
2. Login dan akses `GET /api/masyarakat/me`.
3. Periksa kelayakan awal adopsi.
4. Upload dokumen pengajuan.
5. Pastikan proses OCR berjalan.
6. Buat pengajuan adopsi.
7. Buat donasi uang.
8. Upload bukti transfer.
9. Pastikan analisis nominal berjalan sesuai implementasi.
10. Login sebagai pengelola panti dan verifikasi donasi barang.
11. Pastikan `jumlah_terpenuhi` pada wishlist bertambah sesuai transaksi yang diverifikasi.
12. Login sebagai admin dan akses dokumen COTA melalui endpoint yang aman.
13. Pastikan statistik publik dapat diakses melalui `GET /api/public/statistics`.
14. Pastikan endpoint publik, pengaduan, kalender, dan direktori panti tetap berfungsi.
15. Pastikan `/api/public/ai/chat` dan `/api/public/ai/health` tidak lagi terdaftar.

## I. Pemeriksaan Akhir

- Backend berjalan tanpa error.
- Chatbot sudah tidak tersedia.
- Analisis dokumen dan bukti transfer tetap berfungsi.
- Database dan file upload lama tetap aman.
- Frontend tidak lagi memanggil endpoint chatbot.
- Semua fitur yang masih digunakan telah diuji.