# HaloKids Backend - Final Lengkap

Paket ini menggunakan 10 tabel inti HaloKids, FastAPI + MySQL, JWT/bcrypt, local file storage, dua alur AI internal, dan chatbot Custom Agentic AI publik.

## Role
- `masyarakat`: layanan publik setelah login: COTA/adopsi, donasi, pengaduan, relawan, notifikasi, profil.
- `pengelola-panti`: hanya mengelola panti yang ditugaskan: data operasional, wishlist, donasi, laporan dana, galeri, notifikasi.
- `admin`: Admin Dinsos: user/role, seluruh panti, pengaduan, COTA, verifikasi AI, donasi, relawan, kalender, laporan pengawasan, notifikasi, statistik.
- Guest bukan role database; Guest menggunakan endpoint publik tanpa JWT.

## AI internal
Tidak ada OpenAI, Gemini, Claude, Anthropic, atau API AI eksternal.

### Agent dokumen
`app/services/ai_service.py` melakukan: PDF/image extraction, OCR, field extraction, validasi karakteristik dokumen, matching nama/tanggal dengan data pengajuan, nominal transfer matching, anomaly detection, dan human-in-the-loop.

### Agent chatbot
`app/services/agentic_chat.py` melakukan: intent detection, entity extraction, memory sesi pendek, tool selection, query database, business rule kelayakan adopsi, emergency triage, dan response generation.

Endpoint:
- `GET /api/public/ai/health`
- `POST /api/public/ai/chat`

## Modul
- Direktori panti + wishlist + galeri + laporan dana + laporan pengawasan publik.
- COTA/adopsi + kelayakan + dokumen awal/tambahan + OCR + review manual.
- Pengaduan anonim/login + kode tiket + status + notifikasi.
- Donasi uang + bukti transfer + analisis nominal.
- Donasi barang + wishlist + nama/jumlah/satuan + estimasi antar + pemenuhan wishlist saat terverifikasi; validasi mencegah nama barang ganda ketika wishlist dipilih.
- Relawan + identitas + verifikasi.
- Kalender kunjungan/open house yang dikelola admin secara file JSON.
- Dashboard/statistik admin dan statistik publik yang hanya memakai data yang tersedia.

## Endpoint penting publik
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

## Instalasi
1. Backup folder HaloKids dan database `halokids_db`.
2. Jangan salin `.env.example` menjadi `.env` jika `.env` lama sudah benar; pertahankan `.env` lama.
3. Pastikan `.env` memiliki `DATABASE_URL`, `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, dan opsional `FRONTEND_ORIGINS`.
4. Aktifkan venv lalu: `python -m pip install -r requirements.txt`.
5. Pasang Tesseract OCR pada Windows untuk scan gambar/PDF; atau set `TESSERACT_CMD` ke path `tesseract.exe`.
6. Periksa migration: `alembic current`.
7. Jika database lama sudah di-stamp pada `4e754c9ff4c4`, jalankan `alembic upgrade head` agar kolom donasi barang ditambahkan.
8. Jika database kosong, `alembic upgrade head` dapat membuat baseline kemudian menambahkan perubahan terbaru; atau gunakan `python scripts/create_tables.py` untuk membuat tabel dari metadata.
9. Jalankan `uvicorn app.main:app --reload`.
10. Buka `http://127.0.0.1:8000/docs`.

## Catatan database
Migration baru tidak membuat tabel baru. Jumlah tabel inti tetap 10; perubahan donasi hanya menambah kolom pada tabel `donasi`. Jangan menjalankan DROP DATABASE untuk pemasangan paket.

## Testing
Jalankan `pytest tests` setelah dependency terpasang. Pengujian lokal/SQLite di paket tidak menggantikan pengujian akhir menggunakan MySQL dan Windows pada komputer project.
