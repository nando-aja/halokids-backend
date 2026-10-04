# HaloKids Custom Agentic AI — Source Code

Fitur ini dibuat sendiri di Python dan tidak menggunakan OpenAI, Gemini, Claude, atau API AI eksternal.

## File utama

### 1. `app/services/agentic_chat.py`
Engine agent: intent detection, entity extraction, tool routing, DB tools, response generation, dan short-term session memory.

### 2. `app/schemas/ai_chat.py`
Schema request/response untuk chatbot.

### 3. `app/api/routes/ai.py`
REST endpoint:
- `GET /api/public/ai/health`
- `POST /api/public/ai/chat`

### 4. `app/main.py`
Mendaftarkan router AI pada `/api/public/ai` dan CORS untuk frontend React.

### 5. `app/core/config.py`
Membaca `FRONTEND_ORIGINS` dari `.env`.

## Arsitektur

```text
React Landing Page
      |
      | POST message + session_id
      v
FastAPI /api/public/ai/chat
      |
      v
HaloKidsPublicAgent
      |
      +--> Intent Detection
      |
      +--> Entity Extraction
      |
      +--> Tool Selection
      |       |
      |       +--> Database: Panti
      |       +--> Database: Tiket
      |       +--> Database: Statistik
      |       +--> Business Rule: Kelayakan Adopsi
      |
      +--> Response Generation
      |
      v
JSON response
      |
      v
Chatbot di Landing Page
```

## Topik yang dapat dilayani
- Pengaduan
- Lacak tiket
- Adopsi/COTA
- Kelayakan awal
- Dokumen COTA
- Direktori panti
- Donasi
- Relawan
- Statistik publik
- Privasi
- Jalur darurat

## Contoh request

```json
{
  "message": "Apa syarat dokumen awal COTA?",
  "session_id": "guest-abc12345"
}
```

## Contoh respons

```json
{
  "session_id": "guest-abc12345",
  "message": "Untuk tahap awal pengajuan COTA pada web HaloKids, siapkan KTP, KK, akta kelahiran, buku nikah, SKCK, dan surat sehat.",
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
