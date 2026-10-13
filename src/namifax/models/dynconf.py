"""DynConf: caller IDs the fax server rejects (B track, group 2)."""

from __future__ import annotations

from typing import Optional

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class DynConf(Base):
    # Table and column names are kept exactly as the legacy SQL spells them. The port also created a
    # twin table "DynamicConfig" that no code reads; it is not modelled.
    __tablename__ = "DynConf"

    dynconf_id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    device: Mapped[Optional[str]] = mapped_column(String(64))
    callid: Mapped[str] = mapped_column(String(255), nullable=False)
