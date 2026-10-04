from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_pengelola_panti
from app.db.models.dana import LaporanDana
from app.db.models.donation import Donasi
from app.db.models.gallery import GaleriPanti
from app.db.models.panti import PantiAsuhan
from app.db.models.user import User
from app.db.models.wishlist import WishlistPanti
from app.schemas.dana import DanaResponse
from app.schemas.donation import DonationResponse, DonationStatus
from app.schemas.gallery import GalleryResponse
from app.schemas.notification import NotificationResponse
from app.schemas.panti import PantiResponse, PantiUpdate
from app.schemas.wishlist import WishlistCreate, WishlistResponse, WishlistUpdate
from app.services.ai_service import analyze_transfer_proof
from app.services.notification_service import (
    create_notification,
    get_user_notifications,
    mark_all_notifications_read,
    mark_notification_read,
)
from app.services.storage import get_storage_absolute_path, save_upload_file


router = APIRouter()


def get_managed_panti(
    db: Session,
    current_user: User,
) -> PantiAsuhan:
    panti = (
        db.query(PantiAsuhan)
        .filter(PantiAsuhan.id_admin_pengelola == current_user.id)
        .first()
    )

    if panti is None:
        raise HTTPException(
            404,
            "Panti yang dikelola tidak ditemukan",
        )

    return panti


