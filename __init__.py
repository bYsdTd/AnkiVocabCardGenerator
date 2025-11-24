from __future__ import annotations

import json
import os
import ssl
import traceback
import urllib.request
import urllib.error
from typing import Dict, Any

from aqt import mw, gui_hooks
from aqt.qt import QAction, QDialog, QVBoxLayout, QLabel, QLineEdit, QCheckBox, QDialogButtonBox, qconnect
from aqt.utils import tooltip
import random
import string

# ---------------- 简单日志工具：写到插件目录的 debug.log ---------------- #

def log(msg: str) -> None:
    """Append a log line into this add-on's debug.log file."""
    try:
        base = os.path.dirname(__file__)
        path = os.path.join(base, "debug.log")
        with open(path, "a", encoding="utf-8") as f:
            f.write(msg + "\n")
    except Exception:
        # logging 失败就算了，避免影响主流程
        pass


def get_config() -> Dict[str, Any]:
    return mw.addonManager.getConfig(__name__)


def save_config(cfg: Dict[str, Any]) -> None:
    mw.addonManager.writeConfig(__name__, cfg)


# ---------------- OpenAI 调用封装 ---------------- #

def _read_env_file_key() -> str:
    base = os.path.dirname(__file__)
    path = os.path.join(base, ".env")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                    if k.strip() == "OPENAI_API_KEY":
                        return v.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""

def _read_env_file_var(varname: str) -> str:
    base = os.path.dirname(__file__)
    path = os.path.join(base, ".env")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s or s.startswith("#"):
                    continue
                if "=" in s:
                    k, v = s.split("=", 1)
                    if k.strip() == varname:
                        return v.strip().strip('"').strip("'")
    except Exception:
        return ""
    return ""

def _read_system_prompt() -> str:
    base = os.path.dirname(__file__)
    path = os.path.join(base, "system_prompt.txt")
    if not os.path.exists(path):
        return ""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return ""

def ensure_media_file(col, desired_name: str, generator_fn):
    """
    尝试使用已有媒体文件，如果不存在就调用 generator_fn 生成。
    generator_fn() 必须返回 bytes。
    返回最终文件名（可能是 desired_name 或带 hash 的实际保存名）。
    """
    # 1. 如果已有，直接用
    if col.media.have(desired_name):
        log(f"[media] reuse existing file: {desired_name}")
        return desired_name

    # 2. 没有 → 调用生成器
    log(f"[media] generating new media: {desired_name}")
    data = generator_fn()

    # 3. 写文件（返回实际文件名，可能带 hash 后缀）
    stored_name = col.media.write_data(desired_name, data)
    log(f"[media] stored file as: {stored_name}")

    return stored_name


def resolve_api_key(cfg: Dict[str, Any]) -> str:
    key = os.environ.get("OPENAI_API_KEY", "").strip()
    if not key:
        key = _read_env_file_key().strip()
    return key

def get_api_base_for(provider: str, cfg: Dict[str, Any]) -> str:
    bases = cfg.get("api_bases", {}) or {}
    if provider in bases and str(bases[provider]).strip():
        return str(bases[provider]).strip()
    defaults = {
        "openai": "https://api.openai.com/v1",
        "gemini": "https://generativelanguage.googleapis.com/v1beta/openai",
    }
    return cfg.get("api_base", defaults.get(provider, "https://api.openai.com/v1"))

def get_audio_api_base_for(provider: str, cfg: Dict[str, Any]) -> str:
    bases = cfg.get("api_bases_audio", {}) or {}
    if provider in bases and str(bases[provider]).strip():
        return str(bases[provider]).strip()
    return get_api_base_for(provider, cfg)

def _proxy_addr_for(provider: str, cfg: Dict[str, Any]) -> str:
    m = cfg.get("proxy_enabled_map", {}) or {}
    enabled = bool(m.get(provider, True))
    addr = str(cfg.get("proxy", "")).strip()
    return addr if (enabled and addr) else ""

