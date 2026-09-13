"""Canonical allowlist for matter document ingestion."""

from pathlib import Path

ALLOWED_SUFFIXES = {
    ".pdf",
    ".docx",
    ".txt",
    ".md",
    ".csv",
    ".xlsx",
    ".xls",
    ".htm",
    ".html",
    ".xml",
    ".pptx",
    ".ppt",
    ".jpg",
    ".jpeg",
    ".png",
    ".vcf",
    ".vcard",
    ".rtf",
    ".eml",
    ".msg",
}

ALLOWED_TYPES = {
    "",
    "application/octet-stream",
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    "application/vnd.ms-excel",
    "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    "application/vnd.ms-powerpoint",
    "application/vnd.ms-outlook",
    "application/rtf",
    "application/xml",
    "text/xml",
    "text/plain",
    "text/markdown",
    "text/csv",
    "text/html",
    "text/vcard",
    "text/x-vcard",
    "text/rtf",
    "message/rfc822",
    "image/jpeg",
    "image/jpg",
    "image/png",
}

SUPPORTED_LABEL = (
    "PDF, DOCX, TXT, CSV, XLSX, XLS, HTM/HTML, XML, PPTX, PPT, "
    "JPG/JPEG, PNG, VCF, RTF, EML, or MSG"
)

UNSUPPORTED_MESSAGE = f"Unsupported file type. Use {SUPPORTED_LABEL}."


def suffix_of(filename: str) -> str:
    return Path(filename).suffix.lower()
