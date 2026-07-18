"""Agent 集群数据模型."""

from enum import Enum
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


class AgentRole(str, Enum):
    """Agent 角色."""

    ORCHESTRATOR = "orchestrator"
    CODER = "coder"
    PLANNER = "planner"
    REVIEWER = "reviewer"
    TESTER = "tester"


@dataclass
class AgentTask:
    """分派给 Specialist 的任务."""

    role: AgentRole
    instruction: str
    context: Dict[str, Any] = field(default_factory=dict)


@dataclass
class AgentResult:
    """Agent 执行结果."""

    role: AgentRole
    success: bool
    output: str
    tool_calls: List[Dict[str, Any]] = field(default_factory=list)
    error: Optional[str] = None
    thinking: Optional[str] = None
    duration: Optional[float] = None
