"""UserPasswords: the password history that blocks reuse (B track, group 3)."""

from __future__ import annotations

from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from namifax.models.meta import Base


class UserPasswords(Base):
    # Table and column names are kept exactly as the legacy SQL spells them. The port's own table used
    # pwd_id / password, which the service never wrote to, so the history never worked.
    __tablename__ = "UserPasswords"

    upid: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uid: Mapped[int] = mapped_column(Integer, nullable=False)
    pwdhash: Mapped[str] = mapped_column(String(255), nullable=False)
