from app.core.security import verify_password
from app.db.database import SessionLocal
from app.db.models.user import User

db = SessionLocal()

user = db.query(User).filter(User.email == "login@halokids.com").first()

if user is None:
    print("USER TIDAK DITEMUKAN")
else:
    print("USER DITEMUKAN")
    print("ID:", user.id)
    print("Email:", user.email)

    hasil = verify_password("HaloKids123", user.password_hash)

    print("Password cocok:", hasil)

db.close()