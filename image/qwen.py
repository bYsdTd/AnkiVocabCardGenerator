import json
import ssl
import urllib.request
import urllib.error
import os
from typing import Dict, Any

from . import ImageAdapter
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
    image_cfg = adapters.get("image", {}) or {}
    override = image_cfg.get("qwen", {}) or {}
    merged = {**defaults, **override}
    models = cfg.get("image_models", {}) or {}
    size_map = cfg.get("image_size_map", {}) or {}
    if "qwen" in models:
        merged["model"] = str(models.get("qwen"))
    elif "image_model" in cfg:
        merged["model"] = str(cfg.get("image_model"))
    if "qwen" in size_map:
        merged["size"] = str(size_map.get("qwen"))
    elif "image_size" in cfg:
        merged["size"] = str(cfg.get("image_size"))
    return merged

class QwenImageAdapter(ImageAdapter):
    def generate(self, word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> bytes:
        api_key = resolve_api_key_for("qwen", cfg)
        conf = _adapter_cfg(cfg)
        model = str(conf.get("model", "qwen-image-plus"))
        size_cfg = str(conf.get("size", "1328x1328"))
        size_dash = size_cfg.replace("x", "*")
        base_image = get_audio_api_base_for("qwen", cfg)
        url = f"{base_image}/services/aigc/multimodal-generation/generation"
        meaning = info.get("meaning", "")
        prompt = (
            f"Create a very simple, clear, flat illustration that helps remember the English word "
            f"'{word}' meaning: {meaning}. "
            f"Use one concrete scene or object that suggests this idea. "
            f"NO text, NO letters, NO numbers. Minimal style, high contrast, easy to recognize at small size."
        )
        payload = {
            "model": model,
            "input": {
                "messages": [
                    {
                        "role": "user",
                        "content": [
                            {"text": prompt}
                        ]
                    }
                ]
            },
            "parameters": {
                "negative_prompt": "",
                "prompt_extend": True,
                "watermark": False,
                "size": size_dash
            }
        }
        body = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(url, data=body, method="POST")
        log(f"[image] qwen image generation request: url={url}, body={body.decode('utf-8')}")
        req.add_header("Content-Type", "application/json")
        req.add_header("Authorization", f"Bearer {api_key}")
        proxy = _proxy_addr_for("qwen", cfg)
        ctx = ssl.create_default_context()
        https_handler = urllib.request.HTTPSHandler(context=ctx)
        http_handler = urllib.request.HTTPHandler()
        try:
            if proxy:
                proxy_handler = urllib.request.ProxyHandler({"http": proxy, "https": proxy})
                opener = urllib.request.build_opener(proxy_handler, https_handler, http_handler)
                resp = opener.open(req, timeout=120)
            else:
                opener = urllib.request.build_opener(https_handler, http_handler)
                resp = opener.open(req, timeout=120)
        except urllib.error.HTTPError as e:
            try:
                err_body = e.read().decode("utf-8", errors="ignore")
            except Exception:
                err_body = "<no body>"
            log(f"[image] qwen HTTPError {e.code}: {err_body}")
            raise
        raw = resp.read().decode("utf-8")
        data = json.loads(raw)
        try:
            choices = data["output"]["choices"]
            msg = choices[0]["message"]
            content = msg["content"][0]
            url2 = content.get("image", "")
        except Exception:
            url2 = ""
        if not url2:
            raise RuntimeError("qwen image generation: missing image URL in response")
        req2 = urllib.request.Request(url2, method="GET")
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
            log(f"[image] media download via proxy failed: {e}, retry direct")
            no_proxy = urllib.request.ProxyHandler({})
            opener = urllib.request.build_opener(no_proxy, https_handler, http_handler)
            resp2 = opener.open(req2, timeout=120)
            return resp2.read()