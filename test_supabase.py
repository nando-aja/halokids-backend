from app.core.config import settings
from app.services.supabase_storage import supabase


print("Supabase URL:", settings.SUPABASE_URL)
print("Private bucket:", settings.SUPABASE_PRIVATE_BUCKET)
print("Public bucket:", settings.SUPABASE_PUBLIC_BUCKET)

try:
    buckets = supabase.storage.list_buckets()

    print("\nKoneksi Supabase berhasil!")
    print("Bucket yang ditemukan:")

    for bucket in buckets:
        print("-", bucket.name)

except Exception as e:
    print("\nKoneksi Supabase gagal!")
    print(e)