# Hakimi Codex

现代化 AI 代码助手 CLI 工具，基于 [Textual](https://textual.textualize.io/) 构建 TUI 界面，支持多 Agent 协作、工具调用、代码生成与项目分析。

---

## 目录

- [功能特性](#功能特性)
- [安装](#安装)
- [快速开始](#快速开始)
- [命令列表](#命令列表)
- [界面说明](#界面说明)
- [多 Agent 协作模式](#多-agent-协作模式)
- [可用工具](#可用工具)
- [配置说明](#配置说明)
- [项目结构](#项目结构)
- [支持的模型](#支持的模型)
- [开发计划](#开发计划)
- [常见问题](#常见问题)
- [贡献](#贡献)
- [许可证](#许可证)

---

## 功能特性

- 🖥️ **现代化 TUI 界面**：基于 `textual` 的终端用户界面，支持分栏、快捷键、主题色
- 🤖 **多 Agent 协作流水线**：planner、coder、reviewer、tester 协同完成复杂任务
- 🛠️ **工具调用系统**：文件读写、命令执行、代码执行、目录浏览、文本搜索、网络搜索
- 🧠 **思考过程可视化**：支持显示/隐藏 LLM 的 thinking 内容
- 📝 **代码生成与写入**：自动生成源码文件，支持写入前确认
- 🔍 **项目分析**：自动识别项目类型、框架与依赖
- 🌐 **多模型支持**：兼容 OpenAI API 格式，支持 DeepSeek、OpenAI、Kimi 等
- ⚙️ **丰富的设置项**：运行时通过 `/setting` 动态调整行为
- 🪟 **Windows 友好**：针对 Windows PowerShell/cmd 做了编码和命令兼容处理

---

## 安装

### 环境要求

- Python >= 3.9
- Git
- 一个兼容 OpenAI API 的 LLM API Key

### 从源码安装

```bash
# 克隆仓库
git clone git@github.com:Sauomore/hakimi-codex.git
cd hakimi-codex

# 创建虚拟环境（推荐）
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

# 安装依赖
pip install -e .
```

### 验证安装

```bash
hakimi --version
```

---

## 快速开始

### 1. 启动

```bash
# 在当前目录启动
hakimi

# 在指定项目目录启动
hakimi /path/to/project
```

### 2. 配置模型

启动后输入：

```text
/model
```

按提示填写：

- Provider（如 `openai`、`deepseek`）
- Model ID（如 `deepseek-chat`、`gpt-4o`）
- API Key
- Base URL（可选，留空使用默认）

也可以使用快速添加命令：

```text
/model add deepseek-v3 sk-your-api-key deepseek
/model add gpt-4o sk-your-api-key openai
/model add kimi-k2.6 sk-your-api-key kimi
```

### 3. 开始对话

在底部输入框输入你的需求，例如：

```text
帮我写一个数字时钟的 HTML 页面
```

### 4. 启用多 Agent 模式

```text
/setting agent_mode=true
```

再次发送需求时，系统会自动调度 planner、coder、reviewer、tester 协作完成。

---

## 命令列表

| 命令 | 说明 |
|------|------|
| `/model` | 配置或切换当前模型 |
| `/model add <id> <key> [provider]` | 快速添加模型 |
| `/model list` | 列出所有模型 |
| `/model select <id>` | 激活指定模型 |
| `/setting` | 查看所有设置项 |
| `/setting key=value` | 修改某个设置项 |
| `/file <path>` | 将文件加载到上下文 |
| `/diff` | 显示当前文件的 diff |
| `/run <command>` | 执行 shell 命令 |
| `/status` | 显示当前模型、项目路径等状态 |
| `/commit [message]` | 提交当前改动到 Git |
| `/clear` | 清空当前聊天记录 |
| `/help` | 显示所有命令 |
| `/exit` | 退出程序 |

### 设置项示例

```text
/setting agent_mode=true
/setting agent_fold_output=true
/setting think_fold=true
/setting debug_mode=true
```

---

## 界面说明

启动后界面主要包含：

- **顶部状态栏**：显示当前模型、项目名称、Agent 模式状态
- **中间聊天区域**：显示用户消息、AI 回复、系统提示、工具执行结果
- **底部输入框**：输入消息或命令

### 快捷键

| 快捷键 | 说明 |
|--------|------|
| `Enter` | 发送消息 |
| `Ctrl + C` | 退出程序 |
| `↑ / ↓` | 浏览历史输入 |
| `Tab` | 切换焦点 |

---

## 多 Agent 协作模式

当 `agent_mode=true` 时，用户请求会进入多 Agent 流水线：

```text
User Request
     │
     ▼
┌─────────┐
│ Planner │  ── 分析需求，制定实施计划
└────┬────┘
     │
     ▼
┌────────┐
│ Coder  │  ── 编写或修改源码文件
└────┬───┘
     │
     ▼
┌──────────┐
│ Reviewer │  ── 审查代码质量与问题
└────┬─────┘
     │
     ▼
┌────────┐
│ Tester │  ── 生成并运行测试
└────────┘
```

每个 Specialist 都有独立的系统提示和职责，最终由 Orchestrator 汇总结果返回给用户。

### Agent 输出折叠

通过 `agent_fold_output` 控制：

- `true`（默认）：每个 Agent 只显示 `OK/FAIL` 状态，错误才显示详情
- `false`：显示每个 Agent 的完整输出

### 思考过程折叠

通过 `think_fold` 控制：

- `true`（默认）：只显示 `Thinking...` 一行
- `false`：显示完整 thinking 内容

---

## 可用工具

LLM 在运行时可以调用以下工具：

| 工具 | 说明 |
|------|------|
| `read_file` | 读取文件内容，支持 `limit` 限制长度 |
| `write_file` | 写入或覆盖文件（写文件前可选确认弹窗） |
| `execute_command` | 执行 shell 命令 |
| `execute_code` | 在沙箱中执行 Python 代码片段 |
| `list_directory` | 列出目录内容 |
| `search_files` | 在文件中搜索文本 |
| `analyze_project` | 分析项目结构与类型 |
| `web_search` | 使用搜索引擎查询网络信息 |

---

## 配置说明

配置文件默认保存在：

```text
Windows: C:\Users\<用户名>\.config\hakimi\config.toml
macOS:   ~/.config/hakimi/config.toml
Linux:   ~/.config/hakimi/config.toml
```

### 常用设置项

| 设置项 | 说明 | 默认值 |
|--------|------|--------|
| `agent_mode` | 启用多 Agent 协作模式 | `false` |
| `agent_run_tests` | Agent 流水线是否自动运行测试 | `true` |
| `agent_fold_output` | 折叠 Agent 成功输出，仅显示错误 | `true` |
| `think_mode` | 是否显示 LLM 的 thinking 内容 | `true` |
| `think_fold` | 是否折叠 thinking 内容 | `true` |
| `think_lines` | thinking 折叠时显示的行数 | `2` |
| `stream` | 是否开启流式响应 | `true` |
| `temperature` | LLM 采样温度 | `0.7` |
| `max_tokens` | 单次回复最大 token 数 | `4096` |
| `max_tool_rounds` | 单轮对话最大工具调用次数 | `10` |
| `confirm_write_file` | 写文件前是否弹出确认框 | `true` |
| `confirm_command_execution` | 执行命令前是否确认 | `true` |
| `confirm_tool_execution` | 调用工具前是否确认 | `true` |
| `markdown_render` | 是否对消息进行 Markdown 渲染 | `true` |
| `show_tool_results` | 是否显示工具执行结果 | `true` |
| `tool_results_fold` | 是否折叠工具执行结果 | `true` |
| `auto_analyze` | 启动时是否自动分析项目 | `true` |
| `debug_mode` | 是否输出调试日志到项目根目录 | `false` |

---

## 项目结构

```text
hakimi-codex/
├── codex/
│   ├── __init__.py
│   ├── __main__.py              # CLI 入口
│   ├── app.py                   # Textual 应用入口
│   ├── core/                    # 核心逻辑
│   │   ├── agents/              # 多 Agent 系统
│   │   │   ├── __init__.py
│   │   │   ├── agent_runner.py
│   │   │   ├── models.py
│   │   │   ├── orchestrator.py
│   │   │   └── specialist_prompts.py
│   │   ├── tools/               # 工具实现
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── code.py
│   │   │   ├── filesystem.py
│   │   │   ├── project.py
│   │   │   ├── schemas.py
│   │   │   ├── shell.py
│   │   │   └── web.py
│   │   ├── chat_engine.py       # 聊天流程引擎
│   │   ├── config.py            # 配置管理
│   │   ├── diff_utils.py        # 代码 diff 工具
│   │   ├── llm_client.py        # LLM API 客户端
│   │   ├── models.py            # 数据模型
│   │   ├── prompts.py           # 系统提示词
│   │   ├── project_analyzer.py  # 项目分析器
│   │   └── tool_parser.py       # 工具调用解析器
│   ├── ui/                      # TUI 界面
│   │   ├── __init__.py
│   │   ├── screens/
│   │   │   ├── __init__.py
│   │   │   ├── confirmation_dialog.py
│   │   │   ├── main_screen.py
│   │   │   ├── model_edit_dialog.py
│   │   │   └── splash_screen.py
│   │   └── styles/
│   │       └── codex.tcss
│   ├── utils/                   # 通用工具
│   │   ├── __init__.py
│   │   ├── logger.py
│   │   └── markdown.py
│   └── legacy/                  # 旧版组件保留
├── install.bat
├── pyproject.toml
├── setup.py
└── README.md
```

---

## 支持的模型

理论上支持所有兼容 OpenAI Chat Completions API 的模型，已测试：

- DeepSeek（`deepseek-chat`、`deepseek-reasoner`、`deepseek-v4-pro` 等）
- OpenAI GPT 系列
- Kimi（Moonshot）K2.x 系列
- 其他自定义 OpenAI 兼容服务

Provider 自动识别规则：

| model_id 关键字 | Provider |
|----------------|----------|
| `deepseek` | deepseek |
| `kimi`, `moonshot` | kimi |
| `gpt`, `o1`, `o3` | openai |
| `claude` | anthropic |
| `gemini` | google |
| `mistral` | mistral |
| `llama`, `qwen` | ollama |

---

## 开发计划

- [x] 基础 TUI 界面
- [x] 多 Agent 协作流水线
- [x] 工具调用系统
- [x] 模型配置管理
- [x] 文件写入确认
- [x] Agent 输出折叠
- [x] thinking 内容折叠
- [ ] Git 自动提交增强
- [ ] 插件系统
- [ ] 更多编程语言 Specialist
- [ ] 本地模型支持

---

## 常见问题

### Q: Windows 下执行命令出现编码错误？

A: 已针对 Windows 做特殊处理，优先 UTF-8 解码，失败时回退到 GBK。如仍有问题请开启 `debug_mode` 并查看日志。

### Q: Agent 模式下文件没有创建？

A: 检查 `confirm_write_file` 设置。如果开启，写文件前会弹窗确认；确保对话框没有被遮挡。

### Q: 如何查看完整 thinking 内容？

A: 输入 `/setting think_fold=false`。

### Q: 如何关闭 Agent 成功输出的折叠？

A: 输入 `/setting agent_fold_output=false`。

### Q: 流式输出显示异常？

A: 部分场景下流式输出可能出现渲染问题，可临时关闭：

```text
/setting stream=false
```

---

## 贡献

欢迎提交 Issue 和 Pull Request。

```bash
# Fork 后克隆
git clone git@github.com:<your-name>/hakimi-codex.git

# 创建分支
git checkout -b feature/xxx

# 提交改动
git commit -m "feat: xxx"

# 推送到你的仓库
git push origin feature/xxx
```

---

## 许可证

[MIT](LICENSE)
