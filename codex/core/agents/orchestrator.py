"""Orchestrator Agent - 调度 Specialist 流水线."""

import json
import re
import time
from pathlib import Path
from typing import Any, Awaitable, Callable, Dict, List, Optional

from ..llm_client import LLMClient
from ..models import AppConfig, ModelConfig
from ...utils.markdown import extract_thinking_tags
from .agent_runner import AgentRunner
from .models import AgentRole, AgentResult, AgentTask


ProgressCallback = Callable[[str], None]
StatusCallback = Callable[[Dict[str, str]], None]
ConfirmCallback = Optional[Callable[..., Awaitable[bool]]]
PlanReviewCallback = Optional[Callable[[str], Awaitable[Optional[str]]]]


class Orchestrator:
    """Orchestrator 负责理解用户意图并调度多个 Specialist 组成流水线."""

    def __init__(
        self,
        project_path: str,
        config: AppConfig,
        model: ModelConfig,
        progress_callback: ProgressCallback = None,
        status_callback: StatusCallback = None,
        confirm_callback: ConfirmCallback = None,
        plan_review_callback: PlanReviewCallback = None,
    ):
        self.project_path = Path(project_path).resolve()
        self.config = config
        self.default_model = model
        self.progress_callback = progress_callback or (lambda _: None)
        self.status_callback = status_callback or (lambda _: None)
        self.confirm_callback = confirm_callback
        self.plan_review_callback = plan_review_callback

    def _build_system_prompt(self) -> str:
        return f"""You are the Orchestrator agent in Hakimi Codex.

Project: {self.project_path.name}
Path: {self.project_path}

Your job is to decide whether the user's request requires a code-writing specialist pipeline.

Rules:
1. If the request requires creating, modifying, or refactoring code files, output ONLY a JSON object:
   {{"needs_coder": true}}
2. If the request does not require code changes, answer the user directly in Chinese.
3. The JSON must be valid and contain no Markdown code blocks.
"""

    def _get_model_for_role(self, role: AgentRole) -> ModelConfig:
        """根据角色获取对应模型配置，未配置则使用主模型."""
        model_id: Optional[str] = None
        if role == AgentRole.PLANNER:
            model_id = self.config.ai.planner_model
        elif role == AgentRole.CODER:
            model_id = self.config.ai.coder_model
        elif role == AgentRole.REVIEWER:
            model_id = self.config.ai.reviewer_model
        elif role == AgentRole.TESTER:
            model_id = self.config.ai.tester_model

        if model_id:
            for m in self.config.models:
                if m.id == model_id and m.enabled:
                    return m
        return self.default_model

    async def process(self, user_input: str) -> str:
        """处理用户输入并返回最终回复."""
        self.status_callback({
            "agent": "Orchestrator",
            "model": self.default_model.name,
            "state": "deciding",
        })
        llm_client = LLMClient(self.default_model, think_mode=self.config.ai.think_mode)
        try:
            system_prompt = self._build_system_prompt()
            messages = [{"role": "user", "content": user_input}]

            full_response = ""
            async for chunk in llm_client.chat(
                messages,
                system_prompt=system_prompt,
                stream=self.config.ai.stream,
            ):
                full_response += chunk

            thinking_content, stripped_response = extract_thinking_tags(full_response)
            decision = self._parse_decision(stripped_response)
            if not decision.get("needs_coder"):
                self.status_callback({"agent": "-", "model": "-", "state": "idle"})
                return stripped_response.strip()

            return await self._run_pipeline(user_input)

        except Exception as e:
            self.status_callback({"agent": "-", "model": "-", "state": "error"})
            return f"[Orchestrator error] {str(e)}"
        finally:
            await llm_client.close()

    async def _run_pipeline(self, user_input: str) -> str:
        """运行 Plan -> Code -> Review -> Test 流水线."""
        results: List[AgentResult] = []

        # Planner
        planner_model = self._get_model_for_role(AgentRole.PLANNER)
        self._report_status("Planner", planner_model.name, "running")
        self.progress_callback("Agent Planner: analyzing request...")
        plan_result = await self._run_agent(
            AgentRole.PLANNER,
            f"Analyze the following request and provide a concise implementation plan.\n\nRequest: {user_input}",
            planner_model,
        )
        results.append(plan_result)
        if not plan_result.success:
            self.status_callback({"agent": "-", "model": "-", "state": "idle"})
            return self._format_pipeline_results(results, user_input)
        plan = plan_result.output

        # 用户确认 / 修改计划
        if self.plan_review_callback:
            self.progress_callback(
                f"Agent Planner: plan ready ({plan_result.duration or 0:.1f}s), waiting for approval..."
            )
            reviewed_plan = await self.plan_review_callback(plan)
            if reviewed_plan is None:
                self.status_callback({"agent": "-", "model": "-", "state": "idle"})
                return "Agent 流水线已取消（计划未通过审核）。"
            plan = reviewed_plan

        # Coder
        coder_model = self._get_model_for_role(AgentRole.CODER)
        self._report_status("Coder", coder_model.name, "running")
        self.progress_callback("Agent Coder: implementing...")
        coder_result = await self._run_agent(
            AgentRole.CODER,
            f"You MUST implement the request by writing the necessary files. "
            f"For simple tasks, use write_file directly WITHOUT listing the directory first.\n\n"
            f"Request: {user_input}\n\nPlan: {plan}",
            coder_model,
        )
        results.append(coder_result)
        if not coder_result.success:
            self.status_callback({"agent": "-", "model": "-", "state": "idle"})
            return self._format_pipeline_results(results, user_input)
        code_output = coder_result.output
        self.progress_callback(
            f"Agent Coder: completed in {coder_result.duration or 0:.1f}s"
        )

        # 检查 coder 是否实际生成了源码文件（支持多种文件类型）
        source_extensions = {".py", ".html", ".htm", ".js", ".ts", ".css", ".java", ".cpp", ".c", ".go", ".rs", ".rb", ".php", ".swift", ".kt", ".scala"}
        source_files = [
            f for f in self.project_path.iterdir()
            if f.is_file() and f.suffix.lower() in source_extensions and not f.name.startswith("test_")
        ]
        if not source_files:
            coder_result = AgentResult(
                role=AgentRole.CODER,
                success=False,
                output="Coder reported success but no source files were created.",
                error="no_source_files",
            )
            results[-1] = coder_result
            self.status_callback({"agent": "-", "model": "-", "state": "idle"})
            return self._format_pipeline_results(results, user_input)

        # Reviewer
        reviewer_model = self._get_model_for_role(AgentRole.REVIEWER)
        self._report_status("Reviewer", reviewer_model.name, "running")
        self.progress_callback("Agent Reviewer: reviewing...")
        reviewer_prompt = (
            f"Review the following implementation for the request.\n\n"
            f"Request: {user_input}\n\nPlan: {plan}\n\n"
            f"Implementation output: {code_output}"
        )
        if source_files:
            reviewer_prompt += f"\n\nSource files: {', '.join(f.name for f in source_files)}"
        reviewer_result = await self._run_agent(
            AgentRole.REVIEWER,
            reviewer_prompt,
            reviewer_model,
        )
        results.append(reviewer_result)
        self.progress_callback(
            f"Agent Reviewer: {'completed' if reviewer_result.success else 'failed'} in {reviewer_result.duration or 0:.1f}s"
        )

        # Tester
        if self.config.ai.agent_run_tests:
            tester_model = self._get_model_for_role(AgentRole.TESTER)
            self._report_status("Tester", tester_model.name, "running")
            self.progress_callback("Agent Tester: generating and running tests...")
            tester_prompt = (
                f"Generate and run tests for the following implementation.\n\n"
                f"Request: {user_input}\n\nImplementation output: {code_output}"
            )
            if source_files:
                tester_prompt += f"\n\nSource files: {', '.join(f.name for f in source_files)}"
            tester_result = await self._run_agent(
                AgentRole.TESTER,
                tester_prompt,
                tester_model,
            )
            results.append(tester_result)
            self.progress_callback(
                f"Agent Tester: {'completed' if tester_result.success else 'failed'} in {tester_result.duration or 0:.1f}s"
            )

        self.status_callback({"agent": "-", "model": "-", "state": "idle"})
        return self._format_pipeline_results(results, user_input)

    def _report_status(self, agent: str, model: str, state: str) -> None:
        """上报当前运行状态."""
        self.status_callback({"agent": agent, "model": model, "state": state})

    async def _run_agent(
        self, role: AgentRole, instruction: str, model: Optional[ModelConfig] = None
    ) -> AgentResult:
        """运行单个 Specialist，并记录耗时."""
        model = model or self._get_model_for_role(role)
        runner = AgentRunner(
            role=role,
            project_path=str(self.project_path),
            config=self.config,
            model=model,
            confirm_callback=self.confirm_callback,
        )
        start = time.time()
        result = await runner.run(AgentTask(role=role, instruction=instruction))
        result.duration = time.time() - start
        return result

    def _parse_decision(self, text: str) -> Dict[str, Any]:
        """解析 Orchestrator 的调度决定."""
        _, cleaned = extract_thinking_tags(text)

        match = re.search(r'\{.*?"needs_coder".*?\}', cleaned, re.DOTALL)
        if not match:
            return {"needs_coder": False}
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return {"needs_coder": False}

    def _format_pipeline_results(self, results: List[AgentResult], user_input: str) -> str:
        """格式化流水线最终结果给用户."""
        lines = [
            "[bold]Agent 流水线执行完成[/bold]",
            f"请求：{user_input}",
            "",
        ]

        # 是否折叠输出（仅显示错误）
        fold_output = self.config.ai.agent_fold_output
        # 是否折叠 thinking 内容
        think_fold = self.config.ai.think_fold
        think_lines = self.config.ai.think_lines

        for result in results:
            status = "[bold green]OK[/bold green]" if result.success else "[bold red]FAIL[/bold red]"
            duration_text = f" ({result.duration:.1f}s)" if result.duration else ""
            lines.append(f"[{status}] {result.role.value}{duration_text}")

            # 显示 thinking 内容（如果有）
            if result.thinking and self.config.ai.think_mode:
                if think_fold:
                    lines.append("[#888888]Thinking... (use /setting think_fold=false to expand)[/#888888]")
                else:
                    lines.append(f"[#888888]{result.thinking}[/#888888]")
                lines.append("")

            if fold_output:
                # 折叠模式：只显示错误信息
                if not result.success:
                    lines.append(result.output)
                else:
                    lines.append("[#666666]（输出已折叠，设置 agent_fold_output=false 可显示完整输出）[/#666666]")
            else:
                # 完整模式：显示所有输出
                lines.append(result.output)

            lines.append("")

        return "\n".join(lines)