def resolve_api_key_for(provider: str, cfg: Dict[str, Any]) -> str:
    env_map = {
        "openai": "OPENAI_API_KEY",
        "deepseek": "DEEPSEEK_API_KEY",
        "qwen": "DASHSCOPE_API_KEY",
        "doubao": "DOUBAO_API_KEY",
        "kimi": "MOONSHOT_API_KEY",
        "grok": "XAI_API_KEY",
        "gemini": "GEMINI_API_KEY",
    }
    env_name = env_map.get(provider, "OPENAI_API_KEY")
    key = os.environ.get(env_name, "").strip()
    if not key:
        key = _read_env_file_var(env_name).strip()
    if not key and provider == "openai":
        key = resolve_api_key(cfg)
    return key

def _openai_compatible_vocab(word: str, cfg: Dict[str, Any], provider: str) -> Dict[str, str]:
    api_base = get_api_base_for(provider, cfg)
    api_key = resolve_api_key_for(provider, cfg)
    models = cfg.get("text_models", {}) or {}
    default_models = {"gemini": "gemini-2.0-flash"}
    model = str(models.get(provider, cfg.get("text_model", default_models.get(provider, "gpt-4o-mini"))))
    system_msg = _read_system_prompt()
    params = cfg.get("text_params", {}) or {}
    p = params.get(provider, {}) or {}
    temperature = float(p.get("temperature", 0.4))
    response_format_type = str(p.get("response_format", "json_object")).strip()
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"WORD: {word.strip()}"},
        ],
        "temperature": temperature,
    }
    if response_format_type:
        payload["response_format"] = {"type": response_format_type}
    proxy_addr = _proxy_addr_for(provider, cfg)
    bases = [api_base]
    if provider == "gemini":
        if "openai" in api_base:
            bases.append("https://generativelanguage.googleapis.com/v1beta")
        else:
            bases.append("https://generativelanguage.googleapis.com/v1beta/openai")
    resp = None
    last_err = None
    for b in bases:
        try:
            url = f"{b}/chat/completions"
            resp = _http_post_json(url, payload, api_key, proxy_addr)
            break
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code == 404:
                continue
            raise
    if resp is None:
        raise last_err or RuntimeError("no response")
    content = resp["choices"][0]["message"]["content"]
    content2 = _strip_code_fences(content)
    log(f"[{provider}] raw response: {content2}")
    data = json.loads(content2)
    return {
        "meaning": _str_field(data.get("meaning", "")),
        "example": _str_field(data.get("example", "")),
        "phonetic": _str_field(data.get("phonetic", "")),
        "synonyms": _str_field(data.get("synonyms", "")),
        "notesCN": _str_field(data.get("notesCN", "")),
    }

def _gemini_vocab(word: str, cfg: Dict[str, Any]) -> Dict[str, str]:
    api_base = get_api_base_for("gemini", cfg)
    api_key = resolve_api_key_for("gemini", cfg)
    models = cfg.get("text_models", {}) or {}
    model = str(models.get("gemini", cfg.get("text_model", "gemini-1.5-flash")))
    url = f"{api_base}/v1beta/models/{model}:generateContent?key={api_key}"
    system_msg = _read_system_prompt()
    prompt = f"{system_msg}\nWORD: {word.strip()}\n请仅返回JSON对象。"
    params = cfg.get("text_params", {}) or {}
    p = params.get("gemini", {}) or {}
    temperature = float(p.get("temperature", 0.4))
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature},
    }
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
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
    out = json.loads(raw)
    text = ""
    try:
        text = out["candidates"][0]["content"]["parts"][0]["text"]
    except Exception:
        text = "{}"
    try:
        data = json.loads(text)
    except Exception:
        data = {}
    return {
        "meaning": _str_field(data.get("meaning", "")),
        "example": _str_field(data.get("example", "")),
        "phonetic": _str_field(data.get("phonetic", "")),
        "synonyms": _str_field(data.get("synonyms", "")),
        "notesCN": _str_field(data.get("notesCN", "")),
    }

def call_text(word: str, cfg: Dict[str, Any]) -> Dict[str, str]:
    provider = str(cfg.get("text_provider", "openai_compatible")).strip() or "openai_compatible"
    prov = provider if provider != "openai_compatible" else "openai"
    return _openai_compatible_vocab(word, cfg, prov)

def call_tts(text: str, cfg: Dict[str, Any]) -> bytes:
    provider = str(cfg.get("tts_provider", "openai_compatible")).strip() or "openai_compatible"
    prov = provider if provider != "openai_compatible" else "openai"
    from .tts import get_tts_adapter
    adapter = get_tts_adapter(prov)
    return adapter.synthesize(text, cfg)

