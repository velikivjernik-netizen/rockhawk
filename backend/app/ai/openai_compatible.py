from __future__ import annotations

import json
import re

import httpx

from app.ai.base import Citation, ExtractionResult
from app.ai.mock import MockProvider
from app.config import get_settings

SYSTEM = (
    "You are RockHawk, an attorney-assistance extractor. "
    "Use ONLY the provided page text. If the answer is not supported, "
    "return {\"value\":\"Not found\",\"not_found\":true,\"quote\":\"\",\"page\":null}. "
    "Never invent parties, dates, amounts, or legal conclusions. "
    "You do not make autonomous legal decisions."
)


class OpenAICompatibleProvider:
    name = "openai_compatible"

    def __init__(self, base_url: str | None = None, api_key: str | None = None, model: str | None = None) -> None:
        self._fallback = MockProvider()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def extract(self, **kwargs) -> ExtractionResult:
        pages = kwargs["pages"]
        context = "\n\n".join(f"[Page {n}]\n{text}" for n, text in pages[:20])
        user = (
            f"Column: {kwargs['column_name']}\nType: {kwargs['value_type']}\n"
            f"Instruction: {kwargs['instruction']}\n"
            f"Enum options: {kwargs.get('enum_options')}\n\nSOURCE PAGES:\n{context}\n\n"
            "Return JSON with keys value, not_found, quote, page."
        )
        data = self._complete(user)
        if data is None:
            return self._fallback.extract(**kwargs)
        return self._to_result(data, kwargs["document_id"], kwargs["document_name"], pages)

    def answer(self, *, question: str, snippets: list[dict]) -> ExtractionResult:
        context = json.dumps(snippets[:12], ensure_ascii=False)[:12000]
        user = f"Question: {question}\nGrounding snippets (JSON):\n{context}\nAnswer only from snippets."
        data = self._complete(user)
        if data is None:
            return self._fallback.answer(question=question, snippets=snippets)
        citations = []
        for snippet in snippets[:6]:
            if snippet.get("page"):
                citations.append(
                    Citation(
                        document_id=str(snippet.get("document_id") or ""),
                        document_name=str(snippet.get("document_name") or ""),
                        page=int(snippet["page"]),
                        quote=str(snippet.get("text") or "")[:280],
                    )
                )
        value = str(data.get("value") or "Not found")
        return ExtractionResult(
            value=value,
            not_found=bool(data.get("not_found")) or value.lower() == "not found",
            citations=citations,
            evidence_quote=str(data.get("quote") or ""),
            provider=self.name,
        )

    def _complete(self, user: str) -> dict | None:
        settings = get_settings()
        headers = {"Content-Type": "application/json"}
        api_key = self.api_key if self.api_key is not None else settings.openai_compatible_api_key
        model = self.model or settings.openai_compatible_model
        base_url = self.base_url or settings.openai_compatible_base_url
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
        payload = {
            "model": model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": SYSTEM},
                {"role": "user", "content": user},
            ],
        }
        try:
            with httpx.Client(timeout=60.0) as client:
                response = client.post(
                    f"{base_url.rstrip('/')}/chat/completions",
                    headers=headers,
                    json=payload,
                )
                response.raise_for_status()
                content = response.json()["choices"][0]["message"]["content"]
        except Exception:
            return None
        return _parse_json(content)

    def _to_result(self, data: dict, document_id: str, document_name: str, pages) -> ExtractionResult:
        value = str(data.get("value") or "Not found").strip()
        not_found = bool(data.get("not_found")) or value.lower() == "not found"
        quote = str(data.get("quote") or "")
        page = data.get("page")
        citations = []
        if quote and page:
            citations.append(
                Citation(document_id=document_id, document_name=document_name, page=int(page), quote=quote[:400])
            )
        elif quote:
            for num, text in pages:
                if quote[:40].lower() in text.lower():
                    citations.append(
                        Citation(document_id=document_id, document_name=document_name, page=num, quote=quote[:400])
                    )
                    break
        if not_found:
            value = "Not found"
        return ExtractionResult(
            value=value,
            not_found=not_found,
            citations=citations,
            evidence_quote=quote[:400],
            provider=self.name,
        )


def _parse_json(content: str) -> dict | None:
    content = content.strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", content, re.S)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
