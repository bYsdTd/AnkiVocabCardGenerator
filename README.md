# OpenAI English Vocab Card Generator for Anki

[English](README.md) | [简体中文](README.zh-CN.md)

An Anki add-on for English learners: input a headword and automatically generate definition, example sentence, phonetic (IPA), paraphrase/synonyms, Chinese translation, and TTS audio, then write everything into your target deck and note type.

## Features
- One-click creation of a complete vocab card (definition/example/IPA/paraphrase/Chinese translation)
- Auto-generate and insert MP3 audio (word and example sentence)
- Configurable proxy, models, and voice parameters (supports `tts_voices` pool)
- Customizable deck, note type, and field mapping
- Works with Anki 2.1.55+

## Installation
- Copy this folder into your Anki user directory at `addons21/AnkiVocabCardGenerator`.
- Or use “Tools → Add-ons → Install from folder” to import this directory.
- Restart Anki.

## Configuration
Edit `config.json` in the project root. You must set `openai_api_key`. Example:

```json
{
  "openai_api_key": "sk-xxxx...",
  "api_base": "https://api.openai.com/v1",
  "proxy": "http://127.0.0.1:8118",

  "text_model": "gpt-4o-mini",
  "tts_model": "gpt-4o-mini-tts",
  "tts_voice": "alloy",
  "tts_voices": ["alloy", "ash", "ballad", "coral", "echo", "fable", "onyx", "nova", "sage", "shimmer", "verse"],

  "deck_name": "Vocab",
  "note_type": "VocabularyPro",

  "field_word": "Word",
  "field_meaning": "Meaning",
  "field_example": "Example",
  "field_phonetic": "Phonetic",
  "field_audio": "Audio",
  "field_audio_example": "AudioExample",
  "field_synonyms": "Synonyms",
  "field_notes_cn": "NotesCN"
}
```

- If using a proxy, ensure the address and protocol are correct (used for HTTP/HTTPS).
- Tweak models and voice settings as needed. If `tts_voices` is set, a voice is chosen randomly from the list.
- Deck and field names must match your note type.
- The system prompt is externalized in `system_prompt.txt` so you can edit it without changing code.

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

If it doesn’t exist, create it in Anki and ensure field names match `config.json`. The deck defaults to `Vocab` and is created automatically if missing.

## Usage
- Open Anki and go to “Tools → OpenAI: Create Vocab Card”.
- Enter an English word; the add-on will generate content and audio in the background and create the card.
- A tooltip confirms success and the card is added to the `Vocab` deck.

## How It Works
- Text generation: calls OpenAI Chat Completions and returns strict JSON (guided by `system_prompt.txt`).
- Audio generation: calls OpenAI TTS to produce MP3 (default `gpt-4o-mini-tts`, voice can be randomized via `tts_voices`).
- Note writing: creates the note, writes fields, saves audio to media, and targets the desired deck.
- Menu entry: registers a Tools menu action on profile open.

## Privacy & Costs
- Never commit real API keys. Recommended management:
  - Environment variable: set `OPENAI_API_KEY` at OS level
  - Local `.env` file in the add-on directory (ignored by `.gitignore`), e.g. `OPENAI_API_KEY=sk-xxxx`
  - Enter the key via Anki’s add-on config UI; don’t push real keys in `config.json`
- Key resolution order: environment → `.env` → `config.json`.
- OpenAI usage may incur costs; ensure your account has quota.

## License
MIT License. See `LICENSE`.