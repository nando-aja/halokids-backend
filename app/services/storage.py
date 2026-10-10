from pathlib import Path
from uuid import uuid4
from datetime import datetime
from mimetypes import guess_type

from fastapi import HTTPException, UploadFile, status

from app.core.config import settings
from app.services.supabase_storage import supabase


BASE_DIR = Path(__file__).resolve().parents[2]

# STORAGE_DIR tetap dipertahankan karena masih dipakai
# oleh fitur kalender kunjungan yang menggunakan JSON lokal.
STORAGE_DIR = BASE_DIR / "storage"

# Cache lokal hanya digunakan sementara ketika AI/OCR,
# FileResponse, atau proses lain membutuhkan file berbentuk Path.
# File permanennya tetap berada di Supabase.
STORAGE_CACHE_DIR = BASE_DIR / ".storage_cache"


STORAGE_FOLDERS = {
    "ktp",
    "kk",
    "dokumen_pendukung",
    "bukti_transfer",
    "identitas_relawan",
    "laporan_dana",
    "galeri_panti",
    "laporan_pengawasan",
}


ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
}

MAX_FILE_SIZE = 10 * 1024 * 1024


# Folder yang memang boleh diakses publik.
PUBLIC_FOLDERS = {
    "laporan_dana",
    "galeri_panti",
    "laporan_pengawasan",
}


def _get_bucket_name(folder_name: str) -> str:
    """
    Menentukan bucket berdasarkan jenis folder.
    """
    if folder_name not in STORAGE_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder storage tidak valid",
        )

    if folder_name in PUBLIC_FOLDERS:
        return settings.SUPABASE_PUBLIC_BUCKET

    return settings.SUPABASE_PRIVATE_BUCKET


def _get_object_path(relative_path: str) -> tuple[str, str]:
    """
    Mengubah path aplikasi:

        storage/ktp/abc.jpg

    menjadi:

        bucket = halokids-private
        object_path = ktp/abc.jpg
    """

    if not relative_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file kosong",
        )

    normalized = relative_path.replace("\\", "/")

    if not normalized.startswith("storage/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file harus berada di dalam storage",
        )

    object_path = normalized[len("storage/"):]

    path = Path(object_path)

    if len(path.parts) < 2:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file tidak valid",
        )

    folder_name = path.parts[0]

    if folder_name not in STORAGE_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder storage tidak valid",
        )

    # Cegah path traversal
    if any(part in {"..", "."} for part in path.parts):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file tidak valid",
        )

    return _get_bucket_name(folder_name), object_path


def save_upload_file(
    file: UploadFile,
    folder_name: str,
    prefix: str = "",
) -> str:
    """
    Upload file ke Supabase Storage.

    Path yang dikembalikan tetap menggunakan format lama:

        storage/ktp/abc.jpg

    supaya database dan route HaloKids yang sudah ada
    tidak perlu langsung diubah.
    """

    if folder_name not in STORAGE_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Folder storage tidak valid",
        )

    if not file.filename:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama file tidak ditemukan",
        )

    extension = Path(file.filename).suffix.lower()

    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Format file harus JPG, JPEG, PNG, atau PDF",
        )

    filename = f"{prefix}{uuid4().hex}{extension}"

    object_path = f"{folder_name}/{filename}"
    bucket_name = _get_bucket_name(folder_name)

    # Baca file secara bertahap supaya ukuran bisa dibatasi.
    chunks = []
    total_size = 0

    try:
        while chunk := file.file.read(1024 * 1024):
            total_size += len(chunk)

            if total_size > MAX_FILE_SIZE:
                raise HTTPException(
                    status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                    detail="Ukuran file maksimal 10 MB",
                )

            chunks.append(chunk)

        file_bytes = b"".join(chunks)

        local_path = (BASE_DIR / "storage" / folder_name / filename).resolve()
        local_path.parent.mkdir(parents=True, exist_ok=True)
        local_path.write_bytes(file_bytes)

        content_type = (
            file.content_type
            or guess_type(file.filename)[0]
            or "application/octet-stream"
        )

        # Pastikan Supabase menerima MIME type yang sesuai.
        if extension in {".jpg", ".jpeg"}:
            content_type = "image/jpeg"
        elif extension == ".png":
            content_type = "image/png"
        elif extension == ".pdf":
            content_type = "application/pdf"

        supabase.storage.from_(bucket_name).upload(
            path=object_path,
            file=file_bytes,
            file_options={
                "content-type": content_type,
                "cache-control": "3600",
                "upsert": "false",
            },
        )

    except HTTPException:
        raise

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Gagal mengupload file ke Supabase: {exc}",
        )

    finally:
        file.file.close()

    # Tetap menggunakan format path lama agar model DB / route
    # HaloKids tidak langsung rusak.
    return f"storage/{object_path}"


