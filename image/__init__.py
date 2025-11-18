from typing import Dict, Any
from abc import ABC, abstractmethod

class ImageAdapter(ABC):
    @abstractmethod
    def generate(self, word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> bytes:
        pass

from .openai import OpenAICompatibleImageAdapter
from .qwen import QwenImageAdapter

def get_image_adapter(provider: str) -> ImageAdapter:
    if provider == "qwen":
        return QwenImageAdapter()
    return OpenAICompatibleImageAdapter(provider)