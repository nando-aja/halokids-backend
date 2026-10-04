from pathlib import Path
from uuid import uuid4

from fastapi import HTTPException, UploadFile, status


BASE_DIR = Path(__file__).resolve().parents[2]
STORAGE_DIR = BASE_DIR / "storage"

STORAGE_FOLDERS = {
    "ktp": STORAGE_DIR / "ktp",
    "kk": STORAGE_DIR / "kk",
    "dokumen_pendukung": STORAGE_DIR / "dokumen_pendukung",
    "bukti_transfer": STORAGE_DIR / "bukti_transfer",
    "identitas_relawan": STORAGE_DIR / "identitas_relawan",
    "laporan_dana": STORAGE_DIR / "laporan_dana",
    "galeri_panti": STORAGE_DIR / "galeri_panti",
    "laporan_pengawasan": STORAGE_DIR / "laporan_pengawasan",
}

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".pdf",
}

MAX_FILE_SIZE = 10 * 1024 * 1024

for folder in STORAGE_FOLDERS.values():
    folder.mkdir(parents=True, exist_ok=True)


# Folder yang berisi dokumen/foto yang memang boleh dilihat publik
# (transparansi panti). Folder lain (KTP, KK, bukti transfer, dll.) bersifat privat.
PUBLIC_FOLDERS = {
    "laporan_dana",
    "galeri_panti",
    "laporan_pengawasan",
}


def save_upload_file(
    file: UploadFile,
    folder_name: str,
    prefix: str = "",
) -> str:
    folder = STORAGE_FOLDERS.get(folder_name)

    if folder is None:
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
    file_path = folder / filename
    total_size = 0

    try:
        with file_path.open("wb") as output:
            while chunk := file.file.read(1024 * 1024):
                total_size += len(chunk)

                if total_size > MAX_FILE_SIZE:
                    file_path.unlink(missing_ok=True)
                    raise HTTPException(
                        status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
                        detail="Ukuran file maksimal 10 MB",
                    )

                output.write(chunk)
    finally:
        file.file.close()

    return (
        Path("storage") / folder_name / filename
    ).as_posix()


def get_storage_absolute_path(relative_path: str) -> Path:
    if not relative_path:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file kosong",
        )

    relative = Path(relative_path)

    if relative.is_absolute():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file harus relatif",
        )

    candidate = (BASE_DIR / relative).resolve()
    storage_root = STORAGE_DIR.resolve()

    try:
        candidate.relative_to(storage_root)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Path file tidak valid",
        )

    return candidate


def stored_file_exists(relative_path: str) -> bool:
    try:
        return get_storage_absolute_path(relative_path).is_file()
    except HTTPException:
        return False


def resolve_public_file(folder_name: str, filename: str) -> Path:
    """
    Mengembalikan path absolut file di folder publik.
    Folder privat (KTP, KK, bukti transfer, dst.) ditolak.
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

    candidate = get_storage_absolute_path(
        (Path("storage") / folder_name / filename).as_posix()
    )

    if not candidate.is_file():
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="File tidak ditemukan",
        )

    return candidate


def list_folder_files(folder_name: str, prefix: str = "") -> list[dict]:
    """Daftar file di satu folder storage (terbaru lebih dulu)."""
    folder = STORAGE_FOLDERS.get(folder_name)

    if folder is None:
        return []

    items = []
    for path in folder.iterdir():
        if path.is_file() and path.name.startswith(prefix):
            items.append(
                {
                    "file": (Path("storage") / folder_name / path.name).as_posix(),
                    "nama_file": path.name,
                    "tanggal_unggah": path.stat().st_mtime,
                }
            )

    items.sort(key=lambda item: item["tanggal_unggah"], reverse=True)
    return items