def call_image(word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> bytes:
    provider = str(cfg.get("image_provider", "openai_compatible")).strip() or "openai_compatible"
    prov = provider if provider != "openai_compatible" else "openai"
    from .image import get_image_adapter
    adapter = get_image_adapter(prov)
    return adapter.generate(word, info, cfg)

def _http_post_json(url: str, data: Dict[str, Any], api_key: str, proxy_addr: str) -> Dict[str, Any]:
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)

    def _open_with(opener):
        return opener.open(req, timeout=120)

    try:
        if proxy_addr:
            log(f"[http] use proxy={proxy_addr} for url={url}")
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy_addr,
                "https": proxy_addr,
            })
            opener = urllib.request.build_opener(proxy_handler, https_handler)
            resp = _open_with(opener)
        else:
            log(f"[http] no proxy for url={url}")
            opener = urllib.request.build_opener(https_handler)
            resp = _open_with(opener)
    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            err_body = "<no body>"
        log(f"[http] HTTPError {e.code} for {url}: {err_body}")
        if proxy_addr and e.code == 404:
            try:
                log(f"[http] retry without proxy for url={url}")
                no_proxy = urllib.request.ProxyHandler({})
                opener2 = urllib.request.build_opener(no_proxy, https_handler)
                resp = _open_with(opener2)
            except Exception:
                raise
        else:
            raise

    raw = resp.read().decode("utf-8")
    return json.loads(raw)



def _str_field(v: Any) -> str:
    if v is None:
        return ""
    if isinstance(v, str):
        return v.strip()
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, list):
        return ", ".join(_str_field(x) for x in v).strip()
    if isinstance(v, dict):
        try:
            return json.dumps(v, ensure_ascii=False)
        except Exception:
            return str(v)
    return str(v).strip()

def _strip_code_fences(text: str) -> str:
    s = str(text).strip()
    if s.startswith("```"):
        if s.startswith("```json"):
            s = s[len("```json"):].strip()
        else:
            s = s[len("```"):].strip()
        i = s.rfind("```")
        if i != -1:
            s = s[:i].strip()
    return s

def call_openai_vocab(word: str, cfg: Dict[str, Any]) -> Dict[str, str]:
    """
    返回:
      meaning: 英文解释
      example: 例句
      phonetic: 音标
      synonyms: 英文 paraphrase
      notesCN: 例句的中文翻译
    """
    api_base = cfg.get("api_base", "https://api.openai.com/v1")
    api_key = resolve_api_key(cfg)
    model = cfg.get("text_model", "gpt-4o-mini")

    url = f"{api_base}/chat/completions"
    system_msg = _read_system_prompt()

    payload = {
        "model": model,
        "response_format": {"type": "json_object"},
        "messages": [
            {"role": "system", "content": system_msg},
            {"role": "user", "content": f"WORD: {word.strip()}"},
        ],
        "temperature": 0.4,
    }

    log(f"[vocab] request payload for word={word!r}")
    proxy_addr = _proxy_addr_for("openai", cfg)
    resp = _http_post_json(url, payload, api_key, proxy_addr)
    content = resp["choices"][0]["message"]["content"]
    data = json.loads(content)

    result = {
        "meaning": data.get("meaning", "").strip(),
        "example": data.get("example", "").strip(),
        "phonetic": data.get("phonetic", "").strip(),
        "synonyms": data.get("synonyms", "").strip(),
        "notesCN": data.get("notesCN", "").strip(),
    }
    log(f"[vocab] parsed result={result}")
    return result


