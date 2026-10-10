"""Supabase Storage client. Optional during local API/tests; required for uploads."""
from supabase import Client, create_client

from app.core.config import settings


supabase: Client | None = None
if settings.SUPABASE_URL and settings.SUPABASE_SECRET_KEY:
    supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_SECRET_KEY)
