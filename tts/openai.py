import json
import ssl
import urllib.request
import random
import os
from typing import Dict, Any

from . import TTSAdapter
from .. import resolve_api_key_for, get_api_base_for, _proxy_addr_for

def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _adapter_cfg(provider: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    base = os.path.dirname(__file__)
    fname = f"{provider}_config.json"
    defaults = _load_json(os.path.join(base, fname))
    adapters = cfg.get("adapters", {}) or {}
    tts_cfg = adapters.get("tts", {}) or {}
    override = tts_cfg.get(provider, {}) or {}
    merged = {**defaults, **override}
    models = cfg.get("tts_models", {}) or {}
    voices_map = cfg.get("tts_voices_map", {}) or {}
    voice_map = cfg.get("tts_voice_map", {}) or {}
    if provider in models:
        merged["model"] = str(models.get(provider))
    elif "tts_model" in cfg:
        merged["model"] = str(cfg.get("tts_model"))
    if provider in voice_map:
        merged["default_voice"] = str(voice_map.get(provider))
    elif "tts_voice" in cfg:
        merged["default_voice"] = str(cfg.get("tts_voice"))
    pool = voices_map.get(provider, []) or []
    if pool:
        merged["voices_pool"] = pool
    elif "tts_voices" in cfg:
        merged["voices_pool"] = cfg.get("tts_voices", []) or []
    return merged

class OpenAICompatibleTTSAdapter(TTSAdapter):
    def __init__(self, provider: str):
        self.provider = provider
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for(self.provider, cfg)
        conf = _adapter_cfg(self.provider, cfg)
        model = str(conf.get("model", "gpt-4o-mini-tts"))
        pool = conf.get("voices_pool", []) or []
        voice = str(conf.get("default_voice", "alloy"))
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