def call_openai_tts(text: str, cfg: Dict[str, Any]) -> bytes:
    """生成 MP3 语音，支持 HTTP 代理。"""
    api_base = cfg.get("api_base", "https://api.openai.com/v1")
    api_key = resolve_api_key(cfg)
    model = cfg.get("tts_model", "gpt-4o-mini-tts")

    voices = cfg.get("tts_voices", [])
    if voices:
        voice = random.choice(voices)
    else:
        voice = cfg.get("tts_voice", "alloy")


    url = f"{api_base}"

    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "format": "mp3",
    }

    log(f"[tts] request payload={payload}")

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    proxy = cfg.get("proxy", "").strip()

    # SSL 上下文
    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)

    if proxy:
        log(f"[tts] use proxy={proxy} for url={url}")
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy,
            "https": proxy,
        })
        opener = urllib.request.build_opener(proxy_handler, https_handler)
        resp = opener.open(req, timeout=120)
    else:
        log(f"[tts] no proxy for url={url}")
        opener = urllib.request.build_opener(https_handler)
        resp = opener.open(req, timeout=120)

    audio_bytes = resp.read()
    log(f"[tts] generated audio, length={len(audio_bytes)} bytes")
    return audio_bytes

def call_openai_image(word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> bytes:
    """
    调用 OpenAI 图片 API，生成一张帮助记忆该单词的小图。
    返回的是 PNG 的二进制 bytes。
    """
    api_base = cfg.get("api_base", "https://api.openai.com/v1")
    api_key = resolve_api_key(cfg)
    model = cfg.get("image_model", "dall-e-2")

    # dall-e-2 官方支持: 256x256, 512x512, 1024x1024
    size_cfg = cfg.get("image_size", "256x256")
    allowed_sizes = {"256x256", "512x512", "1024x1024"}
    size = size_cfg if size_cfg in allowed_sizes else "256x256"

    # ✅ 正确 endpoint：/v1/images/generations
    url = f"{api_base}/images/generations"

    meaning = info.get("meaning", "")
    example = info.get("example", "")

    prompt = (
        f"Create a very simple, clear, flat illustration that helps remember the English word "
        f"'{word}' meaning: {meaning}. "
        f"Use one concrete scene or object that suggests this idea. "
        f"NO text, NO letters, NO numbers. Minimal style, high contrast, easy to recognize at small size."
    )

    payload = {
        "model": model,
        "prompt": prompt,
        "n": 1,
        "size": size,
        # "response_format": "b64_json",
    }

    log(f"[image] generating image for word={word!r}, size={size}")

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    proxy = cfg.get("proxy", "").strip()
    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)

    try:
        if proxy:
            log(f"[image] use proxy={proxy} for url={url}")
            proxy_handler = urllib.request.ProxyHandler({
                "http": proxy,
                "https": proxy,
            })
            opener = urllib.request.build_opener(proxy_handler, https_handler)
            resp = opener.open(req, timeout=120)
        else:
            opener = urllib.request.build_opener(https_handler)
            resp = opener.open(req, timeout=120)

        raw = resp.read().decode("utf-8")
        data = json.loads(raw)

    except urllib.error.HTTPError as e:
        try:
            err_body = e.read().decode("utf-8", errors="ignore")
        except Exception:
            err_body = "<no body>"
        log(f"[image] HTTPError {e.code}: {err_body}")
        raise
    except Exception as e:
        log(f"[image] unexpected error: {e}")
        raise

    b64 = data["data"][0]["b64_json"]
    import base64
    img_bytes = base64.b64decode(b64)

    log(f"[image] got image bytes length={len(img_bytes)}")
    return img_bytes


def make_cloze_from_word(word: str) -> str:
    """
    根据单词生成一个简单的拼写挖空版本：
    - 保留首尾字母
    - 从中间随机挖掉 30–60% 的字母（只挖字母）
    - 长度 <= 3 的词直接返回原词
    """
    w = word.strip()
    if len(w) <= 3:
        return w

    chars = list(w)
    indices = [i for i, ch in enumerate(chars) if ch.lower() in string.ascii_lowercase]

    # 不挖第一和最后一个字母
    inner_indices = [i for i in indices if i not in (0, len(chars)-1)]
    if not inner_indices:
        return w

    # 挖掉 30%-60% 的中间字母
    n_to_hide = max(1, int(len(inner_indices) * random.uniform(0.7, 0.8)))
    hide_indices = set(random.sample(inner_indices, n_to_hide))

    for i in hide_indices:
        chars[i] = "_"

    return "".join(chars)


# ---------------- 创建 Note ---------------- #

