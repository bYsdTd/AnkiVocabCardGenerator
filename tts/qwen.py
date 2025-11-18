import json
import ssl
import urllib.request
from typing import Dict, Any

from . import TTSAdapter
from .. import resolve_api_key_for, get_audio_api_base_for, _proxy_addr_for, log

class QwenTTSAdapter(TTSAdapter):
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for("qwen", cfg)
        tts_models = cfg.get("tts_models", {}) or {}
        model = str(tts_models.get("qwen", cfg.get("tts_model", "qwen3-tts-flash")))
        voices_map = cfg.get("tts_voices_map", {}) or {}
        pool = voices_map.get("qwen", []) or []
        voice_map = cfg.get("tts_voice_map", {}) or {}
        voice = str(voice_map.get("qwen", cfg.get("tts_voice", "alloy")))
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