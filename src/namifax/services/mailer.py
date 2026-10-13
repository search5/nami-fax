"""Email dispatching service replacing legacy Mailer.php and htmlMimeMail5.php."""

from __future__ import annotations

import mimetypes
import os
import re
import smtplib
import uuid
from namifax.common import settings
from email.message import EmailMessage
from pathlib import Path
from typing import Any, Sequence


class MailerService:
    """Modern Email service compatible with AvantFAX legacy semantics."""

    def __init__(
        self,
        smtp_server: str | None = None,
        smtp_port: int = 25,
        smtp_user: str | None = None,
        smtp_password: str | None = None,
        use_ssl: bool = False,
        use_tls: bool = False,
        admin_email: str = "root@localhost",
        email_sig_text: str = "",
        email_sig_html: str = "",
        spool_mode: bool = False,
    ) -> None:
        self.smtp_server = smtp_server
        self.smtp_port = smtp_port
        self.smtp_user = smtp_user
        self.smtp_password = smtp_password
        self.use_ssl = use_ssl
        self.use_tls = use_tls
        self.admin_email = admin_email
        self.email_sig_text = email_sig_text
        self.email_sig_html = email_sig_html
        self.spool_mode = spool_mode

        self.last_error: str | None = None
        self._spooled_messages: list[EmailMessage] = []
        self._current_message: EmailMessage | None = None
        self._current_subject: str = "NamiFAX Notification"
        self._attachments: list[dict[str, Any]] = []
        self._embedded_images: list[dict[str, Any]] = []
        self._cc: list[str] = []
        self._bcc: list[str] = []
        self._spooled_envelopes: list[list[str]] = []

    @staticmethod
    def _addresses(value: str | Sequence[str] | None) -> list[str]:
        if not value:
            return []
        parts = re.split(r"[;,]", value) if isinstance(value, str) else list(value)
        return [p.strip() for p in parts if p and p.strip()]

    def set_cc(self, addresses: str | Sequence[str] | None) -> None:
        """Copy the message to these addresses (they are listed in the headers)."""
        self._cc = self._addresses(addresses)

    def set_bcc(self, addresses: str | Sequence[str] | None) -> None:
        """Send the message to these addresses without listing them in the headers."""
        self._bcc = self._addresses(addresses)

    @classmethod
    def get_active_mailer(cls, session: Any = None) -> MailerService:
        """Build a mailer from the SMTP gateway saved in the database (spec 39, section 3.2).

        Without a session there is no configuration source and the plain default mailer is returned.
        When the database cannot be read the local MTA (localhost:25) is used: a mailer without a
        server only keeps messages in memory, so falling back to it would lose the mail silently.
        """
        if session is None:
            return cls()
        try:
            from namifax.services.smtp_settings import SmtpSettingsService
            service = SmtpSettingsService(session)
            cfg = service.get_settings()
            use_ssl = (cfg.smtp_security == "SSL")
            use_tls = (cfg.smtp_security == "STARTTLS")
            return cls(
                smtp_server=cfg.smtp_host,
                smtp_port=cfg.smtp_port,
                smtp_user=cfg.smtp_username if cfg.smtp_auth else None,
                smtp_password=cfg.smtp_password if cfg.smtp_auth else None,
                use_ssl=use_ssl,
                use_tls=use_tls,
                admin_email=cfg.from_email,
                email_sig_text=cfg.email_sig_text,
                email_sig_html=cfg.email_sig_html,
            )
        except Exception:
            return cls.local_mta()

    @classmethod
    def local_mta(cls) -> MailerService:
        """Mailer that hands messages to the MTA on this host."""
        return cls(smtp_server="localhost", smtp_port=25)

    from_settings = get_active_mailer  # earlier name, kept as an alias

    def set_message(self, text: str, subject: str | None = None) -> None:
        """Construct multi-part plaintext and HTML message bodies."""
        if subject:
            self._current_subject = subject

        msg = EmailMessage()
        msg["Subject"] = self._current_subject
        # a sender may be "Name <address>" already; a bare address gets the product name
        msg["From"] = self.admin_email if "<" in self.admin_email else f"NamiFAX <{self.admin_email}>"

        # Plaintext body with signature
        full_text = text
        if self.email_sig_text:
            full_text = f"{text}\n\n\n\n{self.email_sig_text}"
        msg.set_content(full_text, charset=settings.email_charset(), cte=settings.email_encoding("TEXT"))

        # HTML alternative body
        converted = text.replace("\n", "<br />")
        sig_html = f"<br /><br />{self.email_sig_html}" if self.email_sig_html else ""
        html_body = f"<html><body>{converted}{sig_html}</body></html>"
        msg.add_alternative(html_body, subtype="html", charset=settings.email_charset(), cte=settings.email_encoding("HTML"))

        self._current_message = msg

    def attach_file(self, file_path: str | Path, alt_name: str | None = None) -> bool:
        """Attach file to the current message."""
        path = Path(file_path)
        if not path.exists():
            self.last_error = f"Attachment file not found: {path}"
            return False

        filename = alt_name or path.name
        content_type, _ = mimetypes.guess_type(str(path))
        if not content_type:
            content_type = "application/octet-stream"

        main_type, sub_type = content_type.split("/", 1)
        data = path.read_bytes()

        self._attachments.append({
            "data": data,
            "maintype": main_type,
            "subtype": sub_type,
            "filename": filename,
        })
        return True

    def embed_image(self, image_path: str | Path, cid: str | None = None) -> bool:
        """Embed an inline image into HTML body."""
        path = Path(image_path)
        if not path.exists():
            self.last_error = f"Image file not found: {path}"
            return False

        cid = cid or f"{uuid.uuid4().hex}@namifax"
        content_type, _ = mimetypes.guess_type(str(path))
        main_type, sub_type = (content_type or "image/jpeg").split("/", 1)

        self._embedded_images.append({
            "data": path.read_bytes(),
            "maintype": main_type,
            "subtype": sub_type,
            "cid": cid,
        })
        return True

    def sendmail(self, to: str | Sequence[str], subject: str | None = None) -> bool:
        """Dispatch email to recipient(s)."""
        self.last_error = None

        if not self._current_message:
            self.set_message("", subject=subject)

        if subject:
            if "Subject" in self._current_message:
                del self._current_message["Subject"]
            self._current_message["Subject"] = subject

        recipients = [to] if isinstance(to, str) else list(to)
        if "To" in self._current_message:
            del self._current_message["To"]
        self._current_message["To"] = ", ".join(recipients)

        if self._cc:
            if "Cc" in self._current_message:
                del self._current_message["Cc"]
            self._current_message["Cc"] = ", ".join(self._cc)
        envelope = recipients + self._cc + self._bcc

        # Inline pictures (the fax thumbnail): shown at the end of the HTML part
        if self._embedded_images:
            html = self._current_message.get_body(("html",))
            if html is not None:
                tags = "".join(f'<br /><img src="cid:{img["cid"]}" alt="" />' for img in self._embedded_images)
                body = html.get_content().replace("</body>", f"{tags}</body>", 1)
                html.set_content(body, subtype="html", charset=settings.email_charset(), cte=settings.email_encoding("HTML"))
                for img in self._embedded_images:
                    html.add_related(img["data"], maintype=img["maintype"], subtype=img["subtype"], cid=f"<{img['cid']}>")

        # Attach files
        for att in self._attachments:
            self._current_message.add_attachment(
                att["data"],
                maintype=att["maintype"],
                subtype=att["subtype"],
                filename=att["filename"],
            )

        # Spool mode for unit testing and offline development
        if self.spool_mode or not self.smtp_server:
            self._spooled_messages.append(self._current_message)
            self._spooled_envelopes.append(envelope)
            return True

        # SMTP dispatch
        try:
            server = (
                smtplib.SMTP_SSL(self.smtp_server, self.smtp_port, timeout=15)
                if self.use_ssl
                else smtplib.SMTP(self.smtp_server, self.smtp_port, timeout=15)
            )

            with server as client:
                if self.use_tls and not self.use_ssl:
                    client.starttls()
                if self.smtp_user and self.smtp_password:
                    client.login(self.smtp_user, self.smtp_password)
                client.send_message(self._current_message, to_addrs=envelope)
            return True
        except Exception as exc:
            self.last_error = str(exc)
            return False

    def get_spooled_messages(self) -> list[EmailMessage]:
        return list(self._spooled_messages)

    def get_error(self) -> str | None:
        return self.last_error


# Legacy alias
Mailer = MailerService
