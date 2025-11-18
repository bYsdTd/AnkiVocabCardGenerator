from typing import Dict, Any
from abc import ABC, abstractmethod
import os
import json

class TTSAdapter(ABC):
    @abstractmethod
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        pass

from .openai import OpenAICompatibleTTSAdapter
from .qwen import QwenTTSAdapter

def get_tts_adapter(provider: str) -> TTSAdapter:
    if provider == "qwen":
        return QwenTTSAdapter()
    return OpenAICompatibleTTSAdapter(provider)

def get_tts_format(provider: str, cfg: Dict[str, Any]) -> str:
    base = os.path.dirname(__file__)
    fname = f"{provider}_config.json"
    path = os.path.join(base, fname)
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
            fmt = str(data.get("format", "mp3")).strip()
            return fmt if fmt in ("mp3", "wav") else "mp3"
    except Exception:
        return "mp3"