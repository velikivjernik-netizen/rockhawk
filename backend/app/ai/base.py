from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol


@dataclass
class Citation:
    document_id: str
    document_name: str
    page: int
    quote: str


@dataclass
class ExtractionResult:
    value: str
    not_found: bool
    citations: list[Citation] = field(default_factory=list)
    evidence_quote: str = ""
    provider: str = ""


class AIProvider(Protocol):
    name: str

    def extract(
        self,
        *,
        column_name: str,
        value_type: str,
        instruction: str,
        enum_options: list[str] | None,
        pages: list[tuple[int, str]],
        document_id: str,
        document_name: str,
    ) -> ExtractionResult: ...

    def answer(
        self,
        *,
        question: str,
        snippets: list[dict],
    ) -> ExtractionResult: ...
