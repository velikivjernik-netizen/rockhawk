from __future__ import annotations

import re
from datetime import datetime

from app.ai.base import Citation, ExtractionResult


NOT_FOUND = "Not found"


class MockProvider:
    """Grounded extractor. Never invents values that are not on a page."""

    name = "mock"

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
    ) -> ExtractionResult:
        haystack = [(num, text, text.lower()) for num, text in pages]
        key = f"{column_name} {instruction}".lower()

        if value_type == "boolean":
            return self._boolean(haystack, key, document_id, document_name)
        if value_type == "date":
            return self._date(haystack, key, document_id, document_name)
        if value_type == "money":
            return self._money(haystack, key, document_id, document_name)
        if value_type == "number":
            return self._number(haystack, key, document_id, document_name)
        if value_type == "enum":
            if "attorney" in key or "review" in column_name.lower():
                return self._attorney_review(haystack, enum_options or ["Yes", "No"], document_id, document_name)
            return self._enum(haystack, enum_options or [], document_id, document_name)
        return self._text(haystack, key, column_name, document_id, document_name)

    def answer(self, *, question: str, snippets: list[dict]) -> ExtractionResult:
        if not snippets:
            return ExtractionResult(
                value="Not found in the current review table or source pages.",
                not_found=True,
                provider=self.name,
            )
        lines = []
        citations: list[Citation] = []
        q_terms = {t for t in re.findall(r"[a-z0-9]{3,}", question.lower()) if t not in _STOP}
        for snippet in snippets[:8]:
            text = str(snippet.get("text") or "")
            score = sum(1 for term in q_terms if term in text.lower())
            if q_terms and score == 0 and "value" not in snippet:
                continue
            label = snippet.get("label") or snippet.get("document_name") or "source"
            lines.append(f"- {label}: {text[:400]}")
            if snippet.get("page"):
                citations.append(
                    Citation(
                        document_id=str(snippet.get("document_id") or ""),
                        document_name=str(snippet.get("document_name") or label),
                        page=int(snippet.get("page") or 1),
                        quote=text[:280],
                    )
                )
        if not lines:
            return ExtractionResult(
                value="Not found in the current review table or source pages.",
                not_found=True,
                provider=self.name,
            )
        body = (
            "Answer grounded only in the current table outputs and cited pages:\n"
            + "\n".join(lines)
            + "\n\nRockHawk does not make legal determinations. An attorney must review."
        )
        return ExtractionResult(value=body, not_found=False, citations=citations, provider=self.name)

    def _hit(self, page_num: int, page_text: str, quote: str, value: str, document_id: str, document_name: str) -> ExtractionResult:
        citation = Citation(document_id=document_id, document_name=document_name, page=page_num, quote=quote[:400])
        return ExtractionResult(
            value=value,
            not_found=False,
            citations=[citation],
            evidence_quote=quote[:400],
            provider=self.name,
        )

    def _miss(self) -> ExtractionResult:
        return ExtractionResult(value=NOT_FOUND, not_found=True, provider=self.name)

    def _boolean(self, haystack, key, document_id, document_name) -> ExtractionResult:
        positive, negative = _boolean_cues(key)
        for num, raw, lower in haystack:
            if any(cue in lower for cue in negative):
                quote = _sentence_around(raw, negative)
                return self._hit(num, raw, quote, "false", document_id, document_name)
            if any(cue in lower for cue in positive):
                quote = _sentence_around(raw, positive)
                return self._hit(num, raw, quote, "true", document_id, document_name)
        return self._miss()

    def _date(self, haystack, key, document_id, document_name) -> ExtractionResult:
        pattern = re.compile(
            r"\b(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},\s+\d{4}\b"
            r"|\b\d{4}-\d{2}-\d{2}\b"
            r"|\b\d{1,2}/\d{1,2}/\d{4}\b",
            re.I,
        )
        label_terms = _terms_for(key, extra=["effective", "date", "executed", "as of"])
        best = None
        for num, raw, lower in haystack:
            for match in pattern.finditer(raw):
                window = raw[max(0, match.start() - 80) : match.end() + 40]
                score = sum(1 for term in label_terms if term in window.lower())
                if best is None or score > best[0]:
                    best = (score, num, raw, match.group(0), window)
        if best and (best[0] > 0 or "date" in key):
            iso = _normalize_date(best[3])
            return self._hit(best[1], best[2], best[4], iso, document_id, document_name)
        return self._miss()

    def _money(self, haystack, key, document_id, document_name) -> ExtractionResult:
        pattern = re.compile(r"\$[\d,]+(?:\.\d{2})?")
        required = [term for term in ("cap", "liability", "limitation", "aggregate") if term in key]
        label_terms = _terms_for(key, extra=["cap", "liability", "limitation", "aggregate"])
        best = None
        for num, raw, _lower in haystack:
            for match in pattern.finditer(raw):
                window = raw[max(0, match.start() - 90) : match.end() + 50]
                lowered = window.lower()
                if required and not any(term in lowered for term in required):
                    continue
                score = sum(1 for term in label_terms if term in lowered)
                if best is None or score > best[0]:
                    best = (score, num, raw, match.group(0), window)
        if best and best[0] > 0:
            return self._hit(best[1], best[2], best[4], best[3], document_id, document_name)
        return self._miss()

    def _number(self, haystack, key, document_id, document_name) -> ExtractionResult:
        days = re.compile(r"(\d+)\s+days?", re.I)
        label_terms = _terms_for(key, extra=["notice", "period", "days", "term"])
        for num, raw, _lower in haystack:
            for match in days.finditer(raw):
                window = raw[max(0, match.start() - 70) : match.end() + 30]
                if any(term in window.lower() for term in label_terms):
                    return self._hit(num, raw, window, match.group(1), document_id, document_name)
        return self._miss()

    def _attorney_review(self, haystack, options, document_id, document_name) -> ExtractionResult:
        triggers = (
            "liability",
            "termination",
            "privilege",
            "settlement",
            "personal data",
            "injunctive",
            "confidential",
        )
        yes = options[0] if options else "Yes"
        no = options[1] if len(options) > 1 else "No"
        for num, raw, lower in haystack:
            if any(trigger in lower for trigger in triggers):
                quote = _sentence_around(raw, [t for t in triggers if t in lower])
                return self._hit(num, raw, quote, yes, document_id, document_name)
        if haystack:
            num, raw, _lower = haystack[0]
            return self._hit(num, raw, raw[:160], no, document_id, document_name)
        return self._miss()

    def _enum(self, haystack, options, document_id, document_name) -> ExtractionResult:
        for option in options:
            needle = option.lower()
            for num, raw, lower in haystack:
                if needle in lower:
                    return self._hit(num, raw, _sentence_around(raw, [needle]), option, document_id, document_name)
        return self._miss()

    def _text(self, haystack, key, column_name, document_id, document_name) -> ExtractionResult:
        extractors = [
            ("governing", r"(?<!not )governed by the laws of ([^\.\n]+)", 1),
            ("law", r"(?:shall be |is )?governed by the laws of the (State of [A-Za-z ]+)", 1),
            ("confidential", r"confidential(?:ity)?(?: obligations?)? (?:survive|remain)[^\.\n]{0,80}", 0),
            ("notice period", r"(\d+\s+days?[^\.\n]{0,80}notice[^\.\n]*)", 1),
            ("termination notice", r"(thirty \(\d+\) days[^\.\n]+|(\d+)\s+days['’]? (?:prior )?written notice[^\.\n]*)", 0),
            ("party", r"(?:between|by and between)\s+([^\n]{10,160})", 1),
            ("venue", r"courts? (?:of|in) ([^\.\n]+)", 1),
        ]
        for label, pattern, group in extractors:
            if label not in key and label.split()[0] not in column_name.lower():
                continue
            regex = re.compile(pattern, re.I)
            for num, raw, _lower in haystack:
                match = regex.search(raw)
                if match:
                    value = match.group(group or 0).strip(" .;")
                    return self._hit(num, raw, match.group(0), value, document_id, document_name)

        # Fallback: return a short sentence that contains the most query terms, else miss.
        terms = _terms_for(key, extra=re.findall(r"[a-z]{4,}", column_name.lower()))
        best = None
        for num, raw, lower in haystack:
            for sentence in re.split(r"(?<=[\.!?])\s+", raw):
                lowered = sentence.lower()
                if any(neg in lowered for neg in ("does not", "do not", "not restate", "not contain", "is not stated")):
                    continue
                score = sum(1 for term in terms if term in lowered)
                if score >= 3 and (best is None or score > best[0]):
                    best = (score, num, raw, sentence.strip())
        if best:
            return self._hit(best[1], best[2], best[3], best[3][:240], document_id, document_name)
        return self._miss()


