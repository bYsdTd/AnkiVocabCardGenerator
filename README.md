# English Vocab Card Generator for Anki (OpenAI / Gemini / Qwen)

[English](README.md) | [简体中文](README.zh-CN.md)

An Anki add-on for English learners. Enter a headword and it automatically generates definition, example sentence, phonetic (IPA), paraphrase/synonyms, Chinese translation, word cloze, optional mnemonic image, and TTS audio, then writes everything into your target deck and note type. Supports multiple providers: OpenAI‑compatible (OpenAI, DeepSeek, Qwen, Kimi, Grok) and Gemini.

## Features
- One-click vocab card: meaning, example, IPA, paraphrase/synonyms, Chinese translation, cloze
- Auto-generate and insert audio for word and example (mp3/wav depending on provider)
- Optional mnemonic image field; media cached to avoid duplicate calls
- Multi-provider: OpenAI‑compatible (OpenAI/DeepSeek/Qwen/Kimi/Grok) and Gemini
- Per-provider proxy, models, and voice pools; random voice selection supported
- Customizable deck, note type, and field mapping; Anki 2.1.55+

## Installation
- Copy this folder into your Anki user directory at `addons21/AnkiVocabCardGenerator`.
- Or use “Tools → Add-ons → Install from folder” to import this directory.
- Restart Anki.

## Configuration
Edit `config.json` in the project root. Choose providers and tune models/voices. API keys are read from environment variables or a local `.env` file (no real keys in VCS).

Example:

```json
{
  "proxy": "http://127.0.0.1:8118",
  "proxy_enabled_map": {
    "openai": true,
    "deepseek": false,
    "qwen": false,
    "kimi": false,
    "grok": false,
    "gemini": true
  },

  "text_provider": "gemini",
  "tts_provider": "gemini",
  "image_provider": "gemini",

  "api_bases": {
    "openai": "https://api.openai.com/v1",
    "deepseek": "https://api.deepseek.com/v1",
    "qwen": "https://dashscope.aliyuncs.com/compatible-mode/v1",
    "kimi": "https://api.moonshot.cn/v1",
    "grok": "https://api.x.ai/v1",
    "gemini": "https://generativelanguage.googleapis.com/v1beta/openai"
  },
  "api_bases_audio": {
    "qwen": "https://dashscope.aliyuncs.com/api/v1"
  },

  "text_models": {
    "openai": "gpt-4o-mini",
    "deepseek": "deepseek-chat",
    "qwen": "qwen-flash",
    "kimi": "moonshot-v1-8k",
    "grok": "grok-2-mini",
    "gemini": "gemini-2.5-pro"
  },
  "text_params": {
    "openai": {"temperature": 0.4, "response_format": "json_object"},
    "deepseek": {"temperature": 0.4, "response_format": "json_object"},
    "qwen": {"temperature": 0.4, "response_format": "json_object"},
    "kimi": {"temperature": 0.4, "response_format": "json_object"},
    "grok": {"temperature": 0.4, "response_format": "json_object"},
    "gemini": {"temperature": 0.4}
  },

  "enable_tts_word": true,
  "enable_tts_example": true,
  "enable_image": true,
  "field_image": "Image",

  "deck_name": "Vocab",
  "note_type": "VocabularyPro",

  "field_word": "Word",
  "field_meaning": "Meaning",
  "field_example": "Example",
  "field_phonetic": "Phonetic",
  "field_audio": "Audio",
  "field_audio_example": "AudioExample",
  "field_synonyms": "Synonyms",
  "field_notes_cn": "NotesCN",
  "field_word_cloze": "WordCloze"
}
```

- If using a proxy, ensure address and protocol are correct. You can enable/disable per provider via `proxy_enabled_map`.
- `text_provider`, `tts_provider`, and `image_provider` select which backend to use. Models can be overridden per provider via `text_models`, `tts_models`, `image_models` or via adapter configs in `tts/*_config.json` and `image/*_config.json`.
- The system prompt is in `system_prompt.txt` so you can edit it without changing code.
- Audio format is provider-specific (mp3 or wav) and the correct extension is auto-selected.

## Prepare the Note Type
Create a note type named `VocabularyPro` with these fields:
- `Word`
- `Meaning`
- `Example`
- `Phonetic`
- `Audio`
- `AudioExample`
- `Synonyms`
- `NotesCN`
- `WordCloze`
- `Image` (optional)

Ensure field names match `config.json`. The deck defaults to `Vocab` and is created automatically if missing. Audio fields are filled with Anki `[sound:filename]` tags.

## Usage
- Open Anki and go to “Tools → OpenAI: Create Vocab Card”.
- Enter an English word and optionally enable “Generate Mnemonic Image”.
- Content is generated in the background and the card is created; a tooltip confirms success and the card is added to the `Vocab` deck.

## How It Works
- Text generation: provider-specific endpoints unify to an OpenAI‑compatible payload; strict JSON is enforced by `system_prompt.txt` (`__init__.py` orchestrates calls).
- Audio generation: pluggable adapters under `tts/` select provider and voice; audio is cached in media with correct extension.
- Image generation: pluggable adapters under `image/` can create a small mnemonic image and cache it.
- Note writing: fields are populated, audio/image saved to media, and the target deck is used.
- Menu entry: on profile open, a Tools menu action is registered for quick access.

## Privacy & Costs
- Do not commit real API keys.
- Key resolution order: environment → `.env` → `config.json`.
- Supported environment variable names:
  - `OPENAI_API_KEY`, `DEEPSEEK_API_KEY`, `DASHSCOPE_API_KEY` (Qwen), `DOUBAO_API_KEY`, `MOONSHOT_API_KEY` (Kimi), `XAI_API_KEY` (Grok), `GEMINI_API_KEY`.
- You may create a local `.env` file in the add-on directory (ignored by `.gitignore`) containing lines like `GEMINI_API_KEY=xxxxx`.
- API usage may incur costs; ensure your account has quota.

## License
MIT License. See `LICENSE`.

## Project Structure

```
AnkiVocabCardGenerator/
├── __init__.py              # Add-on entrypoint: menu, background tasks, orchestration
├── manifest.json            # Anki add-on metadata
├── config.json              # Providers, models, proxy, fields, deck/note config
├── system_prompt.txt        # System prompt for strict JSON output
├── image/
│   ├── __init__.py          # Image adapter registry
│   ├── openai.py            # OpenAI‑compatible image generation
│   ├── gemini.py            # Gemini image generation
│   ├── qwen.py              # Qwen (DashScope) image generation
│   ├── openai_config.json   # Default model/size for OpenAI images
│   └── qwen_config.json     # Default model/size for Qwen images
├── tts/
│   ├── __init__.py          # TTS adapter registry and format chooser
│   ├── openai.py            # OpenAI‑compatible TTS
│   ├── gemini.py            # Gemini TTS (wav)
│   ├── qwen.py              # Qwen TTS via DashScope
│   ├── openai_config.json   # Default model/voice/format
│   ├── gemini_config.json   # Default model/voice/format
│   └── qwen_config.json     # Default model/voice/format
├── README.md                # English documentation
├── README.zh-CN.md          # Simplified Chinese documentation
├── LICENSE                  # MIT license
└── debug.log                # Runtime log created at add-on root
```