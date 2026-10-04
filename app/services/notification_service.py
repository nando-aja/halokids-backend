from sqlalchemy.orm import Session

from app.db.models.notification import Notifikasi


def create_notification(
    db: Session,
    user_id: int,
    title: str,
    message: str,
) -> Notifikasi:
    item = Notifikasi(
        id_user=user_id,
        judul=title[:150],
        pesan=message[:255],
        is_read=False,
    )
    db.add(item)
    return item


def get_user_notifications(db: Session, user_id: int) -> list[Notifikasi]:
    return (
        db.query(Notifikasi)
        .filter(Notifikasi.id_user == user_id)
        .order_by(Notifikasi.id.desc())
        .all()
    )


def mark_notification_read(
    db: Session,
    user_id: int,
    notification_id: int,
) -> Notifikasi | None:
    """Menandai satu notifikasi milik user sebagai sudah dibaca."""
    item = (
        db.query(Notifikasi)
        .filter(
            Notifikasi.id == notification_id,
            Notifikasi.id_user == user_id,
        )
        .first()
    )

    if item is None:
        return None

    item.is_read = True
    db.commit()
    db.refresh(item)
    return item


def mark_all_notifications_read(db: Session, user_id: int) -> int:
    """Menandai semua notifikasi user sebagai dibaca. Mengembalikan jumlahnya."""
    updated = (
        db.query(Notifikasi)
        .filter(
            Notifikasi.id_user == user_id,
            Notifikasi.is_read.is_(False),
        )
        .update({Notifikasi.is_read: True}, synchronize_session=False)
    )
    db.commit()
    return updated