def _get_cache_path(relative_path: str) -> Path:
    """
    Mengubah logical path:

        storage/ktp/abc.jpg

    menjadi cache lokal:

        .storage_cache/ktp/abc.jpg
    """

    normalized = relative_path.replace("\\", "/")

    if not normalized.startswith("storage/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file tidak valid",
        )

    object_path = normalized[len("storage/"):]

    cache_path = (STORAGE_CACHE_DIR / object_path).resolve()
    cache_root = STORAGE_CACHE_DIR.resolve()

    try:
        cache_path.relative_to(cache_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file tidak valid",
        )

    return cache_path


def get_storage_absolute_path(relative_path: str) -> Path:
    """
    Mendapatkan file dalam bentuk Path lokal.

    File permanen berada di Supabase.
    Jika belum ada di cache lokal, file akan didownload
    dari Supabase terlebih dahulu.

    Fungsi ini sengaja mempertahankan nama lama karena
    AI/OCR HaloKids menggunakannya.
    """

    bucket_name, object_path = _get_object_path(relative_path)

    cache_path = _get_cache_path(relative_path)

    if cache_path.is_file():
        return cache_path

    cache_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        file_bytes = (
            supabase.storage
            .from_(bucket_name)
            .download(object_path)
        )

        cache_path.write_bytes(file_bytes)

    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"File tidak ditemukan di Supabase Storage: {exc}",
        )

    return cache_path


def stored_file_exists(relative_path: str) -> bool:
    """
    Mengecek apakah file tersedia di Supabase.
    """
    try:
        path = get_storage_absolute_path(relative_path)
        return path.is_file()
    except HTTPException:
        return False


def resolve_public_file(folder_name: str, filename: str) -> Path:
    """
    Mengembalikan file publik sebagai Path lokal cache.

    Hanya folder publik yang diperbolehkan.
    """

    if folder_name not in PUBLIC_FOLDERS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File tidak ditemukan",
        )

    if filename != Path(filename).name:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nama file tidak valid",
        )

    relative_path = (
        Path("storage")
        / folder_name
        / filename
    ).as_posix()

    path = get_storage_absolute_path(relative_path)

    if not path.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File tidak ditemukan",
        )

    return path


def list_folder_files(
    folder_name: str,
    prefix: str = "",
) -> list[dict]:
    """
    Mengambil daftar file dari Supabase Storage terlebih dahulu agar fitur berjalan
    tanpa tergantung sepenuhnya pada Supabase, lalu fallback ke Supabase bila perlu.
    """

    if folder_name not in STORAGE_FOLDERS:
        return []

    local_dir = (BASE_DIR / "storage" / folder_name).resolve()
    if local_dir.is_dir():
        files: list[dict] = []
        seen: set[str] = set()
        for path in sorted(local_dir.iterdir(), key=lambda item: item.stat().st_mtime, reverse=True):
            if not path.is_file():
                continue
            filename = path.name
            if not filename.startswith(prefix):
                continue
            relative_path = (Path("storage") / folder_name / filename).as_posix()
            if relative_path in seen:
                continue
            seen.add(relative_path)
            files.append(
                {
                    "file": relative_path,
                    "nama_file": filename,
                    "tanggal_unggah": path.stat().st_mtime,
                }
            )
        if files:
            return files

    bucket_name = _get_bucket_name(folder_name)

    try:
        items = (
            supabase.storage
            .from_(bucket_name)
            .list(
                folder_name,
                {
                    "limit": 100,
                    "offset": 0,
                },
            )
        )

    except Exception:
        return []

    result = []
    seen: set[str] = set()

    for item in items:
        filename = item.get("name")

        if not filename:
            continue

        if not filename.startswith(prefix):
            continue

        # Abaikan kemungkinan entry folder.
        if item.get("id") is None and item.get("metadata") is None:
            continue

        updated_at = item.get("updated_at") or item.get("created_at")

        timestamp = 0

        if updated_at:
            try:
                timestamp = datetime.fromisoformat(
                    updated_at.replace("Z", "+00:00")
                ).timestamp()
            except (ValueError, TypeError):
                timestamp = 0

        relative_path = (
            Path("storage")
            / folder_name
            / filename
        ).as_posix()

        if relative_path in seen:
            continue
        seen.add(relative_path)

        result.append(
            {
                "file": relative_path,
                "nama_file": filename,
                "tanggal_unggah": timestamp,
            }
        )

    result.sort(
        key=lambda item: item["tanggal_unggah"],
        reverse=True,
    )

    return result

def delete_stored_file(relative_path: str) -> None:
    """Delete a stored object and its local cache, if present."""
    bucket_name, object_path = _get_object_path(relative_path)
    if supabase is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase Storage belum dikonfigurasi",
        )
    try:
        supabase.storage.from_(bucket_name).remove([object_path])
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Gagal menghapus file dari Supabase Storage",
        ) from exc

    local_path = (BASE_DIR / relative_path).resolve()
    storage_root = (BASE_DIR / "storage").resolve()
    if storage_root not in local_path.parents:
        raise HTTPException(status_code=400, detail="Path file tidak valid")
    local_path.unlink(missing_ok=True)
    cache_path = _get_cache_path(relative_path)
    cache_path.unlink(missing_ok=True)
