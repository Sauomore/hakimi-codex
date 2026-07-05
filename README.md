# Hakimi Codex

一个现代化的 AI 代码助手 CLI 工具。

---

## Features

- Clean TUI Interface - Textual-based terminal UI, no emojis, high contrast
- Single-window chat layout - messages flow top to bottom
- Inline diff rendering - red/green line highlighting for code changes
- File modification preview - shows diff before applying changes
- "Thinking..." indicator while waiting for AI response
- Command System - `/` prefix commands for all operations
- 8 AI Tools - Command execution, file read/write, directory listing, search, code sandbox, project analysis
- Settings Management - Stream output, thinking mode, temperature, etc.
- No preset models - add any model via CLI command

---

## Known Issues

- **Streaming output**: Currently has display issues (double rendering, Markdown parsing inconsistency). A fix is planned for the next update. Disable streaming with `/setting stream=false` for stable output.

---

## Quick Start

```bash
# Install
pip install -r requirements.txt
pip install -e .

# Launch in current directory
hakimi

# Or specify project directory
hakimi /path/to/project
```

---

## First Time Setup - Add a Model

Hakimi does not ship with preset models. You must add your own via the `/model add` command.

### Quick Add (shorthand format)

```bash
# DeepSeek V3
/model add deepseek-v3 sk-your-api-key deepseek

# DeepSeek V4 Pro
/model add deepseek-v4 sk-your-api-key deepseek

# DeepSeek Flash
/model add deepseek-flash sk-your-api-key deepseek

# OpenAI GPT-4o
/model add gpt-4o sk-your-api-key openai

# Claude 3.5 Sonnet
/model add claude-3-5-sonnet-20241022 sk-your-api-key anthropic

# Google Gemini
/model add gemini-1.5-pro sk-your-api-key google

# Mistral
/model add mistral-large-latest sk-your-api-key mistral

# Local Ollama
/model add llama3.1 http://localhost:11434 ollama
```

### Full Format (key-value pairs)

```bash
/model add name="My DeepSeek" model_id=deepseek-v3 api_key=sk-xxx provider=deepseek
```

### Auto-detected Providers

If you omit the provider, Hakimi auto-detects from the model ID:

| Keyword in model_id | Provider |
|---------------------|----------|
| `deepseek` | deepseek |
| `gpt`, `o1`, `o3` | openai |
| `claude` | anthropic |
| `gemini` | google |
| `mistral` | mistral |
| `llama`, `qwen` | ollama |
| (other) | custom |

### After Adding

```bash
/model list              # see all added models
/model select deepseek-v3   # activate a model
```

---

## Commands

### Model Management

| Command | Description | Example |
|---------|-------------|---------|
| `/model add <model_id> <api_key> [provider]` | Add a new model | `/model add deepseek-v3 sk-xxx deepseek` |
| `/model list` | List all added models | `/model list` |
| `/model select <id>` | Activate a model | `/model select deepseek-v3` |
| `/model delete <id>` | Remove a model | `/model delete deepseek-v3` |

### Settings

| Command | Description | Example |
|---------|-------------|---------|
| `/setting` | Show all current settings | `/setting` |
| `/setting stream=false` | Disable streaming output | `/setting stream=false` |
| `/setting temperature=0.5` | Change temperature | `/setting temperature=0.5` |
| `/setting think_mode=false` | Disable thinking output | `/setting think_mode=false` |

### File & Code

| Command | Description | Example |
|---------|-------------|---------|
| `/file <path>` | Load file into context | `/file src/main.py` |
| `/diff` | Show diff for current file | `/diff` |

### Shell & Git

| Command | Description | Example |
|---------|-------------|---------|
| `/run <command>` | Execute shell command | `/run python -m pytest` |
| `/status` | Show project & git status | `/status` |
| `/commit [message]` | Git commit all changes | `/commit "fix: bug"` |

### Session

| Command | Description |
|---------|-------------|
| `/clear` | Clear chat history |
| `/help` | Show all commands |
| `/exit` | Quit application |

---

## Settings

| Setting | Type | Default | Description |
|---------|------|---------|-------------|
| `stream` | bool | `true` | Stream output |
| `think_mode` | bool | `true` | Show thinking content |
| `think_fold` | bool | `true` | Collapse thinking by default |
| `think_lines` | int | `2` | Lines shown when folded |
| `temperature` | float | `0.7` | AI temperature |
| `show_tool_results` | bool | `true` | Show tool execution results |
| `tool_results_fold` | bool | `true` | Collapse tool results by default |
| `auto_analyze` | bool | `true` | Auto analyze project on start |

---

## Layout

```
+-------------------------------------------------------+
|  Hakimi v0.2.2 | project-name | model:deepseek-v3     |
+-------------------------------------------------------+
|                                                       |
|  Welcome to Hakimi Codex v0.2.2                       |
|  Project: /path/to/project                            |
|  Type /help for all commands                          |
|                                                       |
|  > hello                                              |
|  Hi! How can I help you today?                        |
|                                                       |
|  --- diff                                             |
|  - def old_func():                                    |
|  + def new_func():                                    |
|  ---                                                  |
|                                                       |
|  [tool: execute_command]                              |
|  $ python -m pytest                                   |
|  =================== 3 passed ===================      |
|                                                       |
+-------------------------------------------------------+
|  > Type a message or /command...                      |
|  Ctrl+C to quit | /help | /model to configure         |
+-------------------------------------------------------+
```

---

## Project Structure

```
hakimi_codex/
├── codex/
│   ├── core/
│   │   ├── models.py            # Model definitions
│   │   ├── config.py            # Config persistence
│   │   ├── llm_client.py        # LLM API client
│   │   ├── tools.py             # Tool execution engine
│   │   ├── code_sandbox.py      # Python sandbox
│   │   ├── project_analyzer.py  # Project auto-detection
│   │   ├── settings_manager.py  # Settings management
│   │   └── command_handler.py   # Command processor
│   ├── screens/
│   │   ├── main_screen.py       # Main chat layout
│   │   └── model_edit_dialog.py # Model editor
│   ├── styles/
│   │   └── codex.tcss           # Theme styles
│   ├── app.py                   # Main app
│   └── __main__.py              # CLI entry
├── hakimi.bat                   # Windows launcher
├── requirements.txt
├── setup.py
└── README.md
```

---

## License

MIT License
