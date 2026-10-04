from datetime import date
from decimal import Decimal
from uuid import uuid4

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_masyarakat
from app.db.models.adoption import PengajuanAdopsi
from app.db.models.donation import Donasi
from app.db.models.notification import Notifikasi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.user import User
from app.db.models.volunteer import Relawan
from app.db.models.wishlist import WishlistPanti
from app.schemas.adoption import (
    AdoptionCreate,
    AdoptionEligibilityResponse,
    AdoptionResponse,
    AdditionalDocumentType,
)
from app.schemas.donation import DonationCreate, DonationResponse
from app.schemas.notification import NotificationResponse
from app.schemas.report import ReportCreate, ReportResponse
from app.schemas.user import UserResponse, UserUpdate
from app.schemas.volunteer import VolunteerCreate, VolunteerResponse
from app.services.adoption_eligibility import check_adoption_eligibility
from app.services.ai_service import analyze_adoption_documents
from app.services.ai_service import analyze_transfer_proof as run_transfer_proof_analysis
from app.services.notification_service import (
    create_notification,
    mark_all_notifications_read,
)
from app.services.storage import stored_file_exists


router = APIRouter()

REQUIRED_INITIAL_DOCUMENTS = {
    "akta_kelahiran",
    "buku_nikah",
    "skck",
    "surat_sehat",
}


def validate_initial_documents(
    data: AdoptionCreate,
) -> dict[str, str]:
    if not data.dokumen_ktp or not data.dokumen_kk:
        raise HTTPException(
            status_code=422,
            detail="KTP dan KK wajib diunggah untuk pengajuan awal.",
        )

    docs = data.dokumen_pendukung or {}

    missing = REQUIRED_INITIAL_DOCUMENTS - set(docs.keys())
    if missing:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Dokumen awal COTA belum lengkap.",
                "dokumen_kurang": sorted(missing),
            },
        )

    paths = {
        "ktp": data.dokumen_ktp,
        "kk": data.dokumen_kk,
        **docs,
    }

    missing_files = [
        key
        for key, path in paths.items()
        if not isinstance(path, str)
        or not stored_file_exists(path)
    ]

    if missing_files:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Ada file yang belum ditemukan di local storage.",
                "file_tidak_ditemukan": missing_files,
            },
        )

    return paths


@router.get(
    "/me",
    response_model=UserResponse,
)
def get_my_profile(
    current_user: User = Depends(require_masyarakat),
):
    return current_user


