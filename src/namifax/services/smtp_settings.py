import logging
import os
import smtplib
import ssl
from dataclasses import dataclass, field
from datetime import datetime
from email.message import EmailMessage
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from namifax.common.secretbox import encrypt
from namifax.models.systemsettings import SystemSettings


@dataclass
class SmtpConfig:
    smtp_host: str = "localhost"
    smtp_port: int = 25
    smtp_security: str = "NONE"  # NONE, STARTTLS, SSL
    smtp_auth: bool = False
    smtp_username: Optional[str] = None
    smtp_password: Optional[str] = None
    from_email: str = "root@localhost"
    from_name: str = "NamiFAX"
    email_sig_text: str = ""
    email_sig_html: str = ""
    updated_at: Optional[str] = None


@dataclass
class SmtpTestResult:
    success: bool
    message: str
    details: List[str] = field(default_factory=list)


class SmtpSettingsService:
    """Manages enterprise SMTP gateway configuration and connectivity diagnostics.

    Reads and writes the single ``SystemSettings`` row (id = 1) through an ORM session, so the
    same code runs on SQLite, MySQL, MariaDB and PostgreSQL.
    """

    ROW_ID = 1

    @staticmethod
    def _read_password(stored):
        """The SMTP password in plain text; an undecryptable one is treated as missing (the admin re-enters it)."""
        from namifax.common.secretbox import SecretDecryptError, SecretKeyError, decrypt

        try:
            return decrypt(stored) or stored
        except (SecretDecryptError, SecretKeyError):
            logging.getLogger("namifax").error("The stored SMTP password cannot be decrypted; enter it again")
            return None

    def __init__(self, session: Optional[Session] = None) -> None:
        self.session = session

    def _require_session(self) -> Session:
        if self.session is None:
            raise RuntimeError("SmtpSettingsService: no database session injected (pass request.dbsession)")
        return self.session

    def get_settings(self) -> SmtpConfig:
        row = self._require_session().get(SystemSettings, self.ROW_ID)
        if row is None:
            return SmtpConfig()

        return SmtpConfig(
            smtp_host=row.smtp_host or "localhost",
            smtp_port=int(row.smtp_port or 25),
            smtp_security=row.smtp_security or "NONE",
            smtp_auth=bool(row.smtp_auth),
            smtp_username=row.smtp_username,
            smtp_password=self._read_password(row.smtp_password),
            from_email=row.from_email or "root@localhost",
            from_name=row.from_name or "NamiFAX",
            email_sig_text=row.email_sig_text or "",
            email_sig_html=row.email_sig_html or "",
            updated_at=row.updated_at,
        )

    def save_settings(self, data: Dict[str, Any]) -> bool:
        session = self._require_session()
        port = int(data.get("smtp_port", 25))
        if port < 1 or port > 65535:
            raise ValueError(f"Invalid SMTP port: {port}. Port must be between 1 and 65535.")

        security = str(data.get("smtp_security", "NONE")).upper()
        if security not in ("NONE", "STARTTLS", "SSL"):
            security = "NONE"

        auth_val = data.get("smtp_auth", False)
        auth = False
        if isinstance(auth_val, str):
            auth = auth_val.lower() in ("1", "true", "on", "yes")
        elif isinstance(auth_val, (int, bool)):
            auth = bool(auth_val)

        row = session.get(SystemSettings, self.ROW_ID)
        if row is None:
            row = SystemSettings(id=self.ROW_ID)
            session.add(row)

        row.smtp_host = str(data.get("smtp_host", "localhost")).strip()
        row.smtp_port = port
        row.smtp_security = security
        row.smtp_auth = auth
        row.smtp_username = data.get("smtp_username") or ""
        row.smtp_password = encrypt(data.get("smtp_password") or "")
        row.from_email = str(data.get("from_email", "root@localhost")).strip()
        row.from_name = str(data.get("from_name", "NamiFAX")).strip()
        row.email_sig_text = data.get("email_sig_text", "") or ""
        row.email_sig_html = data.get("email_sig_html", "") or ""
        row.updated_at = datetime.now().isoformat()
        session.flush()
        return True

    def test_connection(self, target_email: str, config: Optional[SmtpConfig] = None) -> SmtpTestResult:
        if config is None:
            config = self.get_settings()

        logs: List[str] = []
        host = config.smtp_host or "localhost"
        port = config.smtp_port or 25
        security = (config.smtp_security or "NONE").upper()

        logs.append(f"Initiating connection to {host}:{port} (Security: {security})...")

        try:
            if security == "SSL":
                ctx = ssl.create_default_context()
                server = smtplib.SMTP_SSL(host, port, context=ctx, timeout=10)
            else:
                server = smtplib.SMTP(host, port, timeout=10)

            with server as s:
                s.ehlo()
                logs.append("EHLO handshake successful.")

                if security == "STARTTLS":
                    logs.append("Starting STARTTLS handshake...")
                    ctx = ssl.create_default_context()
                    s.starttls(context=ctx)
                    s.ehlo()
                    logs.append("STARTTLS handshake verified.")

                if config.smtp_auth:
                    logs.append(f"Authenticating as {config.smtp_username}...")
                    s.login(config.smtp_username or "", config.smtp_password or "")
                    logs.append("Authentication accepted.")

                logs.append(f"Sending diagnostic message from {config.from_email} to {target_email}...")
                msg = EmailMessage()
                msg["Subject"] = "[NamiFAX] SMTP Gateway Diagnostic Test"
                msg["From"] = f"{config.from_name} <{config.from_email}>"
                msg["To"] = target_email
                msg.set_content(
                    "This is an automated diagnostic test message from NamiFAX Admin SMTP Gateway.\n"
                    "If you received this message, your external SMTP configuration is operational."
                )
                s.send_message(msg)
                logs.append("Diagnostic test email delivered successfully.")

            return SmtpTestResult(
                success=True,
                message=f"Successfully connected to {host}:{port} and delivered test email.",
                details=logs,
            )

        except Exception as exc:
            err_msg = str(exc)
            logs.append(f"Error during SMTP operation: {err_msg}")
            return SmtpTestResult(
                success=False,
                message=f"Failed to connect to SMTP server: {err_msg}",
                details=logs,
            )
