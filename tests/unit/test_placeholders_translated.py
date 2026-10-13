"""Words in an input's example text (placeholder) are translated like any other text; only technical values stay as they are."""

from __future__ import annotations

import re
from pathlib import Path

TEMPLATES = Path(__file__).resolve().parents[2] / "src" / "namifax" / "templates"

# values that are not words of a language: addresses, host names, device names, formats, certificate markers
TECHNICAL = {
    "operator@namifax.local", "lp0", "lp1", "lp or raw", "192.168.1.150", "inbound@namifax.local",
    "https://sts.windows.net/... or https://dev-xxx.okta.com", "https://login.microsoftonline.com/.../saml2",
    "-----BEGIN CERTIFICATE-----&#10;...&#10;-----END CERTIFICATE-----", "smtp.example.com", "587", "mailer@company.com",
    "••••••••••••", "fax-system@company.com", "admin@company.com", "https://s3.amazonaws.com or http://minio.internal:9000",
    "us-east-1", "namifax-archive", "AKIA...", "faxes/", "YYYY-MM-DD", "user@domain.com", "username@example.com",
}


def test_every_wordy_placeholder_goes_through_gettext():
    untranslated = []
    for path in sorted(TEMPLATES.glob("*.jinja2")):
        for value in re.findall(r'placeholder="([^"{]*)"', path.read_text(encoding="utf-8")):
            if value not in TECHNICAL:
                untranslated.append(f"{path.name}: {value}")
    assert untranslated == []


def test_the_multiple_numbers_hint_names_the_separator_the_form_uses():
    """Several destinations are separated by semicolons (the original's rule); the text next to the field said comma."""
    template = (TEMPLATES / "sendfax.jinja2").read_text(encoding="utf-8")
    assert "separate numbers with a comma" not in template and "semicolon" in template
