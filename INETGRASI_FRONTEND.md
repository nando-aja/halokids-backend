# Catatan Integrasi Frontend HaloKids

## Status yang perlu diketahui

Backend menyediakan REST API di `http://127.0.0.1:8000` dan dokumentasi interaktif di `/docs`. Frontend ZIP yang diperiksa masih memakai `localStorage`/data simulasi pada beberapa alur dan belum memanggil API backend secara umum. Jadi backend yang diperbaiki ini menyiapkan endpoint dan kontraknya, tetapi frontend tetap perlu diarahkan untuk memakai API sungguhan.

## Konfigurasi

Buat `frontend/.env`:

```env
VITE_API_BASE_URL=http://127.0.0.1:8000
```

Jalankan backend dari folder backend:

```powershell
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

Frontend Vite biasanya berjalan pada port `5173`; origin itu sudah termasuk CORS default. Untuk port lain, tambahkan ke `FRONTEND_ORIGINS` di `.env` backend (pisahkan dengan koma), lalu restart backend.

## Contoh API client minimal (frontend/src/services/api.js)

```js
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || 'http://127.0.0.1:8000';

export async function apiRequest(path, { token, ...options } = {}) {
  const headers = new Headers(options.headers || {});
  if (token) headers.set('Authorization', `Bearer ${token}`);
  if (options.body && !(options.body instanceof FormData) && !headers.has('Content-Type')) {
    headers.set('Content-Type', 'application/json');
  }

  const response = await fetch(`${API_BASE_URL}${path}`, { ...options, headers });
  const contentType = response.headers.get('content-type') || '';
  const payload = contentType.includes('application/json')
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    if (response.status === 401) {
      localStorage.removeItem('halokids_active_session');
    }
    const message = typeof payload === 'object' && payload?.detail
      ? payload.detail
      : `Request gagal (${response.status})`;
    throw new Error(message);
  }
  return payload;
}

export async function login(email, password) {
  const form = new URLSearchParams({ username: email, password });
  return apiRequest('/api/auth/login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
    body: form,
  });
}
```

Login backend menggunakan form URL-encoded, bukan JSON. Simpan `access_token` dari respons dan kirim sebagai `Authorization: Bearer <token>` pada endpoint privat. Saat upload file, gunakan `FormData` dan jangan mengatur `Content-Type` secara manual karena browser menambahkan boundary multipart.

## Endpoint awal yang disarankan untuk disambungkan

- Landing page: `GET /api/public/statistics`, `GET /api/public/panti`
- Detail panti: `GET /api/public/panti/{id}`, `/wishlist`, `/galeri`, `/laporan-dana`, `/laporan-pengawasan`
- Login/registrasi: `POST /api/auth/login`, `POST /api/auth/register`
- Pengaduan: `POST /api/public/pengaduan`, `GET /api/public/pengaduan/{kode_tiket}`
- Donasi: `POST /api/upload/bukti-transfer`, `POST /api/masyarakat/donasi`, `GET /api/masyarakat/donasi`
- Adopsi: endpoint di tag `Masyarakat` dan `Upload Berkas` pada `/docs`

Role valid adalah `masyarakat`, `pengelola-panti`, dan `admin`. Endpoint login menerima `username` yang berisi email. Daftar endpoint, tipe input, dan contoh respons paling akurat tersedia di Swagger `/docs`.
