import json
import ssl
import urllib.request
import os
from typing import Dict, Any

from . import ImageAdapter
from .. import get_api_base_for, resolve_api_key_for, _proxy_addr_for

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
    image_cfg = adapters.get("image", {}) or {}
    override = image_cfg.get(provider, {}) or {}
    merged = {**defaults, **override}
    models = cfg.get("image_models", {}) or {}
    size_map = cfg.get("image_size_map", {}) or {}
    if provider in models:
        merged["model"] = str(models.get(provider))
    elif "image_model" in cfg:
        merged["model"] = str(cfg.get("image_model"))
    if provider in size_map:
        merged["size"] = str(size_map.get(provider))
    elif "image_size" in cfg:
        merged["size"] = str(cfg.get("image_size"))
    return merged

class OpenAICompatibleImageAdapter(ImageAdapter):
    def __init__(self, provider: str):
        self.provider = provider
    def generate(self, word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> bytes:
        api_base = get_api_base_for(self.provider, cfg)
        api_key = resolve_api_key_for(self.provider, cfg)
        conf = _adapter_cfg(self.provider, cfg)
        model = str(conf.get("model", "dall-e-2"))
        size_cfg = str(conf.get("size", "256x256"))
        allowed_sizes = {"256x256", "512x512", "1024x1024"}
        size = size_cfg if size_cfg in allowed_sizes else "256x256"
        url = f"{api_base}/images/generations"
        meaning = info.get("meaning", "")
        prompt = (
            f"Create a very simple, clear, flat illustration that helps remember the English word "
            f"'{word}' meaning: {meaning}. "
            f"Use one concrete scene or object that suggests this idea. "
            f"NO text, NO letters, NO numbers. Minimal style, high contrast, easy to recognize at small size."
        )
        payload = {"model": model, "prompt": prompt, "n": 1, "size": size}
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
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        b64 = data["data"][0]["b64_json"]
        import base64
        img_bytes = base64.b64decode(b64)
        return img_bytes