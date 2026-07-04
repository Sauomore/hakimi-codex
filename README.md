# Hakimi Codex - 智能 AI 代码助手 CLI

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.9+-blue.svg" alt="Python 3.9+">
  <img src="https://img.shields.io/badge/Version-0.1.0-green.svg" alt="v0.1.0">
  <img src="https://img.shields.io/badge/License-MIT-green.svg" alt="MIT License">
  <img src="https://img.shields.io/badge/UI-Textual-orange.svg" alt="Textual UI">
</p>

**Hakimi Codex** 是一款对标 [Aider](https://github.com/paul-gauthier/aider)、[OpenAI Codex CLI](https://github.com/openai/codex) 和 [Kimi CLI](https://www.kimi.com) 的现代化 AI 代码助手 CLI 工具，拥有精美的 TUI（终端用户界面）和强大的 Agent 工具链。

---

## 🌟 核心特性

### 相比 Aider

| 特性 | Aider | Hakimi Codex |
|------|-------|-------------|
| 界面 | 基础 CLI | ✅ **Textual TUI，精美界面** |
| 模型管理 | 命令行配置 | ✅ **可视化模型面板，增删改查** |
| 文件浏览 | 无 | ✅ **内置文件树 + 语法高亮** |
| 终端 | 外部终端 | ✅ **内置终端 + 命令历史** |
| 项目分析 | 无 | ✅ **自动检测项目类型/框架** |
| 代码执行 | 无 | ✅ **Python 沙箱执行** |
| 多 Provider | ✅ 多模型 | ✅ **8+ 提供商预设** |

### 相比 OpenAI Codex CLI

| 特性 | Codex CLI | Hakimi Codex |
|------|-----------|-------------|
| 多模型 | 仅 OpenAI | ✅ **OpenAI + Claude + DeepSeek + Gemini + 本地模型** |
| 界面风格 | 简约 | ✅ **中文界面 + 丰富主题** |
| 终端集成 | 基础 | ✅ **内置终端 + 快捷命令** |
| 模型配置 | 环境变量 | ✅ **可视化配置 + 持久化** |
| 代码执行 | ✅ 有 | ✅ **Python 沙箱 + 安全限制** |
| 工具数量 | 4-5 个 | ✅ **8 个工具** |

### 相比 Kimi CLI

| 特性 | Kimi CLI | Hakimi Codex |
|------|----------|-------------|
| 开源 | 闭源 | ✅ **完全开源 MIT** |
| 提供商 | 仅 Kimi | ✅ **多提供商自由切换** |
| 本地运行 | 云端 | ✅ **本地运行 + Ollama 支持** |
| 界面 | 基础 | ✅ **专业 TUI 界面** |
| 工具调用 | ✅ 有 | ✅ **8 个工具 + 项目分析** |
| 自托管 | 不支持 | ✅ **完全自托管** |

---

## 🚀 快速开始

### 安装

```bash
# 克隆仓库
git clone https://github.com/hakimi-team/hakimi-codex.git
cd hakimi-codex

# 安装依赖
pip install -r requirements.txt

# 安装为命令（推荐）
pip install -e .
```

Windows 用户可直接运行 `install.bat` 一键安装。

### 启动

```bash
# 在当前目录启动
hakimi

# 指定项目目录
hakimi /path/to/project

# 查看版本
hakimi --version
```

如果 `hakimi` 命令不在 PATH 中，使用 `python -m codex` 或 `./hakimi.bat`。

---

## 🎨 界面布局

```
┌─────────────────┬──────────────────────────────┬──────────────────┐
│  📁 文件树       │  📄 代码查看器                │  🤖 模型管理      │
│  (可交互)        │  (语法高亮)                   │  (8个预设)       │
│                 │                              │  增删改查        │
├─────────────────┤                              │                  │
│ 📊 Git 状态    │                              │                  │
│ 💻 终端        │                              │                  │
│ (Tab切换)       │                              │                  │
├─────────────────┴──────────────────────────────┴──────────────────┤
│  💬 聊天面板                                                    │
│  流式 AI 响应 + 工具调用 + Markdown 渲染                        │
└─────────────────────────────────────────────────────────────────┘
```

---

## ⌨️ 快捷键

| 快捷键 | 功能 |
|--------|------|
| `q` | 退出应用 |
| `r` | 刷新文件树和 Git 状态 |
| `m` | 模型管理 |
| `c` | 聚焦聊天 |
| `f` | 聚焦文件树 |
| `Ctrl+T` | **切换 Git/终端面板** |
| `Ctrl+S` | 保存当前文件 |
| `↑` / `↓` | 终端命令历史 |

---

## 🤖 支持的 AI 模型（8 个预设）

| 模型 | 提供商 | 上下文 | 备注 |
|------|--------|--------|------|
| GPT-4o | OpenAI | 128K | 旗舰模型 |
| GPT-4o Mini | OpenAI | 128K | 轻量快速 |
| Claude 3.5 Sonnet | Anthropic | 200K | 代码能力最强 |
| Claude 3 Haiku | Anthropic | 200K | 轻量 |
| DeepSeek Chat | DeepSeek | 64K | 中文友好 |
| Gemini 1.5 Pro | Google | 1M | 超长上下文 |
| Mistral Large | Mistral | 32K | 欧洲开源 |
| Llama 3 (Ollama) | 本地 | 8K | **完全本地运行** |

**支持自定义模型**：OpenRouter、本地 API、私有部署等。

---

## 🛠️ 8 大 AI 工具

Hakimi Codex 为 AI 提供了 8 个强大的工具，让 AI 真正成为 Agent：

| # | 工具 | 功能 | 对标 |
|---|------|------|------|
| 1 | `execute_command` | 执行 Shell 命令 | Aider / Codex CLI |
| 2 | `read_file` | 读取文件内容 | Aider / Codex CLI |
| 3 | `write_file` | 写入/修改文件 | Aider / Codex CLI |
| 4 | `list_directory` | 列出目录结构 | Aider / Codex CLI |
| 5 | `search_files` | 代码搜索 | Aider / Codex CLI |
| 6 | `execute_code` | **Python 沙箱执行** | Codex CLI |
| 7 | `analyze_project` | **项目自动分析** | Hakimi 独有 |
| 8 | `web_search` | **网络搜索** | Kimi CLI |

### Agent 工作模式

AI 会自动按照以下模式工作：

1. **分析** → `analyze_project` 了解项目概况
2. **计划** → 制定执行步骤
3. **执行** → 调用工具读写文件、执行命令
4. **验证** → 运行测试确认修改正确

---

## ⚙️ 配置

首次运行自动创建配置：`~/.config/codex/config.toml`

```toml
version = "0.1.0"
active_model_id = "gpt-4o"

[[models]]
id = "gpt-4o"
name = "GPT-4o"
provider = "openai"
model_id = "gpt-4o"
api_key = "sk-..."
temperature = 0.7
max_tokens = 4096
context_window = 128000
enabled = true
is_default = true
```

### 配置步骤

1. 在右上角 **模型管理** 面板选择模型
2. 点击 **编辑** 填入 API Key
3. 点击 **选择** 激活模型
4. 在下方 **聊天面板** 开始对话

---

## 📂 项目结构

```
hakimi_codex/
├── hakimi.bat              # Windows 启动脚本
├── hakimi.sh               # Linux/macOS 启动脚本
├── install.bat             # Windows 一键安装
├── requirements.txt        # 依赖
├── setup.py                # pip 安装配置
├── pyproject.toml          # 项目配置
├── README.md               # 本文档
└── codex/                  # Python 包
    ├── __main__.py         # CLI 入口
    ├── app.py              # 主应用
    ├── core/               # 核心模块
    │   ├── models.py         # 模型定义（8个预设）
    │   ├── config.py         # 配置持久化
    │   ├── llm_client.py     # LLM API 客户端（通用适配）
    │   ├── git_utils.py      # Git 工具
    │   ├── tools.py          # 工具执行引擎（8个工具）
    │   ├── code_sandbox.py   # Python 沙箱执行器
    │   └── project_analyzer.py  # 项目自动分析器
    ├── widgets/            # UI 组件
    │   ├── file_tree.py      # 可交互文件树
    │   ├── chat_panel.py     # 聊天面板（流式响应）
    │   ├── model_selector.py # 模型管理表格
    │   ├── code_view.py      # 代码查看器（语法高亮）
    │   └── terminal_panel.py # 内置终端面板
    ├── screens/            # 界面
    │   ├── splash_screen.py     # ASCII 启动画面
    │   ├── main_screen.py       # 主工作界面（3栏布局）
    │   └── model_edit_dialog.py # 模型编辑弹窗
    └── styles/
        └── codex.tcss        # 主题样式
```

---

## 🔒 安全特性

- **危险命令拦截**：自动阻止 `rm -rf /`、`format c:` 等危险命令
- **Python 沙箱**：代码执行限制系统模块访问
- **工作目录限制**：工具操作限制在项目路径内
- **API Key 安全**：存储在本地配置文件，不上传

---

## 📄 许可证

MIT License - 完全开源，可自由修改和分发。

---

## 🙏 致谢

- [Aider](https://github.com/paul-gauthier/aider) - 代码助手先驱
- [OpenAI Codex CLI](https://github.com/openai/codex) - 官方 Codex CLI
- [Kimi CLI](https://www.kimi.com) - 智能工具链灵感
- [Textual](https://textual.textualize.io/) - 强大的 TUI 框架
