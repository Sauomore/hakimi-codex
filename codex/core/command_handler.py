"""指令处理器 - 处理 / 开头的命令."""

import re
from typing import Dict, Callable, Optional, List, Tuple
from dataclasses import dataclass


@dataclass
class CommandResult:
    """指令处理结果."""
    success: bool
    message: str
    action: Optional[str] = None  # 内部动作标识
    data: Optional[dict] = None


class CommandHandler:
    """指令处理器."""
    
    # 命令定义: (描述, 参数说明, 示例)
    COMMANDS: Dict[str, Tuple[str, str, str]] = {
        "/help": ("显示所有可用命令", "", "/help"),
        "/setting": ("打开设置面板", "[key=value]", "/setting stream=false\n/setting temperature=0.5"),
        "/model": ("模型管理", "[list|add|edit|delete|select]", "/model list\n/model select gpt-4o"),
        "/file": ("添加文件到上下文", "<path>", "/file src/main.py"),
        "/diff": ("显示当前文件的 diff", "[file]", "/diff\n/diff src/main.py"),
        "/clear": ("清空对话历史", "", "/clear"),
        "/copy": ("复制消息到剪贴板或导出文件", "[last|<id>|all|view|file]", "/copy last\n/copy all\n/copy abc123\n/copy view\n/copy file"),
        "/export": ("导出聊天记录到文件", "[json|text] [path]", "/export\n/export text\n/export json ./backup/chat.jsonl"),
        "/import": ("从 JSONL 文件导入聊天记录", "<path> [--merge]", "/import ./backup/chat.jsonl\n/import ./backup/chat.jsonl --merge"),
        "/history": ("显示聊天记录列表", "", "/history"),
        "/undo": ("撤销最后一次 AI 修改", "", "/undo"),
        "/commit": ("提交当前更改到 Git", "[message]", "/commit\n/commit 'fix: bug'"),
        "/status": ("显示 Git 状态和项目信息", "", "/status"),
        "/run": ("执行 Shell 命令", "<command>", "/run python -m pytest"),
        "/agent": ("多 Agent 协作模式控制", "[on|off|status|test on|off|model <role> <id>]", "/agent on"),
        "/about": ("显示 Hakimi CLI 详细信息", "", "/about"),
        "/exit": ("退出应用", "", "/exit"),
    }
    
    # 设置项定义
    SETTING_KEYS: Dict[str, Tuple[str, type, str]] = {
        "stream": ("流式输出开关", bool, "true/false"),
        "think_mode": ("思考模式开关", bool, "true/false"),
        "think_fold": ("思考内容折叠开关", bool, "true/false"),
        "think_lines": ("折叠时显示行数", int, "1-10"),
        "temperature": ("AI 温度", float, "0.0-2.0"),
        "font_size": ("字体大小", int, "8-24"),
        "theme": ("界面主题", str, "dark/light"),
        "show_tool_results": ("显示工具执行结果", bool, "true/false"),
        "tool_results_fold": ("工具结果默认折叠", bool, "true/false"),
        "auto_analyze": ("启动时自动分析项目", bool, "true/false"),
        "markdown_render": ("AI 消息 Markdown 渲染", bool, "true/false"),
        "confirm_tool_execution": ("启用 AI 工具执行确认机制", bool, "true/false"),
        "confirm_command_execution": ("执行终端命令前确认", bool, "true/false"),
        "confirm_write_file": ("写入文件前显示 diff 并确认", bool, "true/false"),
        "max_tool_rounds": ("最大工具调用轮数", int, "1-50"),
        "max_context_messages": ("保留的最大对话轮数", int, "2-200"),
        "context_ttl_hours": ("上下文时间窗（小时）", float, ">0 or empty"),
        "save_chat_history": ("是否本地保存聊天记录", bool, "true/false"),
        "debug_mode": ("启用调试模式并在项目根目录输出日志", bool, "true/false"),
        "agent_mode": ("启用多 Agent 协作模式", bool, "true/false"),
        "agent_run_tests": ("Agent 流水线是否自动运行测试", bool, "true/false"),
        "planner_model": ("Planner Agent 使用的模型 ID", str, "model_id or empty"),
        "coder_model": ("Coder Agent 使用的模型 ID", str, "model_id or empty"),
        "reviewer_model": ("Reviewer Agent 使用的模型 ID", str, "model_id or empty"),
        "tester_model": ("Tester Agent 使用的模型 ID", str, "model_id or empty"),
    }
    
    def __init__(self):
        self._handlers: Dict[str, Callable] = {}
        self._callbacks: Dict[str, Callable] = {}
    
    def register(self, command: str, handler: Callable) -> None:
        """注册命令处理器."""
        self._handlers[command] = handler
    
    def register_callback(self, action: str, callback: Callable) -> None:
        """注册动作回调."""
        self._callbacks[action] = callback
    
    def parse(self, text: str) -> Tuple[bool, Optional[str], Optional[str]]:
        """解析输入，判断是否是命令.
        
        Returns: (is_command, command_name, args)
        """
        text = text.strip()
        if not text.startswith("/"):
            return False, None, text
        
        parts = text.split(None, 1)
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""
        
        return True, cmd, args
    
    def handle(self, text: str) -> CommandResult:
        """处理指令."""
        is_cmd, cmd, args = self.parse(text)
        
        if not is_cmd:
            # 不是命令，直接返回
            return CommandResult(True, "", action="chat", data={"message": text})
        
        if cmd == "/help":
            return self._handle_help(args)
        
        elif cmd == "/setting":
            return self._handle_setting(args)
        
        elif cmd == "/model":
            return self._handle_model(args)
        
        elif cmd == "/file":
            return CommandResult(True, f"已添加文件到上下文: {args}", action="add_file", data={"path": args})
        
        elif cmd == "/diff":
            return CommandResult(True, f"显示 diff: {args or '当前文件'}", action="show_diff", data={"file": args})
        
        elif cmd == "/clear":
            return CommandResult(True, "对话历史已清空", action="clear_chat")

        elif cmd == "/copy":
            target = args.strip() or "last"
            return CommandResult(True, f"复制: {target}", action="copy_message", data={"target": target})

        elif cmd == "/export":
            parts = args.strip().split(maxsplit=1)
            fmt = parts[0].lower() if parts else "text"
            if fmt not in ("json", "jsonl", "text"):
                fmt = "text"
                path = args.strip() or ""
            else:
                path = parts[1] if len(parts) > 1 else ""
            if fmt == "json":
                fmt = "jsonl"
            return CommandResult(True, f"导出: {fmt} {path or 'default'}", action="export_history", data={"format": fmt, "path": path})

        elif cmd == "/import":
            parts = args.strip().split()
            if not parts:
                return CommandResult(False, "用法: /import <path> [--merge]")
            path = parts[0]
            merge = "--merge" in parts[1:]
            return CommandResult(True, f"导入: {path}", action="import_history", data={"path": path, "merge": merge})

        elif cmd == "/history":
            return CommandResult(True, "", action="show_history")

        elif cmd == "/undo":
            return CommandResult(True, "已撤销最后一次修改", action="undo")
        
        elif cmd == "/commit":
            return CommandResult(True, f"提交: {args or '默认提交信息'}", action="git_commit", data={"message": args})
        
        elif cmd == "/status":
            return CommandResult(True, "显示项目状态", action="show_status")
        
        elif cmd == "/run":
            return CommandResult(True, f"执行: {args}", action="run_command", data={"command": args})
        
        elif cmd == "/agent":
            return self._handle_agent(args)
        
        elif cmd == "/about":
            return CommandResult(True, "", action="show_about")
        
        elif cmd == "/exit":
            return CommandResult(True, "退出", action="exit")
        
        elif cmd in self._handlers:
            # 自定义处理器
            return self._handlers[cmd](args)
        
        else:
            return CommandResult(False, f"未知命令: {cmd}\n输入 /help 查看所有命令")
    
    def _handle_help(self, args: str) -> CommandResult:
        """处理 /help 命令."""
        sections = {
            "聊天与会话": ["/help", "/clear", "/history", "/copy", "/export", "/import", "/undo"],
            "模型与配置": ["/model", "/setting", "/agent"],
            "上下文与工具": ["/file", "/diff", "/run"],
            "Git 与项目": ["/commit", "/status"],
            "系统": ["/about", "/exit"],
        }

        cmd_width = max(len(cmd) for cmd in self.COMMANDS)
        lines = [
            "",
            "[bold #58a6ff]╭──────────────────────────────────────────────────╮[/bold #58a6ff]",
            "[bold #58a6ff]│         Hakimi Codex 命令列表                    │[/bold #58a6ff]",
            "[bold #58a6ff]╰──────────────────────────────────────────────────╯[/bold #58a6ff]",
            "",
        ]

        for section_name, cmds in sections.items():
            lines.append(f"[bold #f0883e]▸ {section_name}[/bold #f0883e]")
            for cmd in cmds:
                if cmd not in self.COMMANDS:
                    continue
                desc, param, example = self.COMMANDS[cmd]
                param_text = f"[italic #8b949e] {self._escape_markup(param)}[/italic #8b949e]  " if param else "  "
                lines.append(f"  [bold #58a6ff]{cmd:<{cmd_width}}[/bold #58a6ff]{param_text}{desc}")
                if example:
                    for ex_line in example.split("\n"):
                        lines.append(f"  {' ' * cmd_width}   [bold #3fb950]↳[/bold #3fb950] {self._escape_markup(ex_line)}")
            lines.append("")

        lines.extend([
            "[bold #f0883e]▸ 设置项 (/setting key=value)[/bold #f0883e]",
            f"  {'名称':<22}{'类型':<10}{'说明':<30}{'可取值'}",
            f"  {'─' * 22}{'─' * 10}{'─' * 30}{'─' * 15}",
        ])

        for key, (desc, type_, hint) in self.SETTING_KEYS.items():
            lines.append(
                f"  [bold #58a6ff]{key:<20}[/bold #58a6ff] "
                f"{type_.__name__:<10} "
                f"{desc:<30} "
                f"[italic #8b949e]{self._escape_markup(hint)}[/italic #8b949e]"
            )

        lines.extend(["", "[italic #6e7681]提示: 命令参数中 [[ ]] 表示可选项，< > 表示必填项。[/italic #6e7681]", ""])
        return CommandResult(True, "\n".join(lines))

    @staticmethod
    def _escape_markup(text: str) -> str:
        """转义 Rich markup 中的方括号."""
        return text.replace("[", "[[").replace("]", "]]")
    
    def _handle_agent(self, args: str) -> CommandResult:
        """处理 /agent 命令."""
        parts = args.strip().split(maxsplit=2)
        if not parts or parts[0].lower() in ("status", ""):
            return CommandResult(True, "", action="get_setting", data={"key": "agent_mode"})

        sub = parts[0].lower()
        if sub in ("on", "true", "1", "yes"):
            return CommandResult(True, "", action="set_setting", data={"key": "agent_mode", "value": True})
        if sub in ("off", "false", "0", "no"):
            return CommandResult(True, "", action="set_setting", data={"key": "agent_mode", "value": False})

        if sub == "model":
            if len(parts) < 3:
                return CommandResult(
                    False,
                    "用法: /agent model <role> <model_id>\n"
                    "roles: planner, coder, reviewer, tester\n"
                    "example: /agent model coder deepseek-v4-pro"
                )
            role = parts[1].lower()
            model_id = parts[2].strip()
            valid_roles = {"planner", "coder", "reviewer", "tester"}
            if role not in valid_roles:
                return CommandResult(False, f"未知角色: {role}. 可用: planner, coder, reviewer, tester")
            return CommandResult(
                True,
                "",
                action="set_setting",
                data={"key": f"{role}_model", "value": model_id}
            )

        if sub == "test":
            if len(parts) < 2:
                return CommandResult(False, "用法: /agent test [on|off]")
            on_off = parts[1].lower()
            value = on_off in ("on", "true", "1", "yes")
            return CommandResult(True, "", action="set_setting", data={"key": "agent_run_tests", "value": value})

        return CommandResult(
            False,
            "用法: /agent [on|off|status|test on|off|model <role> <model_id>]"
        )

    def _handle_setting(self, args: str) -> CommandResult:
        """处理 /setting 命令."""
        if not args.strip():
            # 显示当前设置
            return CommandResult(True, "", action="show_settings")
        
        # 解析 key=value
        match = re.match(r"(\w+)\s*=\s*(.+)", args.strip())
        if not match:
            # 尝试只显示某个设置
            key = args.strip()
            if key in self.SETTING_KEYS:
                return CommandResult(True, "", action="get_setting", data={"key": key})
            return CommandResult(False, "格式错误。使用: /setting key=value\n输入 /help 查看设置项")
        
        key, value = match.groups()
        key = key.strip()
        value = value.strip()
        
        if key not in self.SETTING_KEYS:
            return CommandResult(False, f"未知设置项: {key}\n输入 /help 查看可用设置项")
        
        desc, type_, hint = self.SETTING_KEYS[key]
        
        # 类型转换
        try:
            if type_ is bool:
                parsed_value = value.lower() in ("true", "1", "yes", "on")
            elif type_ is int:
                parsed_value = int(value)
            elif type_ is float:
                parsed_value = float(value)
            else:
                parsed_value = value
        except ValueError:
            return CommandResult(False, f"值类型错误: {key} 需要 {type_.__name__} 类型 [{hint}]")
        
        return CommandResult(
            True,
            f"设置已更新: {key} = {parsed_value}",
            action="set_setting",
            data={"key": key, "value": parsed_value}
        )
    
    def _handle_model(self, args: str) -> CommandResult:
        """处理 /model 命令."""
        parts = args.strip().split(None, 1)
        subcmd = parts[0].lower() if parts else "list"
        subargs = parts[1] if len(parts) > 1 else ""
        
        if subcmd == "list":
            return CommandResult(True, "", action="model_list")
        elif subcmd == "select":
            return CommandResult(True, f"选择模型: {subargs}", action="model_select", data={"id": subargs})
        elif subcmd == "add":
            # 解析模型参数
            # 格式1: /model add <model_id> <api_key> [provider]
            # 格式2: /model add name=xxx model_id=xxx api_key=xxx provider=xxx
            return self._parse_model_add(subargs)
        elif subcmd == "delete":
            return CommandResult(True, f"删除模型: {subargs}", action="model_delete", data={"id": subargs})
        else:
            return CommandResult(False, f"未知子命令: {subcmd}\n可用: list, select, add, delete")
    
    def _parse_model_add(self, args: str) -> CommandResult:
        """解析模型添加参数."""
        if not args:
            return CommandResult(False, 
                "用法: /model add <model_id> <api_key> [provider]\n"
                "或: /model add name=xxx model_id=xxx api_key=xxx provider=xxx\n\n"
                "提供商: openai, anthropic, deepseek, kimi, google, mistral, ollama, openrouter, custom\n"
                "示例: /model add deepseek-v3 sk-xxx deepseek\n"
                "       /model add gpt-4o sk-xxx openai\n"
                "       /model add name=\"DeepSeek\" model_id=deepseek-v3 api_key=sk-xxx provider=deepseek")
        
        # 检查是否是键值对格式
        if "=" in args:
            # 键值对格式: name=xxx model_id=xxx api_key=xxx provider=xxx
            params = {}
            # 匹配 key=value 或 key="value with spaces"
            pattern = r'(\w+)=("(?:[^"\\]|\\.)*"|\S+)'
            for match in re.finditer(pattern, args):
                key = match.group(1)
                value = match.group(2)
                # 去除引号
                if value.startswith('"') and value.endswith('"'):
                    value = value[1:-1]
                params[key] = value
            
            if "model_id" not in params or "api_key" not in params:
                return CommandResult(False, "必须提供 model_id 和 api_key")
            
            return CommandResult(
                True, "",
                action="model_add",
                data=params
            )
        
        # 简写格式: /model add <model_id> <api_key> [provider]
        tokens = args.split()
        if len(tokens) < 2:
            return CommandResult(False, 
                "用法: /model add <model_id> <api_key> [provider]\n"
                "示例: /model add deepseek-v3 sk-xxx deepseek")
        
        model_id = tokens[0]
        api_key = tokens[1]
        provider = tokens[2] if len(tokens) > 2 else self._infer_provider(model_id)
        
        return CommandResult(
            True, "",
            action="model_add",
            data={
                "model_id": model_id,
                "api_key": api_key,
                "provider": provider,
            }
        )
    
    def _infer_provider(self, model_id: str) -> str:
        """从模型ID推断提供商."""
        model_id_lower = model_id.lower()
        if "deepseek" in model_id_lower:
            return "deepseek"
        elif "kimi" in model_id_lower or "moonshot" in model_id_lower:
            return "kimi"
        elif "gpt" in model_id_lower or "o1" in model_id_lower or "o3" in model_id_lower:
            return "openai"
        elif "claude" in model_id_lower:
            return "anthropic"
        elif "gemini" in model_id_lower:
            return "google"
        elif "mistral" in model_id_lower:
            return "mistral"
        elif "llama" in model_id_lower or "qwen" in model_id_lower:
            return "ollama"
        else:
            return "custom"
    
    def get_completions(self, partial: str) -> List[str]:
        """获取命令补全列表."""
        if not partial.startswith("/"):
            return []
        
        return [cmd for cmd in self.COMMANDS.keys() if cmd.startswith(partial.lower())]
    
    def get_setting_completions(self, partial: str) -> List[str]:
        """获取设置项补全."""
        return [key for key in self.SETTING_KEYS.keys() if key.startswith(partial.lower())]
