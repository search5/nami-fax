from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import webauthn
from webauthn.helpers import (
    base64url_to_bytes,
    bytes_to_base64url,
    options_to_json,
)
from webauthn.helpers.structs import (
    AttestationConveyancePreference,
    AuthenticatorAttachment,
    AuthenticatorSelectionCriteria,
    ResidentKeyRequirement,
    PublicKeyCredentialDescriptor,
    UserVerificationRequirement,
)

from sqlalchemy import delete, select, update

from namifax.db.missing import resolve_db
from namifax.models.userwebauthn import UserWebAuthnCredentials

@dataclass
class WebAuthnCredential:
    id: int
    uid: int
    credential_id: str
    device_name: str
    created_at: str | datetime
    last_used_at: str | datetime | None = None
    sign_count: int = 0
    transports: str | None = None

class WebAuthnService:
    """Enterprise W3C WebAuthn / FIDO2 Passkeys authentication service."""

    def __init__(
        self,
        rp_id: str = "localhost",
        rp_name: str = "NamiFAX Enterprise",
        origin: str = "http://localhost:8000",
        db: Any = None,
    ) -> None:
        self.rp_id = rp_id
        self.rp_name = rp_name
        self.origin = origin
        self.db = resolve_db(db, "WebAuthnService")

    def generate_registration_options(
        self,
        user_id: int,
        user_name: str,
        user_display_name: str | None = None,
    ) -> dict[str, Any]:
        """Generate options for navigator.credentials.create()."""
        raw_options = webauthn.generate_registration_options(
            rp_id=self.rp_id,
            rp_name=self.rp_name,
            user_id=str(user_id).encode("utf-8"),
            user_name=user_name,
            user_display_name=user_display_name or user_name,
            attestation=AttestationConveyancePreference.NONE,
            authenticator_selection=AuthenticatorSelectionCriteria(
                # a discoverable credential: the login page offers passkeys without asking for a user name first
                resident_key=ResidentKeyRequirement.REQUIRED,
                require_resident_key=True,
                user_verification=UserVerificationRequirement.PREFERRED,
            ),
        )
        return json.loads(options_to_json(raw_options))

    def verify_registration_response(
        self,
        credential_data: dict[str, Any] | str,
        expected_challenge: str,
        expected_origin: str | None = None,
    ) -> dict[str, Any]:
        """Verify client registration attestation and extract credential details."""
        if isinstance(credential_data, str):
            credential_data = json.loads(credential_data)

        verification = webauthn.verify_registration_response(
            credential=credential_data,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_rp_id=self.rp_id,
            expected_origin=expected_origin or self.origin,
            require_user_verification=False,
        )
        return {
            # random bytes, not text: stored (and looked up) as base64url, which is also how the browser reports the id
            "credential_id": bytes_to_base64url(verification.credential_id) if isinstance(verification.credential_id, bytes) else str(verification.credential_id),
            "credential_public_key": verification.credential_public_key.hex(),
            "sign_count": verification.sign_count,
        }

    def generate_authentication_options(
        self,
        user_id: int | None = None,
    ) -> dict[str, Any]:
        """Generate options for navigator.credentials.get()."""
        allow_creds = []
        if user_id:
            for cred in self.list_credentials(int(user_id)):
                cid = cred.credential_id
                if cid:
                    allow_creds.append(PublicKeyCredentialDescriptor(id=base64url_to_bytes(cid)))

        raw_options = webauthn.generate_authentication_options(
            rp_id=self.rp_id,
            allow_credentials=allow_creds if allow_creds else None,
            user_verification=UserVerificationRequirement.PREFERRED,
        )
        return json.loads(options_to_json(raw_options))

    def verify_authentication_response(
        self,
        credential_data: dict[str, Any] | str,
        expected_challenge: str,
        credential_public_key: bytes,
        credential_current_sign_count: int,
        expected_origin: str | None = None,
    ) -> int:
        """Verify client authentication assertion and return updated sign count."""
        if isinstance(credential_data, str):
            credential_data = json.loads(credential_data)

        verification = webauthn.verify_authentication_response(
            credential=credential_data,
            expected_challenge=base64url_to_bytes(expected_challenge),
            expected_rp_id=self.rp_id,
            expected_origin=expected_origin or self.origin,
            credential_public_key=credential_public_key,
            credential_current_sign_count=credential_current_sign_count,
            require_user_verification=False,
        )
        return verification.new_sign_count

    def save_credential(
        self,
        uid: int,
        credential_id: str,
        public_key: str,
        sign_count: int = 0,
        device_name: str = "Security Key",
        transports: list[str] | str | None = None,
    ) -> WebAuthnCredential:
        """Save a new WebAuthn credential in database."""
        transports_str = ",".join(transports) if isinstance(transports, list) else (transports or "")
        row = UserWebAuthnCredentials(
            uid=int(uid), credential_id=credential_id, public_key=public_key, sign_count=int(sign_count),
            transports=transports_str, device_name=device_name, created_at=_now(),
        )
        self.db.add(row)
        self.db.flush()
        return self._credential(row)

    @staticmethod
    def _credential(row: Any) -> WebAuthnCredential:
        return WebAuthnCredential(
            id=row.id, uid=row.uid, credential_id=row.credential_id, device_name=row.device_name,
            created_at=row.created_at or "", last_used_at=row.last_used_at or None,
            sign_count=row.sign_count or 0, transports=row.transports,
        )

    def list_credentials(self, uid: int) -> list[WebAuthnCredential]:
        """List all active credentials registered by a user, newest first."""
        rows = self.db.execute(
            select(UserWebAuthnCredentials).where(UserWebAuthnCredentials.uid == int(uid))
            .order_by(UserWebAuthnCredentials.id.desc())
        ).scalars().all()
        return [self._credential(r) for r in rows]

    def delete_credential(self, uid: int, credential_db_id: int) -> bool:
        """Delete a credential registered by the user (another user's id removes nothing)."""
        self.db.execute(delete(UserWebAuthnCredentials).where(
            UserWebAuthnCredentials.id == int(credential_db_id), UserWebAuthnCredentials.uid == int(uid)))
        return True

    def get_credential_by_id(self, credential_id: str) -> dict[str, Any] | None:
        """Fetch credential row by base64url credential_id."""
        row = self.db.execute(
            select(UserWebAuthnCredentials).where(UserWebAuthnCredentials.credential_id == credential_id)
        ).scalars().first()
        if row is None:
            return None
        return {c.name: getattr(row, c.key) for c in UserWebAuthnCredentials.__table__.columns}

    def update_sign_count(self, credential_id: str, new_sign_count: int) -> None:
        """Update sign count and last used timestamp."""
        self.db.execute(update(UserWebAuthnCredentials).where(
            UserWebAuthnCredentials.credential_id == credential_id
        ).values(sign_count=int(new_sign_count), last_used_at=_now()))


def _now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
