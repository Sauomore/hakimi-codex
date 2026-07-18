# Hakimi Codex

一个专业、高效的多智能体编程助手，采用工具调用架构，能读写文件、执行命令，并与用户协作完成复杂的软件开发任务。

## 项目概述

Hakimi Codex 是一个 Python 项目，通过大语言模型 (LLM) 驱动的智能体，实现对项目代码的自动分析与修改。它支持严格的工具调用协议（JSON over Markdown code blocks），可执行 `read_file`、`write_file`、`list_directory`、`search_files`、`execute_command` 等操作，能够独立完成文件的创建、修改、搜索和命令运行。

## 主要特性

- **多工具集成**：支持读写文件、目录列表、文件搜索、命令执行等核心操作。
- **严格的工具调用格式**：所有工具调用均通过 `` ```tool `` Markdown 块传递，确保稳定可靠。
- **流式处理支持**：支持 LLM 流式响应，实时输出处理进度。
- **可配置的 LLM 后端**：通过 `src/config.py` 轻松切换不同的 API 端点、模型和认证信息。
- **输出格式化**：自动将 Agent 输出转换为清晰的终端文本或 JSON。
- **测试友好**：包含基础测试用例，方便扩展和验证。

## 项目结构

```
hakimi_codex/
├── main.py                   # 主入口：启动 Agent 交互循环
├── pyproject.toml            # 项目元数据与依赖管理
├── README.md                 # 项目说明
├── src/
│   ├── __init__.py
│   ├── agent.py              # 核心 Agent 类：协调工具调用与对话
│   ├── config.py             # 配置管理：API 密钥、模型、参数
│   ├── llm_client.py         # LLM 客户端：与模型 API 通信
│   ├── output_formatter.py   # 输出格式化：将响应转为可读文本
│   ├── stream_handler.py     # 流式处理：处理实时响应流
│   └── tools.py              # 工具实现：定义可用的工具及其调用逻辑
└── tests/
    ├── __init__.py
    └── test_basic.py         # 基础单元测试
```

## 安装与准备

### 环境要求

- Python 3.10+
- 一个已获得 API 密钥的大语言模型服务（如 OpenAI、DeepSeek 等）

### 安装步骤

1. 克隆仓库：

   ```bash
   git clone git@github.com:你的用户名/hakimi_codex.git
   cd hakimi_codex
   ```

2. （推荐）创建并激活虚拟环境：

   ```bash
   python -m venv venv
   source venv/bin/activate      # Linux/macOS
   venv\Scripts\activate         # Windows
   ```

3. 安装依赖：

   ```bash
   pip install -e .
   ```

   如果 `pyproject.toml` 中未列出具体依赖，请根据实际需要安装 `openai`、`requests` 等库。

4. 配置 API 密钥：

   复制 `.env.example` 为 `.env`（如果有），或直接在环境变量中设置：

   ```bash
   export API_KEY="你的密钥"
   export API_BASE_URL="https://api.openai.com/v1"
   export MODEL_NAME="gpt-4o-mini"
   ```

   也可以在 `src/config.py` 中修改默认值。

## 使用方法

### 直接运行

```bash
python main.py
```

程序将启动交互式会话，你可以直接输入开发任务，例如：

```
用户: 创建一个 hello.py 文件，输出 "Hello, World!"
```

Agent 会调用 `write_file` 工具，在项目目录下生成 `hello.py`。

### 编程调用

你也可以在自己的脚本中导入并使用 Agent：

```python
from src.agent import Agent

agent = Agent()
response = agent.run("列出当前目录下的所有文件")
print(response)
```

## 配置说明

所有配置项均在 `src/config.py` 中定义，支持以下环境变量：

| 环境变量         | 默认值                    | 说明                     |
|------------------|---------------------------|--------------------------|
| `API_KEY`        | (必填)                    | LLM API 密钥             |
| `API_BASE_URL`   | `https://api.openai.com`  | API 基础地址             |
| `MODEL_NAME`     | `gpt-4o-mini`             | 使用的模型名称           |
| `MAX_TOKENS`     | `4096`                    | 最大生成令牌数           |
| `TEMPERATURE`    | `0.0`                     | 生成温度                 |

## 工具说明

Agent 目前支持以下工具（定义在 `src/tools.py`）：

- `read_file(file_path)` – 读取指定文件内容。
- `write_file(file_path, content)` – 写入内容到文件（会覆盖已有文件）。
- `list_directory(dir_path)` – 列出目录中的文件和子目录。
- `search_files(pattern)` – 在当前项目中搜索匹配模式的文件。
- `execute_command(command)` – 在终端中执行命令。

> 注意：`execute_command` 操作会直接在你的系统上运行命令，请确保在安全可控的环境中使用。

## 运行测试

```bash
pytest tests/
```

## 贡献

欢迎提交 Issue 或 Pull Request！请遵循以下原则：

1. Fork 本仓库。
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)。
3. 提交更改 (`git commit -m 'Add some AmazingFeature'`)。
4. 推送到分支 (`git push origin feature/AmazingFeature`)。
5. 打开一个 Pull Request。

## 许可证

本项目采用 MIT 许可证。详见 [LICENSE](LICENSE) 文件。

## 致谢

- [OpenAI](https://openai.com) 提供强大的语言模型 API。
- 所有贡献者和使用者。
