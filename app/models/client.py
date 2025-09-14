from __future__ import annotations
from datetime import datetime
from sqlalchemy import String, Integer, DateTime, func, text
from sqlalchemy.orm import Mapped, mapped_column
from app.core.database import Base

class Client(Base):
    __tablename__ = "clients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)

    first_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    last_name:  Mapped[str | None] = mapped_column(String(100), nullable=True)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    company: Mapped[str | None] = mapped_column(String(255), nullable=True)
    phone: Mapped[str | None] = mapped_column(String(32), nullable=True)

    # --- Adresse structurée ---
    address_line1: Mapped[str | None] = mapped_column(String(200), nullable=True)
    address_line2: Mapped[str | None] = mapped_column(String(200), nullable=True)
    postal_code:   Mapped[str | None] = mapped_column(String(20), nullable=True)
    city:          Mapped[str | None] = mapped_column(String(100), nullable=True)
    state:         Mapped[str | None] = mapped_column(String(100), nullable=True)
    country_code:  Mapped[str | None] = mapped_column(String(2), nullable=True)  # ISO 3166-1 alpha-2

    created_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    orders_count: Mapped[int] = mapped_column(Integer, server_default=text("0"), nullable=False)
    last_order_date: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Verrou optimiste
    version: Mapped[int] = mapped_column(Integer, nullable=False, server_default=text("1"))
    __mapper_args__ = {
        "version_id_col": version,
        "version_id_generator": lambda v: (v or 0) + 1,
    }
