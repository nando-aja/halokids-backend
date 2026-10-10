from datetime import date, datetime, time, timedelta
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_admin
from app.db.models.adoption import PengajuanAdopsi
from app.db.models.donation import Donasi
from app.db.models.dana import LaporanDana
from app.db.models.gallery import GaleriPanti
from app.db.models.notification import Notifikasi
from app.db.models.panti import PantiAsuhan
from app.db.models.report import LaporanPengaduan
from app.db.models.user import User
from app.db.models.volunteer import Relawan
from app.db.models.wishlist import WishlistPanti
from app.schemas.adoption import AdoptionResponse, AdoptionStatus
from app.schemas.calendar import VisitEventCreate, VisitEventResponse, VisitEventUpdate
from app.schemas.donation import DonationResponse, DonationStatus
from app.schemas.notification import NotificationResponse
from app.schemas.panti import PantiCreate, PantiResponse, PantiUpdate
from app.schemas.report import ReportResponse, ReportStatus
from app.schemas.user import UserResponse, UserRoleUpdate
from app.schemas.volunteer import VolunteerResponse, VolunteerStatus, VolunteerUpdate
from app.services.ai_service import analyze_adoption_documents, analyze_transfer_proof
from app.services import visit_calendar
from app.services.notification_service import (
    create_notification,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.services.storage import get_storage_absolute_path, save_upload_file


router = APIRouter()


def validate_manager(
    db: Session,
    user_id: int | None,
) -> None:
    if user_id is None:
        return

    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None or user.peran != "pengelola-panti":
        raise HTTPException(
            422,
            "id_admin_pengelola harus mengarah ke user pengelola-panti",
        )


@router.get(
    "/users",
    response_model=list[UserResponse],
)
def get_users(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(User)
        .order_by(User.id.desc())
        .all()
    )


@router.patch(
    "/users/{user_id}/role",
    response_model=UserResponse,
)
def update_user_role(
    user_id: int,
    data: UserRoleUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    user = (
        db.query(User)
        .filter(User.id == user_id)
        .first()
    )

    if user is None:
        raise HTTPException(404, "User tidak ditemukan")

    if (
        user.id == current_user.id
        and data.peran != "admin"
    ):
        raise HTTPException(
            400,
            "Role admin akun yang sedang dipakai tidak boleh diturunkan",
        )

    user.peran = data.peran
    db.commit()
    db.refresh(user)
    return user


@router.get(
    "/panti",
    response_model=list[PantiResponse],
)
def get_admin_panti(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(PantiAsuhan).order_by(PantiAsuhan.id.desc()).all()


@router.post(
    "/panti",
    response_model=PantiResponse,
    status_code=201,
)
def create_panti(
    data: PantiCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    validate_manager(db, data.id_admin_pengelola)
    item = PantiAsuhan(**data.model_dump())
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/panti/{panti_id}",
    response_model=PantiResponse,
)
def get_admin_panti_detail(
    panti_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id == panti_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Panti tidak ditemukan")

    return item


@router.put(
    "/panti/{panti_id}",
    response_model=PantiResponse,
)
def update_panti(
    panti_id: int,
    data: PantiUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id == panti_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Panti tidak ditemukan")

    validate_manager(db, data.id_admin_pengelola)

    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(item, key, value)

    db.commit()
    db.refresh(item)
    return item


@router.delete("/panti/{panti_id}")
def delete_panti(
    panti_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id == panti_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Panti tidak ditemukan")

    db.delete(item)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409,
            "Panti tidak dapat dihapus karena masih memiliki data yang berelasi",
        )

    return {"message": "Panti berhasil dihapus"}


@router.get(
    "/pengajuan-adopsi",
    response_model=list[AdoptionResponse],
)
def get_all_adoptions(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(PengajuanAdopsi)
        .order_by(PengajuanAdopsi.id.desc())
        .all()
    )


@router.get(
    "/pengajuan-adopsi/{adoption_id}",
    response_model=AdoptionResponse,
)
def get_adoption_detail(
    adoption_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PengajuanAdopsi)
        .filter(PengajuanAdopsi.id == adoption_id)
        .first()
    )

    if item is None:
        raise HTTPException(
            404,
            "Pengajuan adopsi tidak ditemukan",
        )

    return item


@router.post("/pengajuan-adopsi/{adoption_id}/analisis-ai")
def reanalyze_adoption(
    adoption_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PengajuanAdopsi)
        .filter(PengajuanAdopsi.id == adoption_id)
        .first()
    )

    if item is None:
        raise HTTPException(
            404,
            "Pengajuan adopsi tidak ditemukan",
        )

    documents = {
        "ktp": item.dokumen_ktp,
        "kk": item.dokumen_kk,
        **(item.dokumen_pendukung or {}),
    }
    documents = {
        key: value
        for key, value in documents.items()
        if value
    }

    result = analyze_adoption_documents(
        document_paths=documents,
        db=db,
        adoption=item,
    )

    item.hasil_ekstraksi_ai = result

    if result["requires_manual_review"]:
        item.status = "menunggu_tinjauan_manual"

    db.commit()
    db.refresh(item)

    return {
        "id_pengajuan": item.id,
        "status": item.status,
        "hasil_ekstraksi_ai": result,
    }


@router.patch(
    "/pengajuan-adopsi/{adoption_id}/status",
    response_model=AdoptionResponse,
)
def update_adoption_status(
    adoption_id: int,
    new_status: AdoptionStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(PengajuanAdopsi)
        .filter(PengajuanAdopsi.id == adoption_id)
        .first()
    )

    if item is None:
        raise HTTPException(
            404,
            "Pengajuan adopsi tidak ditemukan",
        )

    item.status = new_status

    create_notification(
        db,
        item.id_user,
        "Status Pengajuan Adopsi",
        f"Status pengajuan adopsi #{item.id} berubah menjadi {new_status}.",
    )

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/pengaduan",
    response_model=list[ReportResponse],
)
def get_reports(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(LaporanPengaduan)
        .order_by(LaporanPengaduan.id.desc())
        .all()
    )


@router.patch(
    "/pengaduan/{report_id}/status",
    response_model=ReportResponse,
)
def update_report_status(
    report_id: int,
    new_status: ReportStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(LaporanPengaduan)
        .filter(LaporanPengaduan.id == report_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Laporan tidak ditemukan")

    item.status = new_status

    if item.id_user:
        create_notification(
            db,
            item.id_user,
            "Status Laporan",
            f"Status laporan {item.kode_tiket} berubah menjadi {new_status}.",
        )

    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/donasi",
    response_model=list[DonationResponse],
)
def get_donations(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Donasi).order_by(Donasi.id.desc()).all()


@router.patch(
    "/donasi/{donation_id}/status",
    response_model=DonationResponse,
)
def update_donation_status(
    donation_id: int,
    new_status: DonationStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Donasi)
        .filter(Donasi.id == donation_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Donasi tidak ditemukan")

    previous_status = item.status_verifikasi
    if previous_status == "terverifikasi" and new_status != "terverifikasi":
        raise HTTPException(409, "Donasi yang sudah terverifikasi tidak dapat dibatalkan")
    if previous_status == "ditolak" and new_status == "terverifikasi":
        raise HTTPException(409, "Donasi yang sudah ditolak tidak dapat diverifikasi ulang; buat donasi baru")

    item.status_verifikasi = new_status

    if (
        new_status == "terverifikasi"
        and previous_status != "terverifikasi"
        and item.jenis_donasi == "barang"
        and item.id_wishlist is not None
        and item.jumlah_barang
    ):
        wishlist = (
            db.query(WishlistPanti)
            .filter(WishlistPanti.id == item.id_wishlist)
            .first()
        )
        if wishlist is not None:
            wishlist.jumlah_terpenuhi = min(
                wishlist.jumlah_kebutuhan,
                wishlist.jumlah_terpenuhi + item.jumlah_barang,
            )

    create_notification(
        db,
        item.id_user,
        "Status Donasi",
        f"Status donasi #{item.id} berubah menjadi {new_status}.",
    )

    db.commit()
    db.refresh(item)
    return item


@router.post("/donasi/{donation_id}/analisis-bukti-ai")
def analyze_donation_proof(
    donation_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Donasi)
        .filter(Donasi.id == donation_id)
        .first()
    )

    if item is None:
        raise HTTPException(404, "Donasi tidak ditemukan")

    if not item.bukti_transfer:
        raise HTTPException(
            422,
            "Donasi ini tidak memiliki bukti transfer",
        )

    return analyze_transfer_proof(
        item.bukti_transfer,
        expected_amount=(
            item.jumlah_nominal if item.jenis_donasi == "uang" else None
        ),
    )


@router.get(
    "/relawan",
    response_model=list[VolunteerResponse],
)
def get_volunteers(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return db.query(Relawan).order_by(Relawan.id.desc()).all()


@router.patch(
    "/relawan/{volunteer_id}/status",
    response_model=VolunteerResponse,
)
def update_volunteer_status(
    volunteer_id: int,
    new_status: VolunteerStatus,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = (
        db.query(Relawan)
        .filter(Relawan.id == volunteer_id)
        .first()
    )

    if item is None:
        raise HTTPException(
            404,
            "Data relawan tidak ditemukan",
        )

    item.status = new_status

    create_notification(
        db,
        item.id_user,
        "Status Relawan",
        f"Status pendaftaran relawan #{item.id} berubah menjadi {new_status}.",
    )

    db.commit()
    db.refresh(item)
    return item


@router.put(
    "/relawan/{volunteer_id}",
    response_model=VolunteerResponse,
)
def update_volunteer(
    volunteer_id: int,
    data: VolunteerUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(Relawan).filter(Relawan.id == volunteer_id).first()
    if item is None:
        raise HTTPException(404, "Data relawan tidak ditemukan")
    updates = data.model_dump(exclude_unset=True)
    if updates.get("id_panti") is not None:
        panti = db.query(PantiAsuhan).filter(PantiAsuhan.id == updates["id_panti"]).first()
        if panti is None:
            raise HTTPException(404, "Panti tujuan tidak ditemukan")
        updates.setdefault("panti_tujuan", panti.nama_panti)
    for key, value in updates.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/relawan/{volunteer_id}")
def delete_volunteer(
    volunteer_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = db.query(Relawan).filter(Relawan.id == volunteer_id).first()
    if item is None:
        raise HTTPException(404, "Data relawan tidak ditemukan")
    db.delete(item)
    db.commit()
    return {"message": "Data relawan berhasil dihapus", "id": volunteer_id}


@router.get("/dashboard/stats")
def get_dashboard_stats(
    start_date: date | None = None,
    end_date: date | None = None,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    start_dt = (
        datetime.combine(start_date, time.min)
        if start_date
        else None
    )

    end_exclusive = (
        datetime.combine(end_date + timedelta(days=1), time.min)
        if end_date
        else None
    )

    def apply_range(query, column):
        if start_dt:
            query = query.filter(column >= start_dt)
        if end_exclusive:
            query = query.filter(column < end_exclusive)
        return query

    adoption_query = apply_range(
        db.query(PengajuanAdopsi),
        PengajuanAdopsi.tanggal_pengajuan,
    )
    report_query = apply_range(
        db.query(LaporanPengaduan),
        LaporanPengaduan.tanggal_lapor,
    )
    donation_query = apply_range(
        db.query(Donasi),
        Donasi.tanggal_donasi,
    )

    return {
        "periode": {
            "mulai": start_date,
            "selesai": end_date,
        },
        "jumlah_user": db.query(func.count(User.id)).scalar() or 0,
        "jumlah_panti": db.query(func.count(PantiAsuhan.id)).scalar() or 0,
        "jumlah_pengajuan_adopsi": adoption_query.count(),
        "jumlah_pengaduan": report_query.count(),
        "jumlah_donasi": donation_query.count(),
        "jumlah_relawan": db.query(func.count(Relawan.id)).scalar() or 0,
        "jumlah_panti_terkelola": db.query(func.count(PantiAsuhan.id)).filter(PantiAsuhan.id_admin_pengelola.isnot(None)).scalar() or 0,
    }


@router.post("/panti/{panti_id}/laporan-pengawasan")
def upload_laporan_pengawasan(
    panti_id: int,
    file: UploadFile = File(...),
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    panti = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id == panti_id)
        .first()
    )

    if panti is None:
        raise HTTPException(404, "Panti tidak ditemukan")

    # Prefix panti{id}_ membuat file dapat dikelompokkan per panti tanpa
    # menambah tabel baru (daftar publik: GET /api/public/panti/{id}/laporan-pengawasan).
    path = save_upload_file(
        file,
        "laporan_pengawasan",
        prefix=f"panti{panti_id}_",
    )

    return {
        "message": "Laporan pengawasan berhasil diupload",
        "id_panti": panti_id,
        "file_laporan": path,
        "catatan": "File disimpan di Supabase Storage dan dikelompokkan per panti lewat prefix nama file.",
    }


@router.get(
    "/notifikasi",
    response_model=list[NotificationResponse],
)
def get_admin_notifications(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return (
        db.query(Notifikasi)
        .filter(Notifikasi.id_user == current_user.id)
        .order_by(Notifikasi.id.desc())
        .all()
    )


@router.patch(
    "/notifikasi/read-all",
)
def read_all_admin_notifications(
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    return {
        "diperbarui": mark_all_notifications_read(db, current_user.id),
    }


@router.patch(
    "/notifikasi/{notification_id}/read",
    response_model=NotificationResponse,
)
def read_admin_notification(
    notification_id: int,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    item = mark_notification_read(db, current_user.id, notification_id)

    if item is None:
        raise HTTPException(404, "Notifikasi tidak ditemukan")

    return item



def _admin_file_is_referenced(db: Session, relative_path: str) -> bool:
    """Pastikan admin hanya membuka file yang memang direferensikan aplikasi."""
    normalized = relative_path.replace("\\", "/")

    # Laporan pengawasan tidak memiliki kolom DB khusus; prefix panti adalah
    # satu-satunya indeks yang dipakai sesuai desain 10 tabel.
    if normalized.startswith("storage/laporan_pengawasan/"):
        return Path(normalized).name.startswith("panti")

    if db.query(Donasi.id).filter(Donasi.bukti_transfer == normalized).first():
        return True

    if db.query(Relawan.id).filter(Relawan.dokumen_identitas == normalized).first():
        return True

    if db.query(LaporanDana.id).filter(LaporanDana.file_laporan == normalized).first():
        return True

    if db.query(GaleriPanti.id).filter(GaleriPanti.foto == normalized).first():
        return True

    adoptions = db.query(PengajuanAdopsi.dokumen_ktp, PengajuanAdopsi.dokumen_kk, PengajuanAdopsi.dokumen_pendukung).all()
    for ktp, kk, supporting in adoptions:
        if ktp == normalized or kk == normalized:
            return True
        if isinstance(supporting, dict) and normalized in supporting.values():
            return True

    return False

@router.get("/pengajuan-adopsi/{adoption_id}/dokumen/{dokumen_key}")
def download_adoption_document(
    adoption_id: int,
    dokumen_key: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """Admin membuka dokumen COTA tertentu setelah authorization terhadap record."""
    item = db.query(PengajuanAdopsi).filter(PengajuanAdopsi.id == adoption_id).first()
    if item is None:
        raise HTTPException(404, "Pengajuan adopsi tidak ditemukan")

    allowed = {"ktp": item.dokumen_ktp, "kk": item.dokumen_kk}
    if dokumen_key in (item.dokumen_pendukung or {}):
        allowed[dokumen_key] = (item.dokumen_pendukung or {}).get(dokumen_key)

    relative_path = allowed.get(dokumen_key)
    if not relative_path:
        raise HTTPException(404, "Dokumen tidak ditemukan")

    absolute_path = get_storage_absolute_path(relative_path)
    if not absolute_path.is_file():
        raise HTTPException(404, "File dokumen tidak ditemukan")

    return FileResponse(absolute_path)

@router.get("/files")
def download_stored_file(
    path: str,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    """
    Admin membuka dokumen unggahan (KTP, KK, SKCK, bukti transfer, dst.)
    untuk verifikasi manual. Path berasal dari kolom dokumen_* / bukti_transfer
    dan dibatasi hanya di dalam folder storage.
    """
    absolute_path = get_storage_absolute_path(path)

    if not _admin_file_is_referenced(db, path):
        raise HTTPException(404, "File tidak ditemukan")

    if not absolute_path.is_file():
        raise HTTPException(404, "File tidak ditemukan")

    return FileResponse(absolute_path)


def _ensure_panti_exists(db: Session, panti_id: int | None) -> None:
    if panti_id is None:
        return

    exists = (
        db.query(PantiAsuhan.id)
        .filter(PantiAsuhan.id == panti_id)
        .first()
    )

    if exists is None:
        raise HTTPException(404, "Panti tidak ditemukan")


@router.get(
    "/kalender-kunjungan",
    response_model=list[VisitEventResponse],
)
def get_visit_calendar(
    current_user: User = Depends(require_admin),
):
    return visit_calendar.list_events()


@router.post(
    "/kalender-kunjungan",
    response_model=VisitEventResponse,
    status_code=201,
)
def create_visit_event(
    data: VisitEventCreate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    _ensure_panti_exists(db, data.id_panti)
    return visit_calendar.create_event(data.model_dump())


@router.put(
    "/kalender-kunjungan/{event_id}",
    response_model=VisitEventResponse,
)
def update_visit_event(
    event_id: int,
    data: VisitEventUpdate,
    current_user: User = Depends(require_admin),
    db: Session = Depends(get_db),
):
    changes = data.model_dump(exclude_unset=True)
    _ensure_panti_exists(db, changes.get("id_panti"))

    item = visit_calendar.update_event(event_id, changes)

    if item is None:
        raise HTTPException(404, "Jadwal kunjungan tidak ditemukan")

    return item


@router.delete("/kalender-kunjungan/{event_id}")
def delete_visit_event(
    event_id: int,
    current_user: User = Depends(require_admin),
):
    if not visit_calendar.delete_event(event_id):
        raise HTTPException(404, "Jadwal kunjungan tidak ditemukan")

    return {"message": "Jadwal kunjungan dihapus"}
