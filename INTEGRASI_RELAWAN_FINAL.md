# Integrasi Relawan HaloKids — Final

## Database
Model disesuaikan dengan tabel MySQL `relawan` yang telah ada. Tidak ada migrasi/ALTER TABLE baru dalam paket ini. Kolom yang digunakan: `id`, `id_user`, `dokumen_identitas`, `status`, `nama`, `nomor_hp`, `alamat`, `usia`, `bidang`, `panti_tujuan`, `tanggal`, `sesi_waktu`, `tujuan_kerelawanan`, `created_at`, `id_panti`.

## Endpoint
- `POST /api/upload/identitas-relawan` — multipart field `file`; perlu token masyarakat. Respons mengandung `dokumen_identitas`.
- `POST /api/masyarakat/relawan` — JSON pendaftaran, perlu token masyarakat.
- `GET /api/masyarakat/relawan` — pendaftaran milik pengguna login.
- `GET /api/admin/relawan` — daftar semua relawan, perlu token admin.
- `PATCH /api/admin/relawan/{id}/status?new_status=disetujui|ditolak|menunggu` — ubah status.
- `PUT /api/admin/relawan/{id}` — edit data pendaftaran, perlu token admin.
- `DELETE /api/admin/relawan/{id}` — hapus data, perlu token admin.

## Contoh JSON POST /api/masyarakat/relawan
```json
{
  "dokumen_identitas": "storage/identitas_relawan/NAMA_FILE.pdf",
  "nama": "Nama Relawan",
  "nomor_hp": "081234567890",
  "alamat": "Alamat relawan",
  "usia": 20,
  "bidang": "Pendidikan / Tutor Belajar",
  "panti_tujuan": "Nama panti",
  "id_panti": 1,
  "tanggal": "2026-10-20",
  "sesi_waktu": "09:00-12:00",
  "tujuan_kerelawanan": "Motivasi menjadi relawan"
}
```

Upload identitas dilakukan lebih dahulu; gunakan path persis dari respons upload. Endpoint privat memerlukan `Authorization: Bearer <token>`. Pastikan `id_panti` mengacu ke ID panti yang benar. Jalankan `uvicorn app.main:app --reload`, lalu uji endpoint di `/docs`. Paket ini tidak mengubah database secara otomatis.
