"""单个 Agent 的执行器."""

import json
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..llm_client import LLMClient
from ..models import AppConfig, ModelConfig
from ..tools import ToolExecutor, ToolResultStatus
from ..tool_parser import parse_tool_calls
from ..diff_utils import generate_unified_diff
from ...utils.logger import debug as log_debug
from ...utils.markdown import extract_thinking_tags
from .models import AgentRole, AgentTask, AgentResult
from .specialist_prompts import build_specialist_prompt


ConfirmCallback = Optional[Callable[..., Awaitable[bool]]]


class AgentRunner:
    """运行一个 Specialist Agent 完成指定任务."""

    def __init__(
        self,
        role: AgentRole,
        project_path: str,
        config: AppConfig,
        model: ModelConfig,
        confirm_callback: ConfirmCallback = None,
    ):
        self.role = role
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.model = model
        self.confirm_callback = confirm_callback
        self.llm_client: Optional[LLMClient] = None
        self.tool_executor = ToolExecutor(str(self.project_path))

    async def run(self, task: AgentTask) -> AgentResult:
        """执行 Specialist 任务，支持多轮工具调用."""
        self.llm_client = LLMClient(self.model, think_mode=self.config.ai.think_mode)
        try:
            system_prompt = build_specialist_prompt(self.role, self.project_path)
            messages: List[Dict[str, str]] = [
                {"role": "user", "content": task.instruction}
            ]

            max_rounds = max(1, min(10, self.config.ai.max_tool_rounds))
            all_executed: List[Dict[str, Any]] = []
            final_text = ""

            for _ in range(max_rounds):
                raw_response = ""
                async for chunk in self.llm_client.chat(
                    messages,
                    system_prompt=system_prompt,
                    stream=self.config.ai.stream,
                ):
                    raw_response += chunk

                thinking_content, full_response = extract_thinking_tags(raw_response)
                final_text = full_response.strip()

                tool_calls, errors = parse_tool_calls(full_response)
                if errors:
                    return AgentResult(
                        role=self.role,
                        success=False,
                        output=f"Tool parse errors: {errors[:3]}",
                        error="parse_error",
                    )

                if not tool_calls:
                    break

                # 记录本轮 assistant 的工具调用
                messages.append({"role": "assistant", "content": full_response})

                executed: List[Dict[str, Any]] = []
                for call in tool_calls:
                    tool_name = call.get("tool") or call.get("command")
                    # 优先从 parameters/args 获取，否则从 call 本身获取（排除 tool/command 键）
                    parameters = call.get("parameters") or call.get("args")
                    if not parameters:
                        parameters = {k: v for k, v in call.items() if k not in ("tool", "command")}

                    # 验证必需参数是否存在
                    required_params = {
                        "read_file": ["file_path"],
                        "write_file": ["file_path", "content"],
                        "execute_command": ["command"],
                        "execute_code": ["code"],
                        "search_files": ["pattern"],
                    }
                    if tool_name in required_params:
                        missing = [p for p in required_params[tool_name] if p not in parameters]
                        if missing:
                            executed.append({
                                "tool": tool_name,
                                "status": "error",
                                "output": f"缺少必需参数: {', '.join(missing)}。正确格式：{{\"tool\": \"{tool_name}\", \"parameters\": {{\"{missing[0]}\": \"值\"}}}}",
                            })
                            continue

                    # 写文件前确认（如果 UI 层传入了确认回调且配置允许）
                    if tool_name == "write_file" and self.confirm_callback:
                        file_path = parameters.get("file_path", "")
                        new_content = parameters.get("content", "")
                        need_confirm = (
                            self.config.ai.confirm_tool_execution
                            and self.config.ai.confirm_write_file
                        )
                        if need_confirm:
                            try:
                                log_debug(f"Agent {self.role.value} requesting confirmation for write_file: {file_path}")
                                read_result = self.tool_executor.read_file(file_path)
                                if read_result.status == ToolResultStatus.SUCCESS:
                                    content_to_show = generate_unified_diff(
                                        read_result.output, new_content, file_path
                                    )
                                    content_type = "diff"
                                else:
                                    content_to_show = new_content
                                    content_type = "text"
                                confirmed = await self.confirm_callback(
                                    title=f"Agent {self.role.value} 请求写入文件: {file_path}",
                                    content=content_to_show,
                                    content_type=content_type,
                                    confirm_label="确认写入",
                                )
                            except Exception as e:
                                log_debug(f"Confirmation dialog failed: {e}")
                                confirmed = False
                            if not confirmed:
                                executed.append({
                                    "tool": tool_name,
                                    "status": "cancelled",
                                    "output": f"用户已取消写入: {file_path}",
                                })
                                continue

                    result = self.tool_executor.execute_tool(tool_name, parameters)
                    executed.append({
                        "tool": tool_name,
                        "status": "success" if result.status == ToolResultStatus.SUCCESS else "error",
                        "output": result.output,
                    })

                all_executed.extend(executed)

                # 把工具执行结果反馈给模型，驱动下一轮
                tool_results_text = "\n".join(
                    f"[{r['status']}] {r['tool']}: {r['output'][:500]}"
                    for r in executed
                )
                messages.append({
                    "role": "user",
                    "content": f"Tool execution results:\n{tool_results_text}\n\nContinue if needed.",
                })

            success = all(r["status"] == "success" for r in all_executed)
            output_lines = [f"Agent {self.role.value} completed."]
            for r in all_executed:
                output_lines.append(f"- {r['tool']}: {r['status']}")
                if r["output"]:
                    output_lines.append(f"  {r['output'][:200]}")
            if not all_executed and final_text:
                output_lines.append(final_text)

            return AgentResult(
                role=self.role,
                success=success,
                output="\n".join(output_lines),
                tool_calls=all_executed,
                thinking=thinking_content if thinking_content else None,
            )

        except Exception as e:
            return AgentResult(
                role=self.role,
                success=False,
                output=f"Agent {self.role.value} failed: {str(e)}",
                error=str(e),
            )
        finally:
            await self.llm_client.close()
