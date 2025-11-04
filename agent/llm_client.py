from __future__ import annotations
import os
from typing import Optional
from dotenv import load_dotenv

try:
    from openai import OpenAI
except Exception:
    OpenAI = None  # чтобы не падать, если пакет не установлен

load_dotenv()  # читаем .env в корне

class LLMClient:
    def __init__(self, model: Optional[str] = None):
        self.api_key = os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        self.client = OpenAI(api_key=self.api_key) if (OpenAI and self.api_key) else None

    def available(self) -> bool:
        return self.client is not None

    def complete(self, prompt: str, temperature: float = 0.6) -> Optional[str]:
        if not self.client:
            return None
        r = self.client.chat.completions.create(
            model=self.model,
            temperature=temperature,
            messages=[{"role":"user","content": prompt}],
        )
        return (r.choices[0].message.content or "").strip()