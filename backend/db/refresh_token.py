import uuid
from datetime import datetime , timezone
from sqlalchemy import ForeignKey , DateTime
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped , mapped_column , relationship
from backend.core.database import Base

class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    id : Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4
    )

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id" , ondelete="CASCADE"),
        nullable=False,
        unique=True 
        # Each User will have only one refresh token
    )

    token : Mapped[str] = mapped_column(
        nullable=False,
        unique=True
    )
    expires_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        nullable=False
    )

    created_at: Mapped[DateTime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )