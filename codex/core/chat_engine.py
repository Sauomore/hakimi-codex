"""聊天流程编排引擎（与 UI 无关）."""

import asyncio
import json
import re
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

from textual.worker import get_current_worker

from .config import add_model, get_active_model
from .llm_client import LLMClient
from .models import AppConfig, ModelConfig, ProviderType
from .prompts import build_system_prompt
from .tools import ToolExecutor, ToolResult, ToolResultStatus
from .tool_parser import parse_tool_calls
from .diff_utils import generate_unified_diff
from ..utils.logger import debug as log_debug


async def _default_confirm(**kwargs) -> bool:
    """默认确认回调：直接允许."""
    return True


class ChatCallbacks:
    """聊天引擎与 UI 层之间的回调集合."""

    def __init__(
        self,
        add_system_message: Callable[[str], None],
        add_ai_message: Callable[[str, Optional[str]], None],
        add_tool_result: Callable[[str, str], None],
        confirm_action: Callable[..., Any] = None,
        show_diff_preview: Callable[[str], None] = None,
    ):
        self.add_system_message = add_system_message
        self.add_ai_message = add_ai_message
        self.add_tool_result = add_tool_result
        self.confirm_action = confirm_action or _default_confirm
        self.show_diff_preview = show_diff_preview or (lambda diff: None)


class ChatEngine:
    """聊天引擎 - 处理消息、工具调用和 LLM 交互."""

    def __init__(self, project_path: str, config: AppConfig):
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor(str(self.project_path))
        self.messages: List[Dict[str, Any]] = []

    def set_model(self, model: ModelConfig) -> None:
        """设置当前模型并初始化客户端."""
        if self.llm_client:
            asyncio.create_task(self.llm_client.close())
        self.llm_client = LLMClient(model, think_mode=self.config.ai.think_mode)

    async def close(self) -> None:
        """关闭 LLM 客户端."""
        if self.llm_client:
            await self.llm_client.close()
            self.llm_client = None

    def add_user_message(self, content: str) -> None:
        """添加用户消息到历史."""
        self.messages.append({"role": "user", "content": content})

    def clear_history(self) -> None:
        """清空对话历史."""
        self.messages = []

    async def process_message(self, content: str, callbacks: ChatCallbacks) -> None:
        """处理一条用户消息."""
        active_model = get_active_model(self.config)
        if not active_model:
            callbacks.add_system_message("[bold yellow]No model selected.[/bold yellow] Use /model to configure.")
            return
        if not active_model.api_key:
            callbacks.add_system_message("[bold yellow]No API key configured.[/bold yellow] Use /model to edit.")
            return

        if not self.llm_client or self.llm_client.model.id != active_model.id:
            await self.close()
            self.llm_client = LLMClient(active_model, think_mode=self.config.ai.think_mode)

        self.add_user_message(content)

        try:
            max_rounds = max(1, min(50, self.config.ai.max_tool_rounds))
            for round_num in range(max_rounds):
                api_messages = [m for m in self.messages if m["role"] in ("user", "assistant")]
                system_prompt = build_system_prompt(self.project_path)
                full_response = ""
                thinking_content = ""

                callbacks.add_system_message("[#888888]Thinking...[/#888888]")

                worker = get_current_worker()
                async for chunk in self.llm_client.chat(
                    api_messages,
                    system_prompt=system_prompt,
                    stream=self.config.ai.stream
                ):
                    if worker.is_cancelled:
                        break
                    full_response += chunk

                if worker.is_cancelled:
                    break

                thinking_content = self._extract_thinking(full_response)
                full_response = self._strip_thinking_tags(full_response)

                tool_results = await self._execute_tool_calls(full_response, callbacks)

                if not tool_results:
                    text_only = re.sub(r'```(?:tool|json)\s*\n.*?\n```', '', full_response, flags=re.DOTALL).strip()
                    if self._is_transitional_response(text_only) and round_num < max_rounds - 1:
                        self.messages.append({"role": "assistant", "content": full_response})
                        callbacks.add_system_message(f"[#888888]> {text_only}[/#888888]")
                        self.messages.append({
                            "role": "user",
                            "content": (
                                "You said you would check or confirm something, but no tool call was found in your response. "
                                "If you need data to answer, call a tool immediately using a ```tool block with strict JSON. "
                                "If you already have enough data, provide the final answer directly without transitional phrases."
                            )
                        })
                        continue

                    if self.llm_client and self.llm_client.last_finish_reason == "length":
                        callbacks.add_system_message(
                            "[bold yellow]Response truncated by max_tokens. "
                            "Increase the model's max_tokens in ~/.config/hakimi/config.toml "
                            "or ask for a shorter file.[/bold yellow]"
                        )

                    callbacks.add_ai_message(full_response, thinking_content if thinking_content else None)
                    break
                else:
                    self.messages.append({"role": "assistant", "content": full_response})
                    text_only = re.sub(r'```(?:tool|json)\s*\n.*?\n```', '', full_response, flags=re.DOTALL).strip()
                    if text_only:
                        callbacks.add_system_message(f"[#888888]> {text_only}[/#888888]")
                    for tr in tool_results:
                        self.messages.append({
                            "role": "user",
                            "content": f"[Tool '{tr['tool_name']}' result]\n```\n{tr['output']}\n```"
                        })

            if round_num >= max_rounds - 1:
                callbacks.add_system_message(f"[bold yellow]Max tool rounds reached ({max_rounds}). Stopping.[/bold yellow]")

        except Exception as e:
            callbacks.add_system_message(f"[bold red]Error: {str(e)}[/bold red]")

    def _extract_thinking(self, content: str) -> str:
        """提取 thinking 标签内容."""
        thinking = ""
        pattern = re.compile(r'<thinking>(.*?)</thinking>', re.DOTALL)
        for match in pattern.finditer(content):
            thinking += match.group(1)
        return thinking

    def _strip_thinking_tags(self, content: str) -> str:
        """移除 thinking 标签."""
        return re.sub(r'<thinking>.*?</thinking>', '', content, flags=re.DOTALL)

    def _is_transitional_response(self, text: str) -> bool:
        """判断是否为过渡性回复（需要继续追问）."""
        if not text or len(text) < 10:
            return False

        text_lower = text.lower()

        transitional_keywords = [
            "让我看看", "让我确认", "让我检查", "让我确认一下", "让我检查下",
            "我来确认", "我来检查", "我来确认一下", "我来检查下",
            "需要确认", "需要确认一下", "需要检查", "需要检查下",
            "确认一下", "检查下", "检查", "确认",
            "让我先", "我先",
            "现在让我", "现在我来", "现在我",
            "先确认", "先检查", "先查看",
            "了解一下", "看一下",
            "let me check", "let me confirm", "let me verify",
            "let me take a look", "let me see", "let me review",
            "i will check", "i will confirm", "i will verify",
            "i need to check", "i need to confirm", "i need to verify",
            "need to check", "need to confirm", "need to verify",
            "checking", "confirming", "verifying",
            "taking a look", "taking a look at",
            "reviewing", "looking at",
            "hold on", "one moment", "just a moment",
            "wait a moment", "give me a moment",
            "looking into", "going to check", "going to confirm",
            "let me review", "i will review", "need to review",
        ]

        has_transitional = any(kw in text_lower for kw in transitional_keywords)
        if not has_transitional:
            return False

        if len(text) < 150:
            return True

        if len(text) <= 300:
            analysis_keywords = [
                "分析", "总结", "结论", "建议", "方案", "实现",
                "修改", "优化", "问题", "原因", "方法", "步骤", "结果",
                "analysis", "summary", "conclusion", "recommendation",
                "solution", "implementation", "issue", "cause", "result",
            ]
            has_analysis = any(kw in text_lower for kw in analysis_keywords)
            has_code_blocks = "```" in text or "diff" in text_lower

            if has_analysis or has_code_blocks:
                return False
            return True

        return False

    async def _execute_tool_calls(
        self,
        content: str,
        callbacks: ChatCallbacks
    ) -> List[Dict[str, str]]:
        """解析并执行内容中的工具调用."""
        tool_calls, errors = parse_tool_calls(content)
        log_debug(f"_execute_tool_calls: parsed {len(tool_calls)} tool calls, {len(errors)} errors")

        if errors:
            for err in errors[:3]:
                log_debug(f"tool parse error: {err[:500]}")
                callbacks.add_system_message(f"[bold red]Tool parse error: {err[:200]}[/bold red]")

        if not tool_calls:
            return []

        results = []
        for tool_call in tool_calls:
            tool_name = tool_call.get("tool")
            parameters = tool_call.get("parameters", {})

            log_debug(f"executing tool: {tool_name} with params: {parameters}")
            callbacks.add_tool_result(
                f"tool: {tool_name}",
                f"parameters: {json.dumps(parameters, indent=2, ensure_ascii=False)}"
            )

            if tool_name == "execute_command" and self.config.ai.confirm_tool_execution and self.config.ai.confirm_command_execution:
                command = parameters.get("command", "")
                log_debug(f"confirming execute_command: {command}")
                confirmed = await callbacks.confirm_action(
                    title="确认执行终端命令",
                    content=f"$ {command}",
                    content_type="text",
                    confirm_label="确认执行",
                )
                if not confirmed:
                    self._append_cancelled_result(results, tool_name, "用户已取消执行该命令")
                    continue

            if tool_name == "write_file":
                confirmed = await self._confirm_write_file(parameters, callbacks)
                log_debug(f"write_file confirmed: {confirmed}")
                if not confirmed:
                    self._append_cancelled_result(results, tool_name, f"用户已取消写入文件: {parameters.get('file_path', '')}")
                    continue

            result = self.tool_executor.execute_tool(tool_name, parameters)
            log_debug(f"tool result: {result.status.value} - {result.output[:200]}")
            callbacks.add_tool_result(f"result: {tool_name}", result.output)

            results.append({
                "tool_name": tool_name,
                "output": result.output,
                "status": "success" if result.status == ToolResultStatus.SUCCESS else "error"
            })

        return results

    async def _confirm_write_file(self, parameters: Dict[str, Any], callbacks: ChatCallbacks) -> bool:
        """写入文件前的确认逻辑."""
        file_path = parameters.get("file_path", "")
        new_content = parameters.get("content", "")

        read_result = self.tool_executor.read_file(file_path)
        file_exists = read_result.status == ToolResultStatus.SUCCESS
        old_content = read_result.output if file_exists else ""

        need_confirm = (
            self.config.ai.confirm_tool_execution
            and self.config.ai.confirm_write_file
        )

        if file_exists and old_content == new_content:
            # 内容无变化，跳过写入和确认
            return True

        if file_exists and old_content != new_content:
            diff = generate_unified_diff(old_content, new_content, file_path)
            if need_confirm:
                log_debug(f"confirming write_file (modify): {file_path}")
                return await callbacks.confirm_action(
                    title=f"确认修改文件: {file_path}",
                    content=diff,
                    content_type="diff",
                    confirm_label="确认写入",
                )
            else:
                callbacks.show_diff_preview(diff)
                return True

        if not file_exists and need_confirm:
            log_debug(f"confirming write_file (create): {file_path}")
            return await callbacks.confirm_action(
                title=f"确认创建新文件: {file_path}",
                content=new_content,
                content_type="text",
                confirm_label="确认创建",
            )

        return True

    def _append_cancelled_result(self, results: List[Dict[str, str]], tool_name: str, message: str) -> None:
        """添加已取消的工具结果."""
        results.append({
            "tool_name": tool_name,
            "output": message,
            "status": "error"
        })