@router.put(
    "/me",
    response_model=UserResponse,
)
def update_my_profile(
    data: UserUpdate,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    changes = data.model_dump(exclude_unset=True)

    for key, value in changes.items():
        setattr(current_user, key, value)

    db.commit()
    db.refresh(current_user)
    return current_user


@router.post(
    "/pengajuan-adopsi/cek-kelayakan",
    response_model=AdoptionEligibilityResponse,
)
def cek_kelayakan_adopsi(
    data: AdoptionCreate,
    current_user: User = Depends(require_masyarakat),
):
    return check_adoption_eligibility(
        birth_date=data.tanggal_lahir_pemohon,
        marriage_date=data.tanggal_pernikahan,
    )


@router.post(
    "/pengajuan-adopsi",
    response_model=AdoptionResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_pengajuan_adopsi(
    data: AdoptionCreate,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    eligibility = check_adoption_eligibility(
        birth_date=data.tanggal_lahir_pemohon,
        marriage_date=data.tanggal_pernikahan,
    )

    if not eligibility["eligible"]:
        raise HTTPException(
            status_code=422,
            detail={
                "message": "Pemohon belum memenuhi filter kelayakan awal.",
                "eligibility": eligibility,
            },
        )

    paths = validate_initial_documents(data)

    item = PengajuanAdopsi(
        id_user=current_user.id,
        nama_pemohon=data.nama_pemohon,
        tanggal_lahir_pemohon=data.tanggal_lahir_pemohon,
        tanggal_pernikahan=data.tanggal_pernikahan,
        dokumen_ktp=data.dokumen_ktp,
        dokumen_kk=data.dokumen_kk,
        dokumen_pendukung=data.dokumen_pendukung,
        status="diajukan",
    )

    db.add(item)
    db.flush()

    ai_result = analyze_adoption_documents(
        document_paths=paths,
        db=db,
        adoption=item,
    )

    item.hasil_ekstraksi_ai = ai_result

    if ai_result["requires_manual_review"]:
        item.status = "menunggu_tinjauan_manual"
        notification_message = (
            f"Pengajuan adopsi #{item.id} diterima dan perlu tinjauan manual "
            "karena ditemukan anomali pada dokumen."
        )
    else:
        notification_message = (
            f"Pengajuan adopsi #{item.id} berhasil dikirim dan menunggu "
            "verifikasi Admin Dinsos."
        )

    create_notification(
        db,
        current_user.id,
        "Pengajuan Adopsi",
        notification_message,
    )

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/pengajuan-adopsi",
    response_model=list[AdoptionResponse],
)
def get_my_adoptions(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return (
        db.query(PengajuanAdopsi)
        .filter(PengajuanAdopsi.id_user == current_user.id)
        .order_by(PengajuanAdopsi.id.desc())
        .all()
    )


@router.get(
    "/pengajuan-adopsi/{adoption_id}",
    response_model=AdoptionResponse,
)
def get_my_adoption_detail(
    adoption_id: int,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PengajuanAdopsi)
        .filter(
            PengajuanAdopsi.id == adoption_id,
            PengajuanAdopsi.id_user == current_user.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(
            status_code=404,
            detail="Pengajuan adopsi tidak ditemukan",
        )

    return item


@router.post(
    "/pengajuan-adopsi/{adoption_id}/dokumen-tambahan"
)
def add_adoption_document(
    adoption_id: int,
    jenis_dokumen: AdditionalDocumentType,
    file: UploadFile = File(...),
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PengajuanAdopsi)
        .filter(
            PengajuanAdopsi.id == adoption_id,
            PengajuanAdopsi.id_user == current_user.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Pengajuan adopsi tidak ditemukan")

    from app.services.storage import save_upload_file

    file_path = save_upload_file(
        file,
        "dokumen_pendukung",
    )

    documents = dict(item.dokumen_pendukung or {})
    documents[jenis_dokumen] = file_path
    item.dokumen_pendukung = documents

    paths = {
        "ktp": item.dokumen_ktp,
        "kk": item.dokumen_kk,
        **documents,
    }
    paths = {key: value for key, value in paths.items() if value}

    item.hasil_ekstraksi_ai = analyze_adoption_documents(
        document_paths=paths,
        db=db,
        adoption=item,
    )

    if item.hasil_ekstraksi_ai["requires_manual_review"]:
        item.status = "menunggu_tinjauan_manual"

    db.commit()
    db.refresh(item)

    return item


@router.get(
    "/pengaduan/saya",
    response_model=list[ReportResponse],
)
def get_my_reports(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return (
        db.query(LaporanPengaduan)
        .filter(LaporanPengaduan.id_user == current_user.id)
        .order_by(LaporanPengaduan.id.desc())
        .all()
    )


@router.post(
    "/donasi",
    response_model=DonationResponse,
    status_code=201,
)
def create_donation(
    data: DonationCreate,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    panti = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id == data.id_panti)
        .first()
    )
    if panti is None:
        raise HTTPException(404, "Panti tidak ditemukan")

    item = Donasi(
        id_user=current_user.id,
        id_panti=data.id_panti,
        jenis_donasi=data.jenis_donasi,
        jumlah_nominal=Decimal("0") if data.jenis_donasi == "barang" else data.jumlah_nominal,
        bukti_transfer=None,
        estimasi_waktu_antar=data.estimasi_waktu_antar,
        id_wishlist=None,
        nama_barang=None,
        jumlah_barang=None,
        satuan_barang=None,
        status_verifikasi="menunggu",
    )

    if data.jenis_donasi == "uang":
        if not data.bukti_transfer:
            raise HTTPException(422, "Bukti transfer wajib untuk donasi uang")

        if not data.bukti_transfer.startswith("storage/bukti_transfer/"):
            raise HTTPException(422, "Bukti transfer harus diunggah melalui /api/upload/bukti-transfer")

        if not stored_file_exists(data.bukti_transfer):
            raise HTTPException(422, "Bukti transfer tidak ditemukan di local storage")

        item.bukti_transfer = data.bukti_transfer

        try:
            proof_result = run_transfer_proof_analysis(
                data.bukti_transfer,
                expected_amount=data.jumlah_nominal,
            )
            needs_manual_check = bool(proof_result["requires_manual_review"])
        except Exception:
            needs_manual_check = True

        item.nama_barang = None

    else:
        if data.bukti_transfer:
            raise HTTPException(422, "Bukti transfer tidak digunakan untuk donasi barang")

        wishlist = None
        if data.id_wishlist is not None:
            wishlist = (
                db.query(WishlistPanti)
                .filter(
                    WishlistPanti.id == data.id_wishlist,
                    WishlistPanti.id_panti == data.id_panti,
                )
                .first()
            )
            if wishlist is None:
                raise HTTPException(422, "Wishlist tidak ditemukan untuk panti yang dipilih")

        item.id_wishlist = data.id_wishlist
        item.nama_barang = data.nama_barang or (wishlist.nama_barang if wishlist else None)
        item.jumlah_barang = data.jumlah_barang
        item.satuan_barang = data.satuan_barang
        item.jumlah_nominal = Decimal("0")
        needs_manual_check = False

        # Jika donor memilih wishlist, jumlah yang didonasikan tidak boleh melebihi
        # kebutuhan yang tersisa. Pengelola tetap memverifikasi pemenuhan final.
        if wishlist is not None:
            remaining = max(wishlist.jumlah_kebutuhan - wishlist.jumlah_terpenuhi, 0)
            if data.jumlah_barang is None:
                raise HTTPException(422, "jumlah_barang wajib diisi")
            if data.jumlah_barang > remaining:
                raise HTTPException(422, f"Jumlah donasi melebihi sisa kebutuhan wishlist ({remaining})")

    db.add(item)

    message = (
        f"Donasi baru untuk panti #{panti.id} menunggu verifikasi."
        + (" Bukti transfer perlu dicek manual." if needs_manual_check else "")
    )

    if panti.id_admin_pengelola:
        create_notification(
            db,
            panti.id_admin_pengelola,
            "Donasi Baru",
            message,
        )

    admin_users = db.query(User).filter(User.peran == "admin").all()
    for admin in admin_users:
        create_notification(db, admin.id, "Donasi Baru", message)

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/donasi",
    response_model=list[DonationResponse],
)
def get_my_donations(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return (
        db.query(Donasi)
        .filter(Donasi.id_user == current_user.id)
        .order_by(Donasi.id.desc())
        .all()
    )


@router.post("/donasi/analisis-bukti")
def analyze_transfer_proof(
    file_path: str,
    nominal_donasi: Decimal | None = None,
    current_user: User = Depends(require_masyarakat),
):
    if not stored_file_exists(file_path) or not file_path.startswith(
        "storage/bukti_transfer/"
    ):
        raise HTTPException(
            422,
            "Bukti transfer tidak ditemukan di local storage",
        )

    return run_transfer_proof_analysis(
        file_path,
        expected_amount=nominal_donasi,
    )


@router.post(
    "/relawan",
    response_model=VolunteerResponse,
    status_code=201,
)
def apply_volunteer(
    data: VolunteerCreate,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    volunteer_data = data

    if not stored_file_exists(
        volunteer_data.dokumen_identitas
    ) or not volunteer_data.dokumen_identitas.startswith(
        "storage/identitas_relawan/"
    ):
        raise HTTPException(
            422,
            "Dokumen identitas relawan tidak ditemukan di storage",
        )

    item = Relawan(
        id_user=current_user.id,
        dokumen_identitas=volunteer_data.dokumen_identitas,
        status="menunggu",
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/relawan",
    response_model=list[VolunteerResponse],
)
def get_my_volunteer_registrations(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return (
        db.query(Relawan)
        .filter(Relawan.id_user == current_user.id)
        .order_by(Relawan.id.desc())
        .all()
    )


@router.get(
    "/notifikasi",
    response_model=list[NotificationResponse],
)
def get_my_notifications(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return (
        db.query(Notifikasi)
        .filter(Notifikasi.id_user == current_user.id)
        .order_by(Notifikasi.id.desc())
        .all()
    )


@router.patch("/notifikasi/read-all")
def mark_all_my_notifications_read(
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    return {
        "diperbarui": mark_all_notifications_read(db, current_user.id),
    }


@router.patch(
    "/notifikasi/{notification_id}/read",
    response_model=NotificationResponse,
)
def mark_notification_read(
    notification_id: int,
    current_user: User = Depends(require_masyarakat),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Notifikasi)
        .filter(
            Notifikasi.id == notification_id,
            Notifikasi.id_user == current_user.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Notifikasi tidak ditemukan")

    item.is_read = True
    db.commit()
    db.refresh(item)
    return item
