from .openai import OpenAICompatibleImageAdapter

class QwenImageAdapter(OpenAICompatibleImageAdapter):
    def __init__(self):
        super().__init__("qwen")