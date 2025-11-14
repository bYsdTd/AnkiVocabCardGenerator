from __future__ import annotations

import json
import os
import ssl
import traceback
import urllib.request
from typing import Dict, Any

from aqt import mw, gui_hooks
from aqt.qt import QAction, QInputDialog, qconnect
from aqt.utils import tooltip
import random


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
    if not key:
        key = str(cfg.get("openai_api_key", "")).strip()
    return key

def _http_post_json(url: str, data: Dict[str, Any], api_key: str, cfg: Dict[str, Any]) -> Dict[str, Any]:
    """使用 urllib 调 OpenAI API，支持 HTTP 代理（通过 config.json 的 proxy 字段）。"""
    body = json.dumps(data).encode("utf-8")
    req = urllib.request.Request(url, data=body, method="POST")
    req.add_header("Content-Type", "application/json")
    req.add_header("Authorization", f"Bearer {api_key}")

    proxy = cfg.get("proxy", "").strip()

    # SSL 上下文
    ctx = ssl.create_default_context()
    https_handler = urllib.request.HTTPSHandler(context=ctx)

    if proxy:
        log(f"[http] use proxy={proxy} for url={url}")
        proxy_handler = urllib.request.ProxyHandler({
            "http": proxy,
            "https": proxy,
        })
        opener = urllib.request.build_opener(proxy_handler, https_handler)
        resp = opener.open(req, timeout=120)
    else:
        log(f"[http] no proxy for url={url}")
        opener = urllib.request.build_opener(https_handler)
        resp = opener.open(req, timeout=120)

    raw = resp.read().decode("utf-8")
    return json.loads(raw)



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
    resp = _http_post_json(url, payload, api_key, cfg)
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


    url = f"{api_base}/audio/speech"

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
        raw_audio_name = f"{word.strip().lower()}_word.mp3"

        audio_name = ensure_media_file(
            col,
            raw_audio_name,
            lambda: call_openai_tts(f"{word}.", cfg)
        )

        note[f_audio] = f"[sound:{audio_name}]"
        log(f"[note] wrote word audio: {audio_name}")
    else:
        note[f_audio] = ""
        log("[note] skip word audio per config")

    # 例句语音
    if example_text and enable_tts_example:
        raw_example_audio = f"{word.strip().lower()}_example.mp3"

        example_audio_name = ensure_media_file(
            col,
            raw_example_audio,
            lambda: call_openai_tts(example_text, cfg)
        )

        note[f_audio_example] = f"[sound:{example_audio_name}]"
        log(f"[note] wrote example audio: {example_audio_name}")
    elif example_text:
        note[f_audio_example] = ""
        log("[note] skip example audio per config")
    else:
        note[f_audio_example] = ""

    # ---- Image: 助记图（可选） ----
    if cfg.get("enable_image", True):
        try:
            f_image = cfg.get("field_image", "Image")
            # img_bytes = call_openai_image(word, info, cfg)
            # img_fname = f"{word.strip().lower()}_mnemo.png"

            # col.media.write_data(img_fname, img_bytes)
            # note[f_image] = img_fname
            raw_image_name = f"{word.strip().lower()}_mnemo.png"

            image_name = ensure_media_file(
                col,
                raw_image_name,
                lambda: call_openai_image(word, info, cfg)
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

def _background_create_card(word: str) -> None:
    cfg = get_config()
    if not resolve_api_key(cfg):
        mw.taskman.run_on_main(
            lambda: tooltip("请先在 config.json 中设置 openai_api_key")
        )
        log("[bg] openai_api_key missing in config")
        return

    word_clean = word.strip()
    if not word_clean:
        mw.taskman.run_on_main(lambda: tooltip("单词为空"))
        log("[bg] empty word, abort")
        return

    log(f"[bg] start create card for word={word_clean!r}")

    try:
        # Step 1: OpenAI 生成文本信息
        info = call_openai_vocab(word_clean, cfg)
        log(f"[bg] vocab info received: {info}")

        # Step 2: 生成 TTS + 创建 Note
        _create_vocab_note(word_clean, info, cfg)

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
    word, ok = QInputDialog.getText(
        mw, "Create Vocab Card", "请输入一个英文单词："
    )
    if not ok or not word.strip():
        return

    # 后台线程执行（避免 UI 卡死）
    mw.taskman.run_in_background(
        lambda: _background_create_card(word),
        lambda _: None,
    )


def setup_menu() -> None:
    """在 Tools 菜单下添加入口。"""
    log("[init] setup_menu called, adding menu item")
    action = QAction("OpenAI: Create Vocab Card", mw)
    qconnect(action.triggered, on_menu_triggered)
    mw.form.menuTools.addAction(action)


gui_hooks.profile_did_open.append(setup_menu)
log("[init] profile_did_open hook registered")
