import json
import ssl
import urllib.request
import random
from typing import Dict, Any

from . import TTSAdapter
from .. import resolve_api_key_for, get_api_base_for, _proxy_addr_for

class OpenAICompatibleTTSAdapter(TTSAdapter):
    def __init__(self, provider: str):
        self.provider = provider
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for(self.provider, cfg)
        tts_models = cfg.get("tts_models", {}) or {}
        model = str(tts_models.get(self.provider, cfg.get("tts_model", "gpt-4o-mini-tts")))
        voices_map = cfg.get("tts_voices_map", {}) or {}
        pool = voices_map.get(self.provider, []) or []
        voice_map = cfg.get("tts_voice_map", {}) or {}
        voice = str(voice_map.get(self.provider, cfg.get("tts_voice", "alloy")))
        if pool:
            try:
                voice = random.choice(pool)
            except Exception:
                pass
        api_base = get_api_base_for(self.provider, cfg)
        url = f"{api_base}/audio/speech"
        payload = {"model": model, "voice": voice, "input": text, "format": "mp3"}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        proxy = _proxy_addr_for(self.provider, cfg)
        ctx = ssl.create_default_context()
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            opener = urllib.request.build_opener(proxy_handler, https_handler)
            resp = opener.open(req, timeout=120)
        else:
            opener = urllib.request.build_opener(https_handler)
            resp = opener.open(req, timeout=120)
        return resp.read()