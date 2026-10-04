from __future__ import annotations

import os

os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("SECRET_KEY", "local-verification-secret")
os.environ.setdefault("ALGORITHM", "HS256")
os.environ.setdefault("ACCESS_TOKEN_EXPIRE_MINUTES", "30")

from app.main import app


if __name__ == "__main__":
    routes = [
        (route.path, sorted(route.methods or []))
        for route in app.routes
        if getattr(route, "path", None)
    ]
    print(f"Registered routes: {len(routes)}")
    for path, methods in routes:
        print(f"{','.join(methods):20} {path}")
