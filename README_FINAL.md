# HaloKids Backend

Paket ini menggunakan 10 tabel inti HaloKids, FastAPI + MySQL, JWT/bcrypt, local file storage, serta layanan AI internal untuk analisis dokumen dan bukti transfer. Fitur chatbot publik tidak termasuk dalam versi ini.

## Role

- `masyarakat`: layanan publik setelah login, meliputi COTA/adopsi, donasi, pengaduan, relawan, notifikasi, dan profil.
- `pengelola-panti`: mengelola panti yang ditugaskan, termasuk data operasional, wishlist, donasi, laporan dana, galeri, dan notifikasi.
- `admin`: Admin Dinsos yang mengelola pengguna, seluruh panti, pengaduan, COTA, verifikasi dokumen, donasi, relawan, kalender, laporan pengawasan, notifikasi, dan statistik.
- Guest bukan role database. Guest menggunakan endpoint publik tanpa JWT.

## AI Internal

Layanan AI internal menggunakan `app/services/ai_service.py`. Layanan ini tidak memerlukan chatbot dan tidak menggunakan OpenAI, Gemini, Claude, Anthropic, atau API AI generatif eksternal.

### Analisis dokumen

`app/services/ai_service.py` mendukung pemrosesan PDF/gambar, OCR, ekstraksi informasi dokumen, pemeriksaan karakteristik dokumen, pencocokan nama dan tanggal dengan data pengajuan, serta dukungan peninjauan manual.

### Analisis bukti transfer

Layanan mendukung ekstraksi teks dari bukti transfer, pembacaan nominal, dan pencocokan nominal dengan nilai yang diharapkan. Hasil analisis tetap perlu mengikuti proses verifikasi yang berlaku.

Catatan: OCR dan pencocokan data tidak menjamin keaslian dokumen atau keberhasilan transaksi secara otomatis.

## Modul

- Direktori panti, wishlist, galeri, laporan dana, dan laporan pengawasan publik.
- COTA/adopsi, pemeriksaan kelayakan awal, dokumen awal/tambahan, OCR, dan peninjauan manual.
- Pengaduan anonim/login, kode tiket, status pengaduan, dan notifikasi.
- Donasi uang, bukti transfer, dan analisis nominal.
- Donasi barang, wishlist, nama/jumlah/satuan, estimasi antar, dan pemenuhan wishlist setelah donasi diverifikasi.
- Relawan, identitas, dan verifikasi.
- Kalender kunjungan/open house yang dikelola admin melalui file JSON.
- Dashboard admin, statistik admin, dan statistik publik berdasarkan data yang tersedia.

## Endpoint Penting Publik

- `GET /api/public/panti`
- `GET /api/public/panti/{id}`
- `GET /api/public/panti/{id}/wishlist`
- `GET /api/public/panti/{id}/galeri`
- `GET /api/public/panti/{id}/laporan-dana`
- `GET /api/public/panti/{id}/laporan-pengawasan`
- `GET /api/public/statistics`
- `POST /api/public/pengaduan`
- `GET /api/public/pengaduan/{kode_tiket}`
- `GET /api/public/kalender-kunjungan`
- `GET /api/public/files/{folder}/{filename}` untuk folder publik saja

Endpoint chatbot `/api/public/ai/chat` dan `/api/public/ai/health` tidak digunakan dalam versi ini.

## Instalasi

1. Backup folder HaloKids dan database `halokids_db`.
2. Pertahankan file `.env` lama jika konfigurasinya masih benar.
3. Pastikan `.env` memiliki `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, dan `ACCESS_TOKEN_EXPIRE_MINUTES`. `FRONTEND_ORIGINS` digunakan jika diperlukan.
4. Aktifkan virtual environment, lalu jalankan `python -m pip install -r requirements.txt`.
5. Pasang Tesseract OCR pada Windows untuk pemrosesan gambar/PDF hasil scan, atau atur `TESSERACT_CMD` ke lokasi `tesseract.exe`.
6. Periksa migration dengan `alembic current`.
7. Jika database lama sudah berada pada revision `4e754c9ff4c4`, jalankan `alembic upgrade head` sesuai kondisi migration project.
8. Jika database kosong, ikuti petunjuk migration atau gunakan `python scripts/create_tables.py` sesuai konfigurasi project.
9. Jalankan `uvicorn app.main:app --reload`.
10. Buka `http://127.0.0.1:8000/docs`.

## Catatan Database

Migration terbaru terkait donasi barang menambahkan kolom yang dibutuhkan pada tabel `donasi`. Jangan menjalankan `DROP DATABASE` untuk pemasangan paket. Selalu backup database sebelum menjalankan migration.

## Testing

Jalankan:

`pytest tests`

Pengujian lokal atau SQLite tidak menggantikan pengujian akhir menggunakan MySQL, Windows, Tesseract, dan frontend pada komputer project.

Pastikan seluruh endpoint yang masih digunakan berjalan normal setelah penghapusan chatbot.