def _create_vocab_note(word: str, info: Dict[str, str], cfg: Dict[str, Any]) -> None:
    """
    创建 VocabularyPro Note，写入到 Vocab 牌组。
    info: meaning / example / phonetic / synonyms / notesCN
    """
    col = mw.col

    deck_name = cfg.get("deck_name", "Vocab")
    model_name = cfg.get("note_type", "VocabularyPro")

    # 字段名
    f_word = cfg.get("field_word", "Word")
    f_meaning = cfg.get("field_meaning", "Meaning")
    f_example = cfg.get("field_example", "Example")
    f_phonetic = cfg.get("field_phonetic", "Phonetic")
    f_audio = cfg.get("field_audio", "Audio")
    f_audio_example = cfg.get("field_audio_example", "AudioExample")
    f_synonyms = cfg.get("field_synonyms", "Synonyms")
    f_notes_cn = cfg.get("field_notes_cn", "NotesCN")
    f_word_cloze = cfg.get("field_word_cloze", "WordCloze")

    # 找 NoteType
    notetype = col.models.by_name(model_name)
    if not notetype:
        raise RuntimeError(f"Note type not found: {model_name}")
    log(f"[note] use notetype={model_name}")

    note = col.new_note(notetype)

    # 写入字段
    note[f_word] = word
    note[f_meaning] = info.get("meaning", "")
    note[f_example] = info.get("example", "")
    note[f_phonetic] = info.get("phonetic", "")
    note[f_synonyms] = info.get("synonyms", "")
    note[f_notes_cn] = info.get("notesCN", "")
    note[f_word_cloze] = make_cloze_from_word(word)

    # 媒体写入
    example_text = info.get("example", "")
    enable_tts_word = bool(cfg.get("enable_tts_word", True))
    enable_tts_example = bool(cfg.get("enable_tts_example", True))

    # 单词语音
    # audio_word = call_openai_tts(f'{word}.', cfg)
    # fname_word = f"{word.strip().lower()}_word.mp3"
    # col.media.write_data(fname_word, audio_word)

    # ---- Word Audio ----
    if enable_tts_word:
        mw.taskman.run_on_main(lambda: mw.progress.update(label="正在合成单词发音…"))
        prov_cfg = str(cfg.get("tts_provider", "openai_compatible")).strip() or "openai_compatible"
        prov = prov_cfg if prov_cfg != "openai_compatible" else "openai"
        from .tts import get_tts_format
        ext = get_tts_format(prov, cfg)
        raw_audio_name = f"{word.strip().lower()}_word.{ext}"

        try:
            audio_name = ensure_media_file(
                col,
                raw_audio_name,
                lambda: call_tts(f"{word}.", cfg)
            )
            note[f_audio] = f"[sound:{audio_name}]"
            log(f"[note] wrote word audio: {audio_name}")
        except Exception:
            note[f_audio] = ""
    else:
        note[f_audio] = ""
        log("[note] skip word audio per config")

    # 例句语音
    if example_text and enable_tts_example:
        mw.taskman.run_on_main(lambda: mw.progress.update(label="正在合成例句发音…"))
        prov_cfg = str(cfg.get("tts_provider", "openai_compatible")).strip() or "openai_compatible"
        prov = prov_cfg if prov_cfg != "openai_compatible" else "openai"
        from .tts import get_tts_format
        ext = get_tts_format(prov, cfg)
        raw_example_audio = f"{word.strip().lower()}_example.{ext}"

        try:
            example_audio_name = ensure_media_file(
                col,
                raw_example_audio,
                lambda: call_tts(example_text, cfg)
            )
            note[f_audio_example] = f"[sound:{example_audio_name}]"
            log(f"[note] wrote example audio: {example_audio_name}")
        except Exception:
            note[f_audio_example] = ""
    elif example_text:
        note[f_audio_example] = ""
        log("[note] skip example audio per config")
    else:
        note[f_audio_example] = ""

    # ---- Image: 助记图（可选） ----
    if cfg.get("enable_image", True):
        mw.taskman.run_on_main(lambda: mw.progress.update(label="正在生成助记图…"))
        try:
            f_image = cfg.get("field_image", "Image")
            # img_bytes = call_openai_image(word, info, cfg)
            # img_fname = f"{word.strip().lower()}_mnemo.png"

            # col.media.write_data(img_fname, img_bytes)
            # note[f_image] = img_fname
            raw_image_name = f"{word.strip().lower()}_mnemo.png"

            image_name = ensure_media_file(
                col,
                f"_{raw_image_name}",
                lambda: call_image(word, info, cfg)
            )

            note[f_image] = image_name

            log(f"[note] wrote image file: {image_name}")
        except Exception as e:
            # 图片失败不要中断整个建卡流程
            log(f"[image] failed to create image for {word!r}: {e}")

    # 牌组 id
    deck = col.decks.by_name(deck_name)
    if not deck:
        # 如果牌组不存在则创建
        deck_id = col.decks.id(deck_name)
        deck = col.decks.get(deck_id)
    deck_id = deck["id"]
    log(f"[note] deck_id={deck_id} for deck={deck_name!r}")

    # 新 API：直接指定 deck_id 创建 note
    # add_note 返回新建卡片数量的 OpChanges，但我们这里只关心 note 本身被添加了
    col.add_note(note, deck_id)
    log(f"[note] note added for word={word!r}")


