# Changelog Perbaikan HaloKids Backend

Versi ini melanjutkan paket final sebelumnya dan menutup gap yang masih tersisa pada alur backend.

## 1. Donasi barang dibuat lengkap

Tabel `donasi` tetap menjadi salah satu dari 10 tabel utama, tetapi sekarang memiliki kolom tambahan:
- `id_wishlist` untuk menghubungkan donasi ke kebutuhan wishlist panti.
- `nama_barang` untuk nama barang.
- `jumlah_barang` untuk jumlah barang.
- `satuan_barang` untuk satuan seperti kg, pcs, liter, dan sebagainya.

Untuk donasi barang, `jumlah_nominal` disimpan sebagai `0` karena tidak ada transaksi uang. Donasi uang tetap membutuhkan nominal > 0 dan bukti transfer.

Migration `50e66424d641_donasi_barang.py` menambahkan kolom tersebut ke database lama tanpa menghapus data yang sudah ada.

Saat donasi barang terverifikasi, jumlah terpenuhi pada wishlist terkait otomatis bertambah satu kali. Status donasi dibuat terminal setelah terverifikasi untuk mencegah penghitungan ganda.

## 2. Statistik publik

Ditambahkan:
`GET /api/public/statistics`

Statistik hanya dihitung dari data yang benar-benar tersedia di database. Metrik yang tidak tersedia pada schema 10 tabel dikembalikan sebagai `null` dan tidak dibuat-buat.

## 3. AI Agentic

- Deteksi emergency diperketat agar laporan kekerasan umum tidak selalu dianggap darurat.
- Kalimat seperti `anak dipukuli sekarang` tetap masuk intent `emergency`.
- Pertanyaan seperti `bagaimana cara melaporkan kekerasan` masuk intent `report`.
- Ekstraksi nama OCR menerima format dengan dan tanpa titik dua.
- Validasi isi dokumen heuristik ditambahkan berdasarkan karakteristik teks dokumen. Hasil tetap menjadi alat bantu; keputusan final tetap Admin Dinsos.
- Statistik chatbot menggunakan service statistik publik yang sama dengan endpoint publik agar hasil konsisten.
- Rate limit chatbot publik: 30 request/menit per alamat client.

## 4. Akses file

Admin tetap dapat membuka dokumen yang direferensikan aplikasi. Endpoint dokumen adopsi khusus menggunakan record pengajuan sebagai sumber path, sehingga lebih aman daripada membuka file berdasarkan path mentah.

## 5. Hak akses pengelola panti

Pengelola panti tidak dapat mengubah `status_akreditasi` panti sendiri. Perubahan legalitas/akreditasi tetap berada pada Admin Dinsos.

## 6. Tesseract Windows

`ai_service.py` sekarang mencoba lokasi instalasi Tesseract Windows yang umum dan juga mendukung environment variable `TESSERACT_CMD`.
