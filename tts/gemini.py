import json
import ssl
import urllib.request
import os
import io
import wave
import random
from typing import Dict, Any

from . import TTSAdapter
from .. import resolve_api_key_for, _proxy_addr_for

def _load_json(path: str) -> Dict[str, Any]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}

def _adapter_cfg(cfg: Dict[str, Any]) -> Dict[str, Any]:
    base = os.path.dirname(__file__)
    defaults = _load_json(os.path.join(base, "gemini_config.json"))
    adapters = cfg.get("adapters", {}) or {}
    tts_cfg = adapters.get("tts", {}) or {}
    override = tts_cfg.get("gemini", {}) or {}
    merged = {**defaults, **override}
    models = cfg.get("tts_models", {}) or {}
    voices_map = cfg.get("tts_voices_map", {}) or {}
    voice_map = cfg.get("tts_voice_map", {}) or {}
    if "gemini" in models:
        merged["model"] = str(models.get("gemini"))
    elif "tts_model" in cfg:
        merged["model"] = str(cfg.get("tts_model"))
    if "gemini" in voice_map:
        merged["default_voice"] = str(voice_map.get("gemini"))
    elif "tts_voice" in cfg:
        merged["default_voice"] = str(cfg.get("tts_voice"))
    pool = voices_map.get("gemini", []) or []
    if pool:
        merged["voices_pool"] = pool
    elif "tts_voices" in cfg:
        merged["voices_pool"] = cfg.get("tts_voices", []) or []
    return merged

class GeminiTTSAdapter(TTSAdapter):
    def synthesize(self, text: str, cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for("gemini", cfg)
        conf = _adapter_cfg(cfg)
        model = str(conf.get("model", "gemini-2.5-flash-preview-tts"))
        pool = conf.get("voices_pool", []) or []
        voice = str(conf.get("default_voice", "Kore"))
        if pool:
            try:
                voice = random.choice(pool)
            except Exception:
                pass
        base = "https://generativelanguage.googleapis.com/v1beta"
        url = f"{base}/models/{model}:generateContent"
        payload = {
            "contents": [{"parts": [{"text": text}]}],
            "generationConfig": {
                "responseModalities": ["AUDIO"],
                "speechConfig": {
                    "voiceConfig": {
                        "prebuiltVoiceConfig": {
                            "voiceName": voice
                        }
                    }
                }
            },
            "model": model,
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        req.add_header("Content-Type", "application/json")
        req.add_header("x-goog-api-key", api_key)
        proxy = _proxy_addr_for("gemini", cfg)
        ctx = ssl.create_default_context()
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        if proxy:
            proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
            opener = urllib.request.build_opener(proxy_handler, https_handler)
            resp = opener.open(req, timeout=120)
        else:
            opener = urllib.request.build_opener(https_handler)
            resp = opener.open(req, timeout=120)
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        parts = []
        try:
            parts = data["candidates"][0]["content"]["parts"]
        except Exception:
            parts = []
        b64 = ""
        for p in parts:
            try:
                inline = p.get("inline_data") or p.get("inlineData") or {}
                s = inline.get("data", "")
                if s:
                    b64 = s
                    break
            except Exception:
                pass
        if not b64:
            return b""
        import base64
        pcm = base64.b64decode(b64)
        buf = io.BytesIO()
        w = wave.open(buf, "wb")
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(24000)
        w.writeframes(pcm)
        w.close()
        return buf.getvalue()