def _boolean_cues(key: str) -> tuple[list[str], list[str]]:
    if "terminat" in key and "convenience" in key:
        return (
            [
                "termination for convenience",
                "terminate for convenience",
                "terminate this agreement for convenience",
                "may terminate this agreement for any reason",
            ],
            [
                "no termination for convenience",
                "may not terminate for convenience",
                "may not be terminated for convenience",
            ],
        )
    if "attorney review" in key or "needs attorney" in key:
        return (
            ["needs attorney review", "privilege", "settlement", "injunctive", "personal data"],
            [],
        )
    if "assignment" in key:
        return (["may assign", "assignment is permitted"], ["may not assign", "shall not assign"])
    return (["shall", "will", "is granted"], ["shall not", "does not", "is not"])


def _terms_for(key: str, extra: list[str] | None = None) -> list[str]:
    words = re.findall(r"[a-z0-9]{4,}", key)
    words.extend(extra or [])
    return [w for w in words if w not in _STOP]


def _sentence_around(text: str, needles: list[str]) -> str:
    lower = text.lower()
    for needle in needles:
        idx = lower.find(needle)
        if idx >= 0:
            start = text.rfind(".", 0, idx)
            end = text.find(".", idx)
            start = 0 if start < 0 else start + 1
            end = len(text) if end < 0 else end + 1
            return text[start:end].strip()
    return text[:280]


def _normalize_date(raw: str) -> str:
    raw = raw.strip()
    for fmt in ("%B %d, %Y", "%b %d, %Y", "%Y-%m-%d", "%m/%d/%Y"):
        try:
            return datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    return raw


_STOP = {
    "this",
    "that",
    "with",
    "from",
    "have",
    "what",
    "when",
    "where",
    "which",
    "only",
    "document",
    "column",
    "review",
    "extract",
    "using",
    "the",
    "and",
    "for",
    "not",
}
