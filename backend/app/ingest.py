from __future__ import annotations

import io
import re
from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader


def extract_pages(filename: str, data: bytes) -> list[tuple[int, str]]:
    suffix = Path(filename).suffix.lower()
    if suffix == ".pdf":
        return _pdf_pages(data)
    if suffix in {".docx"}:
        return _docx_pages(data)
    if suffix in {".txt", ".md"}:
        return _text_pages(data.decode("utf-8", errors="replace"))
    raise ValueError(f"Unsupported file type: {suffix or 'unknown'}. Use PDF, DOCX, or TXT.")


def _pdf_pages(data: bytes) -> list[tuple[int, str]]:
    reader = PdfReader(io.BytesIO(data))
    pages: list[tuple[int, str]] = []
    for index, page in enumerate(reader.pages, start=1):
        text = (page.extract_text() or "").strip()
        pages.append((index, text))
    return pages or [(1, "")]


def _docx_pages(data: bytes) -> list[tuple[int, str]]:
    document = DocxDocument(io.BytesIO(data))
    paragraphs = [p.text.strip() for p in document.paragraphs if p.text.strip()]
    chunks = _chunk("\n\n".join(paragraphs))
    return [(i, chunk) for i, chunk in enumerate(chunks, start=1)]


def _text_pages(text: str) -> list[tuple[int, str]]:
    form_feed = [part.strip() for part in text.split("\f") if part.strip()]
    if len(form_feed) > 1:
        return [(i, part) for i, part in enumerate(form_feed, start=1)]
    chunks = _chunk(text)
    return [(i, chunk) for i, chunk in enumerate(chunks, start=1)]


def _chunk(text: str, size: int = 1800) -> list[str]:
    text = text.strip()
    if not text:
        return [""]
    paragraphs = re.split(r"\n\s*\n", text)
    pages: list[str] = []
    current = ""
    for para in paragraphs:
        if len(current) + len(para) + 2 > size and current:
            pages.append(current.strip())
            current = para
        else:
            current = f"{current}\n\n{para}" if current else para
    if current.strip():
        pages.append(current.strip())
    return pages
