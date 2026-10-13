import os
from pathlib import Path
from typing import Any, Dict, List, Optional
from sqlalchemy import select

from namifax.db.missing import resolve_db
from namifax.models.coverpages import CoverPages


SUPPORTED_COVER_EXTENSIONS = {".ps", ".pdf", ".html", ".jinja2"}

COVER_TAGS_METADATA = [
    {"tag": "to_person", "legacy_token": "XXXX-to", "description": "Recipient full name"},
    {"tag": "to_company", "legacy_token": "XXXX-to-company", "description": "Recipient company name"},
    {"tag": "to_fax", "legacy_token": "XXXX-to-fax-number", "description": "Destination fax number"},
    {"tag": "from_person", "legacy_token": "XXXX-from", "description": "Sender full name"},
    {"tag": "from_company", "legacy_token": "XXXX-from-company", "description": "Sender company name"},
    {"tag": "regarding", "legacy_token": "XXXX-regarding", "description": "Subject / Regarding"},
    {"tag": "comments", "legacy_token": "XXXX-comments", "description": "Notes and comments body"},
    {"tag": "pages", "legacy_token": "XXXX-page-count", "description": "Total transmission pages"},
    {"tag": "date", "legacy_token": "XXXX-date", "description": "Dispatch timestamp"},
]


class CoverStudioService:
    """Enterprise Fax Cover Template Studio Service."""

    def __init__(
        self,
        db: Any = None,
        covers_dir: Optional[str] = None,
    ) -> None:
        self.db = resolve_db(db, "CoverStudioService")
        self.covers_dir = covers_dir or os.environ.get(
            "AVANTFAX_COVERS_DIR", "/var/spool/hylafax/covers"
        )
        try:
            os.makedirs(self.covers_dir, exist_ok=True)
        except OSError:
            pass

    @staticmethod
    def get_supported_tags() -> List[Dict[str, str]]:
        return COVER_TAGS_METADATA

    def save_template(self, filename: str, content: bytes, title: str) -> Dict[str, Any]:
        ext = Path(filename).suffix.lower()
        if ext not in SUPPORTED_COVER_EXTENSIONS:
            return {
                "success": False,
                "message": f"Unsupported template format '{ext}'. Supported: {', '.join(sorted(SUPPORTED_COVER_EXTENSIONS))}",
                "cover_id": None,
            }

        safe_filename = os.path.basename(filename)
        dest_path = os.path.join(self.covers_dir, safe_filename)

        try:
            with open(dest_path, "wb") as f:
                f.write(content)
        except OSError as exc:
            return {
                "success": False,
                "message": f"Failed to save template file: {exc}",
                "cover_id": None,
            }

        # Register in CoverPages table
        page = CoverPages(title=title, file=safe_filename)
        self.db.add(page)
        self.db.flush()
        cover_id = page.cover_id

        return {
            "success": True,
            "message": "Cover template saved and registered successfully.",
            "cover_id": cover_id,
            "file_path": dest_path,
        }

    def render_template(self, cover_id: int, context: Dict[str, Any]) -> bytes:
        filename = self.db.execute(select(CoverPages.file).where(CoverPages.cover_id == int(cover_id))).scalars().first()
        if not filename:
            return b""

        file_path = os.path.join(self.covers_dir, filename)
        if not os.path.exists(file_path):
            return b""

        with open(file_path, "rb") as f:
            raw_content = f.read()

        ext = Path(filename).suffix.lower()

        # HTML / Jinja2 rendering
        if ext in (".html", ".jinja2"):
            try:
                import jinja2
                template_str = raw_content.decode("utf-8", errors="ignore")
                template = jinja2.Template(template_str)
                rendered_str = template.render(**context)
                return rendered_str.encode("utf-8")
            except Exception:
                return raw_content

        # PostScript token substitution
        if ext == ".ps":
            ps_text = raw_content.decode("latin-1", errors="ignore")
            for item in COVER_TAGS_METADATA:
                tag = item["tag"]
                token = item["legacy_token"]
                val = str(context.get(tag, ""))
                ps_text = ps_text.replace(token, val)
                ps_text = ps_text.replace(f"{{{{ {tag} }}}}", val)
            return ps_text.encode("latin-1")

        # PDF or binary format: return as-is
        return raw_content
