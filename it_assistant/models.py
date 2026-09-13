from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ToolResult:
    tool_name: str
    data: Any
    summary: str
    error: str | None = None


@dataclass
class AgentState:
    user_request: str = ""
    intent: str = "unknown"
    employee: dict[str, Any] | None = None
    pending_ticket: dict[str, Any] | None = None
    pending_issue: dict[str, Any] | None = None
    tool_history: list[ToolResult] = field(default_factory=list)

    def record(self, result: ToolResult) -> None:
        self.tool_history.append(result)
