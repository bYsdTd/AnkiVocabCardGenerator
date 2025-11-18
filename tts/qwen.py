import json
import ssl
import urllib.request
import os
from typing import Dict, Any

from . import TTSAdapter
from .. import resolve_api_key_for, get_audio_api_base_for, _proxy_addr_for, log

def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _adapter_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    base = os.path.dirname(__file__)
    defaults = _load_json(os.path.join(base, "qwen_config.json"))
    adapters = cfg.get("adapters", {}) or {}
    tts_cfg = adapters.get("tts", {}) or {}
    override = tts_cfg.get("qwen", {}) or {}
    merged = {**defaults, **override}
    models = cfg.get("tts_models", {}) or {}
    voices_map = cfg.get("tts_voices_map", {}) or {}
    voice_map = cfg.get("tts_voice_map", {}) or {}
    if "qwen" in models:
        merged["model"] = str(models.get("qwen"))
    elif "tts_model" in cfg:
        merged["model"] = str(cfg.get("tts_model"))
    if "qwen" in voice_map:
        merged["default_voice"] = str(voice_map.get("qwen"))
    elif "tts_voice" in cfg:
        merged["default_voice"] = str(cfg.get("tts_voice"))
    pool = voices_map.get("qwen", []) or []
    if pool:
        merged["voices_pool"] = pool
    elif "tts_voices" in cfg:
        merged["voices_pool"] = cfg.get("tts_voices", []) or []
    return merged

class QwenTTSAdapter(TTSAdapter):
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for("qwen", cfg)
        conf = _adapter_cfg(cfg)
        model = str(conf.get("model", "qwen3-tts-flash"))
        pool = conf.get("voices_pool", []) or []
        voice = str(conf.get("default_voice", "Katerina"))
        if pool:
            try:
                import random
                voice = random.choice(pool)
            except Exception:
                pass
        base_audio = get_audio_api_base_for("qwen", cfg)
        url = f"{base_audio}/services/aigc/multimodal-generation/generation"
        payload = {"model": model, "input": {"text": text, "voice": voice}, "stream": False}
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        proxy = _proxy_addr_for("qwen", cfg)
        ctx = ssl.create_default_context()
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        http_handler = urllib.request.HTTPHandler()
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            opener = urllib.request.build_opener(proxy_handler, https_handler, http_handler)
            resp = opener.open(req, timeout=120)
        else:
            opener = urllib.request.build_opener(https_handler, http_handler)
            resp = opener.open(req, timeout=120)
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        try:
            audio_url = data["output"]["audio"]["url"]
        except Exception:
            audio_url = ""
        if not audio_url:
            return b""
        req2 = urllib.request.Request(audio_url, method="GET")
        try:
            if proxy:
                proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                opener = urllib.request.build_opener(proxy_handler, https_handler, http_handler)
                resp2 = opener.open(req2, timeout=120)
            else:
                opener = urllib.request.build_opener(https_handler, http_handler)
                resp2 = opener.open(req2, timeout=120)
            return resp2.read()
        except Exception as e:
            log(f"[tts] media download via proxy failed: {e}, retry direct")
            no_proxy = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(no_proxy, https_handler, http_handler)
            resp2 = opener.open(req2, timeout=120)
            return resp2.read()