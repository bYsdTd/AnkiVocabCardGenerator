# OpenAI 英语词汇卡片生成插件（Anki）

[English](README.md) | 简体中文

一个面向英语学习者的 Anki 插件：输入一个英文单词，自动生成词义、例句、音标、近义改写、中文翻译，并生成 TTS 音频，写入到指定牌组与笔记类型中。

## 特性
- 一键生成完整词汇卡片（释义/例句/音标/近义改写/中文翻译）
- 自动生成并插入 MP3 语音（单词与例句）
- 可配置代理、模型与语音参数（支持 `tts_voices` 声音池）
- 可自定义牌组、笔记类型与字段映射
- 适配 Anki 2.1.55+

## 安装
- 将本项目文件夹放入 Anki 用户目录下的 `addons21/AnkiVocabCardGenerator`。
- 或使用 “工具 → 插件 → 从文件夹安装” 导入该目录。
- 重启 Anki。

## 配置
编辑项目根目录下的 `config.json`，至少需要设置 `openai_api_key`（不要将真实密钥提交到任何公共仓库）。示例：

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

- 如果使用代理，确保地址与协议正确（同时用于 HTTP/HTTPS）。
- 可根据需要修改模型与语音参数。若设置了 `tts_voices`，将从列表中随机选择一个声音。
- 牌组与字段名称必须与您的笔记类型一致。
- 系统提示词可在 `system_prompt.txt` 中自定义，无需改动代码。

## 准备笔记类型
插件需要一个名为 `VocabularyPro` 的笔记类型，并包含以下字段：
- `Word`
- `Meaning`
- `Example`
- `Phonetic`
- `Audio`
- `AudioExample`
- `Synonyms`
- `NotesCN`

如未存在，请在 Anki 中创建该笔记类型，并确保字段名称与 `config.json` 中一致。牌组默认使用 `Vocab`，不存在会自动创建。

## 使用方法
- 打开 Anki，进入 “工具 → OpenAI: Create Vocab Card”。
- 输入一个英文单词，插件会在后台生成内容与音频并创建卡片。
- 成功后会出现提示，卡片被添加到 `Vocab` 牌组中。

## 工作原理
- 文本生成：调用 OpenAI Chat Completions，返回严格 JSON 格式（由 `system_prompt.txt` 约束）。
- 语音生成：调用 OpenAI TTS 生成 MP3（默认 `gpt-4o-mini-tts`，支持声音池）。
- 笔记写入：创建并写入字段、保存音频到媒体目录、指定目标牌组。
- 菜单入口：在 Anki 启动后向 “工具” 菜单注册入口。

## 隐私与费用
- 请勿将真实 API 密钥写入版本库。建议以下方式管理密钥：
  - 使用环境变量：在系统中设置 `OPENAI_API_KEY`。
  - 使用本地 `.env` 文件：在插件目录创建 `.env`（已被 `.gitignore` 忽略），内容如 `OPENAI_API_KEY=sk-xxxx`。
  - 仅在 Anki 的插件配置界面填写密钥，不把 `config.json` 推送到公共仓库中包含真实密钥。
- 密钥读取优先级：环境变量 → `.env` → `config.json`。
- 调用 OpenAI 接口可能产生费用，请在使用前确认账户与额度。

## 许可证
本项目采用 MIT 开源许可证，详见 `LICENSE` 文件。