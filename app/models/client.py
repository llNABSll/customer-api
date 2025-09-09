from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String, nullable=False)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    company: Mapped[str | None] = mapped_column(String, nullable=True)
    phone: Mapped[str | None] = mapped_column(String, nullable=True)

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda v: (v or 0) + 1,
    }