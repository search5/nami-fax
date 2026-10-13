"""NetworkPrinters: directly attached network printers (B track, group 1)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class NetworkPrinters(Base):
    # Table and column names are kept exactly as the legacy SQL spells them.
    __tablename__ = "NetworkPrinters"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    protocol: Mapped[Optional[str]] = mapped_column(String(10), server_default="RAW")  # RAW, LPD, IPP
    host: Mapped[str] = mapped_column(String(255), nullable=False)
    port: Mapped[Optional[int]] = mapped_column(Integer, server_default="9100")
    queue_name: Mapped[Optional[str]] = mapped_column(String(255))
    description: Mapped[Optional[str]] = mapped_column(Text)