@router.get(
    "/me",
    response_model=PantiResponse,
)
def get_my_panti(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    return get_managed_panti(db, current_user)


@router.put(
    "/me",
    response_model=PantiResponse,
)
def update_my_panti(
    data: PantiUpdate,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    item = get_managed_panti(db, current_user)

    changes = data.model_dump(
        exclude_unset=True,
        exclude={"id_admin_pengelola", "status_akreditasi"},
    )

    for key, value in changes.items():
        setattr(item, key, value)

    item.id_admin_pengelola = current_user.id
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/wishlist",
    response_model=list[WishlistResponse],
)
def get_wishlist(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    return (
        db.query(WishlistPanti)
        .filter(WishlistPanti.id_panti == panti.id)
        .order_by(WishlistPanti.id.desc())
        .all()
    )


@router.post(
    "/wishlist",
    response_model=WishlistResponse,
    status_code=201,
)
def create_wishlist(
    data: WishlistCreate,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)

    item = WishlistPanti(
        id_panti=panti.id,
        nama_barang=data.nama_barang,
        jumlah_kebutuhan=data.jumlah_kebutuhan,
        jumlah_terpenuhi=0,
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.put(
    "/wishlist/{wishlist_id}",
    response_model=WishlistResponse,
)
def update_wishlist(
    wishlist_id: int,
    data: WishlistUpdate,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    item = (
        db.query(WishlistPanti)
        .filter(
            WishlistPanti.id == wishlist_id,
            WishlistPanti.id_panti == panti.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Wishlist tidak ditemukan")

    changes = data.model_dump(exclude_unset=True)
    for key, value in changes.items():
        setattr(item, key, value)

    if item.jumlah_terpenuhi > item.jumlah_kebutuhan:
        raise HTTPException(
            422,
            "Jumlah terpenuhi tidak boleh melebihi jumlah kebutuhan",
        )

    db.commit()
    db.refresh(item)
    return item


@router.delete("/wishlist/{wishlist_id}")
def delete_wishlist(
    wishlist_id: int,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    item = (
        db.query(WishlistPanti)
        .filter(
            WishlistPanti.id == wishlist_id,
            WishlistPanti.id_panti == panti.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Wishlist tidak ditemukan")

    db.delete(item)
    db.commit()
    return {"message": "Wishlist berhasil dihapus"}


@router.get(
    "/donasi",
    response_model=list[DonationResponse],
)
def get_panti_donations(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    return (
        db.query(Donasi)
        .filter(Donasi.id_panti == panti.id)
        .order_by(Donasi.id.desc())
        .all()
    )


@router.patch(
    "/donasi/{donation_id}/status",
    response_model=DonationResponse,
)
def update_donation_status(
    donation_id: int,
    new_status: DonationStatus,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    item = (
        db.query(Donasi)
        .filter(
            Donasi.id == donation_id,
            Donasi.id_panti == panti.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Donasi tidak ditemukan")

    previous_status = item.status_verifikasi

    if previous_status == "terverifikasi" and new_status != "terverifikasi":
        raise HTTPException(409, "Donasi yang sudah terverifikasi tidak dapat dibatalkan dari dashboard panti")

    if previous_status == "ditolak" and new_status == "terverifikasi":
        raise HTTPException(409, "Donasi yang sudah ditolak tidak dapat diverifikasi ulang; minta donatur membuat pengajuan baru")

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


@router.post(
    "/laporan-dana",
    response_model=DanaResponse,
    status_code=201,
)
def upload_laporan_dana(
    file: UploadFile = File(...),
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)

    item = LaporanDana(
        id_panti=panti.id,
        file_laporan=save_upload_file(
            file,
            "laporan_dana",
        ),
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/laporan-dana",
    response_model=list[DanaResponse],
)
def get_laporan_dana(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    return (
        db.query(LaporanDana)
        .filter(LaporanDana.id_panti == panti.id)
        .order_by(LaporanDana.id.desc())
        .all()
    )


@router.post(
    "/galeri",
    response_model=GalleryResponse,
    status_code=201,
)
def upload_gallery_photo(
    file: UploadFile = File(...),
    deskripsi: str | None = None,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)

    item = GaleriPanti(
        id_panti=panti.id,
        foto=save_upload_file(
            file,
            "galeri_panti",
        ),
        deskripsi=deskripsi,
    )

    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.get(
    "/galeri",
    response_model=list[GalleryResponse],
)
def get_gallery(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    return (
        db.query(GaleriPanti)
        .filter(GaleriPanti.id_panti == panti.id)
        .order_by(GaleriPanti.id.desc())
        .all()
    )


@router.delete("/galeri/{gallery_id}")
def delete_gallery(
    gallery_id: int,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    panti = get_managed_panti(db, current_user)
    item = (
        db.query(GaleriPanti)
        .filter(
            GaleriPanti.id == gallery_id,
            GaleriPanti.id_panti == panti.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Galeri tidak ditemukan")

    db.delete(item)
    db.commit()
    return {"message": "Foto galeri berhasil dihapus"}


def _get_own_donation(
    db: Session,
    current_user: User,
    donation_id: int,
) -> Donasi:
    panti = get_managed_panti(db, current_user)
    item = (
        db.query(Donasi)
        .filter(
            Donasi.id == donation_id,
            Donasi.id_panti == panti.id,
        )
        .first()
    )

    if item is None:
        raise HTTPException(404, "Donasi tidak ditemukan")

    return item


@router.get("/donasi/{donation_id}/bukti")
def download_donation_proof(
    donation_id: int,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    """Pengelola membuka bukti transfer donasi untuk pantinya sendiri."""
    item = _get_own_donation(db, current_user, donation_id)

    # Hanya folder bukti_transfer yang boleh dibuka lewat endpoint ini.
    if not item.bukti_transfer or not item.bukti_transfer.startswith(
        "storage/bukti_transfer/"
    ):
        raise HTTPException(404, "Bukti transfer tidak tersedia")

    absolute_path = get_storage_absolute_path(item.bukti_transfer)

    if not absolute_path.is_file():
        raise HTTPException(404, "File bukti transfer tidak ditemukan")

    return FileResponse(absolute_path)


@router.post("/donasi/{donation_id}/analisis-bukti-ai")
def analyze_donation_proof(
    donation_id: int,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    """Analisis OCR bukti transfer + pencocokan nominal, sebagai alat bantu verifikasi."""
    item = _get_own_donation(db, current_user, donation_id)

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
    "/notifikasi",
    response_model=list[NotificationResponse],
)
def get_panti_notifications(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    return get_user_notifications(db, current_user.id)


@router.patch("/notifikasi/read-all")
def read_all_panti_notifications(
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    return {
        "diperbarui": mark_all_notifications_read(db, current_user.id),
    }


@router.patch(
    "/notifikasi/{notification_id}/read",
    response_model=NotificationResponse,
)
def read_panti_notification(
    notification_id: int,
    current_user: User = Depends(require_pengelola_panti),
    db: Session = Depends(get_db),
):
    item = mark_notification_read(db, current_user.id, notification_id)

    if item is None:
        raise HTTPException(404, "Notifikasi tidak ditemukan")

    return item
