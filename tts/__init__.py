from typing import Dict, Any
from abc import ABC, abstractmethod

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