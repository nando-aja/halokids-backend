# HaloKids Custom Agentic AI

## Tujuan
AI Agentic pada halaman utama berfungsi sebagai asisten informasi publik. Agent membantu pengunjung memahami layanan HaloKids dan memanggil tool internal bila jawaban membutuhkan data database.

## Prinsip
- Dibuat sendiri di backend HaloKids.
- Tidak menggunakan OpenAI, Gemini, Claude, atau API AI eksternal.
- Tidak memerlukan API key AI.
- Deterministik: input yang sama menghasilkan keputusan intent/tool yang konsisten.
- Tidak mengambil keputusan hukum/final adopsi.
- Chat publik tidak menyimpan isi percakapan ke MySQL.
- Memory percakapan hanya sementara di RAM selama 30 menit dan dibatasi jumlah sesi.

## Alur Agent

```text
Pengunjung Halaman Utama
        |
        v
Chatbot HaloKids AI
        |
        v
POST /api/public/ai/chat
        |
        v
Sanitasi Input
        |
        v
Intent Detection + Entity Extraction
        |
        +-------------------------------+
        |                               |
        v                               v
Butuh Database?                    Jawaban Statis
        |                               |
        v                               v
Tool Selection                  Response Generator
        |
        +--> Tool Panti
        +--> Tool Status Tiket
        +--> Tool Statistik
        +--> Tool Kelayakan Awal Adopsi
        |
        v
Response Terstruktur
        |
        v
Frontend menampilkan jawaban
```

## Intent yang didukung
- about
- greeting
- help
- emergency
- report
- track_report
- adoption
- eligibility
- documents
- donation
- volunteer
- panti
- statistics
- privacy
- unknown

## Deteksi darurat dan konteks
- Kata kerja kekerasan terhadap anak (mis. dipukuli, dianiaya, diperkosa, diculik) langsung diarahkan ke jalur darurat
  (SAPA 129 dan 112) sebelum intent lain dievaluasi.
- Kata pendek ("halo", "hai", "kk") dicocokkan sebagai kata utuh.
- Pesan lanjutan ("ceritakan lebih lanjut") memakai topik terakhir dari memori sesi (RAM, 30 menit).

## Endpoint

### GET
`/api/public/ai/health`

### POST
`/api/public/ai/chat`

Request:
```json
{
  "message": "Apa syarat dokumen awal COTA?",
  "session_id": "opsional-untuk-mempertahankan-konteks"
}
```

Response:
```json
{
  "session_id": "...",
  "message": "...",
  "intent": "documents",
  "actions": [
    "mendeteksi pertanyaan dokumen",
    "mengambil daftar dokumen tahap awal"
  ],
  "data": {
    "dokumen_awal": [
      "KTP",
      "KK",
      "Akta kelahiran",
      "Buku nikah",
      "SKCK",
      "Surat sehat"
    ]
  }
}
```

## Batasan privasi
Pengunjung diarahkan untuk tidak mengirim NIK, KTP, KK, password, atau data sangat sensitif melalui chatbot. Dokumen COTA diproses melalui endpoint upload dan pipeline OCR backend, bukan melalui endpoint chat.