# ---------------- 后台任务 & 菜单 ---------------- #

def _background_create_card(word: str, enable_image: bool) -> None:
    cfg = get_config()
    prov_cfg = str(cfg.get("text_provider", "openai_compatible")).strip() or "openai_compatible"
    prov = prov_cfg if prov_cfg != "openai_compatible" else "openai"
    key = resolve_api_key_for(prov, cfg)
    if not key:
        mw.taskman.run_on_main(
            lambda: tooltip("请在插件目录 .env 中设置对应 API_KEY")
        )
        log("[bg] api key missing for text provider")
        return

    word_clean = word.strip()
    if not word_clean:
        mw.taskman.run_on_main(lambda: tooltip("单词为空"))
        log("[bg] empty word, abort")
        return

    log(f"[bg] start create card for word={word_clean!r}")

    try:
        cfg2 = dict(cfg)
        cfg2["enable_image"] = enable_image
        mw.taskman.run_on_main(lambda word_clean=word_clean: mw.progress.update(label=f"正在生成 {word_clean} 的词义与示例…"))
        info = call_text(word_clean, cfg2)
        log(f"[bg] vocab info received: {info}")
        mw.taskman.run_on_main(lambda: mw.progress.update(label="正在创建卡片并写入媒体…"))
        _create_vocab_note(word_clean, info, cfg2)

        mw.taskman.run_on_main(
            lambda word_clean=word_clean: tooltip(f"已创建卡片：{word_clean} ✅")
        )
        log(f"[bg] card creation finished for {word_clean!r}")
    except Exception as e:
        trace = traceback.format_exc()
        log("[bg] 创建卡片失败:\n" + trace)
        msg = f"创建卡片失败：{e}"
        mw.taskman.run_on_main(lambda msg=msg: tooltip(msg))


def on_menu_triggered() -> None:
    cfg = get_config()
    dlg = QDialog(mw)
    dlg.setWindowTitle("Create Vocab Card")
    layout = QVBoxLayout(dlg)
    label = QLabel("请输入一个英文单词：", dlg)
    edit = QLineEdit(dlg)
    cb = QCheckBox("生成助记图", dlg)
    cb.setChecked(bool(cfg.get("enable_image", True)))
    layout.addWidget(label)
    layout.addWidget(edit)
    layout.addWidget(cb)
    btns = QDialogButtonBox(
        QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel,
        parent=dlg,
    )
    layout.addWidget(btns)
    qconnect(btns.accepted, dlg.accept)
    qconnect(btns.rejected, dlg.reject)
    if dlg.exec() != QDialog.DialogCode.Accepted:
        return
    word = edit.text()
    if not word.strip():
        return
    enable_image = cb.isChecked()
    mw.progress.start(label="正在生成卡片…", immediate=True)
    mw.taskman.run_in_background(
        lambda: _background_create_card(word, enable_image),
        lambda _: mw.progress.finish(),
    )


def setup_menu() -> None:
    """在 Tools 菜单下添加入口。"""
    log("[init] setup_menu called, adding menu item")
    action = QAction("OpenAI: Create Vocab Card", mw)
    qconnect(action.triggered, on_menu_triggered)
    mw.form.menuTools.addAction(action)


gui_hooks.profile_did_open.append(setup_menu)
log("[init] profile_did_open hook registered")
