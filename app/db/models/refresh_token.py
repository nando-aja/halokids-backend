
from sqlalchemy import (
    Column,
    BigInteger,
    Integer,
    String,
    DateTime,
    TIMESTAMP,
    ForeignKey,
    text,
)

from app.db.database import Base


class AuthRefreshToken(Base):
    __tablename__ = "auth_refresh_tokens"

    id = Column(BigInteger, primary_key=True, autoincrement=True)

    user_id = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    token_hash = Column(String(255), unique=True, nullable=False)
    expires_at = Column(DateTime, nullable=False)
    revoked_at = Column(DateTime, nullable=True)

    created_at = Column(
        TIMESTAMP,
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP"),
    )
