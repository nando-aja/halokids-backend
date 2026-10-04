from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from app.api.deps import require_masyarakat
from app.db.models.user import User
from app.schemas.adoption import AdditionalDocumentType
from app.services.ai_service import analyze_adoption_documents, analyze_transfer_proof
from app.services.storage import save_upload_file


router = APIRouter()


@router.post("/ktp-adopsi")
def upload_ktp_adopsi(
    ktp: UploadFile = File(...),
    kk: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
):
    ktp_path = save_upload_file(ktp, "ktp")
    kk_path = save_upload_file(kk, "kk")

    ai_preview = analyze_adoption_documents({
        "ktp": ktp_path,
        "kk": kk_path,
    })

    return {
        "message": "Dokumen KTP dan KK berhasil diupload",
        "id_user": current_user.id,
        "dokumen_ktp": ktp_path,
        "dokumen_kk": kk_path,
        "ai_preview": ai_preview,
    }


@router.post("/dokumen-awal-adopsi")
def upload_dokumen_awal_adopsi(
    akta_kelahiran: UploadFile = File(...),
    buku_nikah: UploadFile = File(...),
    skck: UploadFile = File(...),
    surat_sehat: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
):
    files = {
        "akta_kelahiran": akta_kelahiran,
        "buku_nikah": buku_nikah,
        "skck": skck,
        "surat_sehat": surat_sehat,
    }

    hasil_upload = {
        name: save_upload_file(
            file,
            "dokumen_pendukung",
        )
        for name, file in files.items()
    }

    return {
        "message": "Dokumen awal COTA berhasil diupload",
        "id_user": current_user.id,
        "dokumen_pendukung": hasil_upload,
    }


@router.post("/dokumen-tambahan-adopsi")
def upload_dokumen_tambahan_adopsi(
    jenis_dokumen: AdditionalDocumentType,
    file: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
):
    path = save_upload_file(
        file,
        "dokumen_pendukung",
    )

    return {
        "message": "Dokumen tambahan berhasil diupload",
        "id_user": current_user.id,
        "jenis_dokumen": jenis_dokumen,
        "file": path,
    }


@router.post("/bukti-transfer")
def upload_bukti_transfer(
    file: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
):
    path = save_upload_file(
        file,
        "bukti_transfer",
    )

    ai_result = analyze_transfer_proof(path)

    return {
        "message": "Bukti transfer berhasil diupload",
        "id_user": current_user.id,
        "bukti_transfer": path,
        "ai_preview": ai_result,
    }


@router.post("/identitas-relawan")
def upload_identitas_relawan(
    file: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
):
    path = save_upload_file(
        file,
        "identitas_relawan",
    )

    return {
        "message": "Dokumen identitas relawan berhasil diupload",
        "id_user": current_user.id,
        "dokumen_identitas": path,
    }
