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
    model = cfg.get("tts_model", "tts-1")
    voice = cfg.get("tts_voice", "alloy")

    url = f"{api_base}/audio/speech"

    payload = {
        "model": model,
        "voice": voice,
        "input": text,
        "format": "mp3",
    }

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

    # 单词语音
    audio_word = call_openai_tts(word, cfg)
    fname_word = f"{word.strip().lower()}_word.mp3"
    col.media.write_data(fname_word, audio_word)
    note[f_audio] = f"[sound:{fname_word}]"
    log(f"[note] wrote word audio: {fname_word}")

    # 例句语音
    if example_text:
        audio_example = call_openai_tts(example_text, cfg)
        fname_example = f"{word.strip().lower()}_example.mp3"
        col.media.write_data(fname_example, audio_example)
        note[f_audio_example] = f"[sound:{fname_example}]"
        log(f"[note] wrote example audio: {fname_example}")
    else:
        note[f_audio_example] = ""

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
