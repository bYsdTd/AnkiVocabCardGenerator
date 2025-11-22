# 英语词汇卡片生成插件（Anki，支持 OpenAI / Gemini / Qwen）

[English](README.md) | 简体中文

一个面向英语学习者的 Anki 插件：输入英文单词，自动生成词义、例句、音标（IPA）、近义改写、中文翻译、拼写挖空（WordCloze）、可选助记图，并生成 TTS 音频，写入到指定牌组与笔记类型。支持多种提供方：OpenAI 兼容（OpenAI、DeepSeek、Qwen、Kimi、Grok）与 Gemini。

## 特性
- 一键生成：词义、例句、音标、近义改写、中文翻译、拼写挖空
- 自动生成并插入语音（单词与例句，mp3/wav 视提供方而定）
- 可选助记图字段；媒体使用缓存，避免重复调用
- 多提供方：OpenAI 兼容（OpenAI/DeepSeek/Qwen/Kimi/Grok）与 Gemini
- 按提供方配置代理、模型与声音池；支持随机选择声音
- 可自定义牌组、笔记类型与字段映射；适配 Anki 2.1.55+

## 安装
- 将本项目文件夹放入 Anki 用户目录下的 `addons21/AnkiVocabCardGenerator`。
- 或使用 “工具 → 插件 → 从文件夹安装” 导入该目录。
- 重启 Anki。

## 配置
编辑项目根目录下的 `config.json`，选择提供方并调整模型/声音。API 密钥从环境变量或本地 `.env` 文件读取（不要将真实密钥提交到版本库）。

示例：

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

- 如需代理，确保地址与协议正确。可通过 `proxy_enabled_map` 按提供方开关代理。
- `text_provider`、`tts_provider`、`image_provider` 用于选择各自后端。模型可通过 `text_models`、`tts_models`、`image_models` 覆盖，或使用 `tts/*_config.json` 与 `image/*_config.json` 中的适配器配置。
- 系统提示词位于 `system_prompt.txt`，可直接编辑。
- 音频格式由提供方决定（mp3 或 wav），会自动选择相应扩展名。

## 准备笔记类型
创建一个名为 `VocabularyPro` 的笔记类型，包含以下字段：
- `Word`
- `Meaning`
- `Example`
- `Phonetic`
- `Audio`
- `AudioExample`
- `Synonyms`
- `NotesCN`
- `WordCloze`
- `Image`（可选）

确保字段名称与 `config.json` 一致。默认牌组为 `Vocab`，如不存在会自动创建。音频字段将自动填入 Anki 的 `[sound:文件名]` 标签。

## 使用方法
- 打开 Anki，进入 “工具 → OpenAI: Create Vocab Card”。
- 输入英文单词，并可勾选 “生成助记图”。
- 插件在后台生成内容与音频并创建卡片；成功后出现提示，卡片被添加到 `Vocab` 牌组。

## 工作原理
- 文本生成：统一为 OpenAI 兼容负载的调用方式；`system_prompt.txt` 约束输出 JSON（由 `__init__.py` 编排）。
- 语音生成：`tts/` 下的适配器选择提供方与声音；音频按扩展名写入并缓存。
- 图片生成：`image/` 下的适配器按需生成助记图并缓存。
- 笔记写入：填充字段、保存音频/图片到媒体目录、写入目标牌组。
- 菜单入口：在用户档案打开时注册 “工具” 菜单动作。

## 隐私与费用
- 请勿将真实 API 密钥写入版本库。
- 密钥读取优先级：环境变量 → `.env` → `config.json`。
- 支持的环境变量名称：
  - `OPENAI_API_KEY`、`DEEPSEEK_API_KEY`、`DASHSCOPE_API_KEY`（Qwen）、`DOUBAO_API_KEY`、`MOONSHOT_API_KEY`（Kimi）、`XAI_API_KEY`（Grok）、`GEMINI_API_KEY`。
- 可在插件目录创建本地 `.env` 文件（已在 `.gitignore` 忽略），如 `GEMINI_API_KEY=xxxxx`。
- 使用各提供方接口可能产生费用，请确保账户额度充足。

## 许可证
本项目采用 MIT 开源许可证，详见 `LICENSE` 文件。

## 项目结构

```
AnkiVocabCardGenerator/
├── __init__.py              # 插件入口：菜单、后台任务、调用编排
├── manifest.json            # Anki 插件元数据
├── config.json              # 提供方、模型、代理、字段、牌组/笔记类型配置
├── system_prompt.txt        # 系统提示词（约束输出 JSON）
├── image/
│   ├── __init__.py          # 图片适配器注册
│   ├── openai.py            # OpenAI 兼容图片生成
│   ├── gemini.py            # Gemini 图片生成
│   ├── qwen.py              # Qwen（DashScope）图片生成
│   ├── openai_config.json   # OpenAI 图片默认模型/尺寸
│   └── qwen_config.json     # Qwen 图片默认模型/尺寸
├── tts/
│   ├── __init__.py          # TTS 适配器注册与格式选择
│   ├── openai.py            # OpenAI 兼容 TTS
│   ├── gemini.py            # Gemini TTS（wav）
│   ├── qwen.py              # Qwen TTS（DashScope）
│   ├── openai_config.json   # 默认模型/声音/格式
│   ├── gemini_config.json   # 默认模型/声音/格式
│   └── qwen_config.json     # 默认模型/声音/格式
├── README.md                # 英文文档
├── README.zh-CN.md          # 中文文档
├── LICENSE                  # MIT 许可证
└── debug.log                # 运行时日志（自动生成）
```