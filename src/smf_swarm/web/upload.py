"""SMF Swarm — Report / Context Upload Handler.

Extracts text from PDF and plain-text files for pipeline context ingestion.
"""

from __future__ import annotations

import io

MAX_UPLOAD_CHARS = 50000  # ~50K chars max context


def extract_text(content: bytes, filename: str) -> str:
    """Extract readable text from PDF or text file bytes."""
    lower_name = filename.lower()

    if lower_name.endswith(".pdf"):
        return _extract_pdf(content)
    elif lower_name.endswith(".txt"):
        return content.decode("utf-8", errors="ignore")
    elif lower_name.endswith(".md"):
        return content.decode("utf-8", errors="ignore")
    else:
        # Try as text; fail gracefully
        try:
            return content.decode("utf-8", errors="ignore")
        except Exception:
            return "[Could not extract text from this file type]"


def _extract_pdf(content: bytes) -> str:
    """Extract text from PDF using PyPDF2 (graceful fallback)."""
    try:
        from PyPDF2 import PdfReader

        reader = PdfReader(io.BytesIO(content))
        text_parts = []
        for page in reader.pages:
            try:
                text_parts.append(page.extract_text() or "")
            except Exception:
                continue
        return "\n".join(text_parts)
    except ImportError:
        return "[PyPDF2 not installed. PDF text extraction unavailable. pip install PyPDF2]"
    except Exception as e:
        return f"[PDF extraction error: {e}]"


def ingest_file(content: bytes, filename: str) -> dict:
    """Ingest a file and return structured metadata."""
    text = extract_text(content, filename)

    # Truncate if too long
    was_truncated = False
    original_len = len(text)
    if original_len > MAX_UPLOAD_CHARS:
        text = text[:MAX_UPLOAD_CHARS] + "\n\n[...truncated...]"
        was_truncated = True

    return {
        "filename": filename,
        "char_count": original_len,
        "char_sent": len(text),
        "truncated": was_truncated,
        "text": text,
        "text_preview": text[:500] + ("..." if len(text) > 500 else ""),
    }
