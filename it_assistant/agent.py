from __future__ import annotations

import re
import warnings
from typing import Any, TypedDict

try:
    from langchain_core._api.deprecation import LangChainPendingDeprecationWarning
except ImportError:
    LangChainPendingDeprecationWarning = PendingDeprecationWarning

warnings.filterwarnings("ignore", category=LangChainPendingDeprecationWarning)

from langgraph.graph import END, StateGraph

from .models import AgentState, ToolResult
from .tools import employee_lookup, knowledge_search, system_status, ticket_create, ticket_search


class WorkflowState(TypedDict, total=False):
    user_request: str
    intent: str
    employee: dict[str, Any] | None
    pending_ticket: dict[str, Any] | None
    pending_issue: dict[str, Any] | None
    tool_history: list[ToolResult]
    response: str
    employee_query: str
    issue: str
    priority: str
    related_tickets: list[dict[str, Any]]
    duplicate_ticket: dict[str, Any]
    ticket_query: str


class ITSupportAgent:
    """LangGraph-powered agent that routes requests to local IT support tools."""

    def __init__(self) -> None:
        self.state = AgentState()
        self.workflow = self._build_workflow()

    def handle(self, user_request: str) -> str:
        graph_input: WorkflowState = {
            "user_request": user_request,
            "tool_history": [],
            "employee": None,
            "pending_ticket": None,
            "pending_issue": None,
        }
        if self.state.intent in {
            "awaiting_ticket_employee",
            "awaiting_ticket_details",
            "awaiting_issue_employee",
            "awaiting_ticket_check_confirmation",
        }:
            graph_input["intent"] = self.state.intent
            graph_input["employee"] = self.state.employee
            graph_input["pending_ticket"] = self.state.pending_ticket
            graph_input["pending_issue"] = self.state.pending_issue
            graph_input["tool_history"] = self.state.tool_history

        graph_output = self.workflow.invoke(graph_input)
        self.state = AgentState(
            user_request=graph_output.get("user_request", user_request),
            intent=graph_output.get("intent", "unknown"),
            employee=graph_output.get("employee"),
            pending_ticket=graph_output.get("pending_ticket"),
            pending_issue=graph_output.get("pending_issue"),
            tool_history=graph_output.get("tool_history", []),
        )
        return graph_output.get("response", "")

    def _build_workflow(self):
        workflow = StateGraph(WorkflowState)
        workflow.add_node("decide_intent", self._decision_node)
        workflow.add_node("knowledge_search", self._knowledge_search_node)
        workflow.add_node("ticket_lookup", self._ticket_lookup_node)
        workflow.add_node("ticket_creation", self._ticket_creation_node)
        workflow.add_node("issue_triage", self._issue_triage_node)
        workflow.add_node("status_check", self._status_check_node)
        workflow.add_node("generate_response", self._response_generation_node)

        workflow.set_entry_point("decide_intent")
        workflow.add_conditional_edges(
            "decide_intent",
            self._route_from_intent,
            {
                "knowledge": "knowledge_search",
                "ticket_search": "ticket_lookup",
                "create_ticket": "ticket_creation",
                "issue_triage": "issue_triage",
                "status": "status_check",
                "respond": "generate_response",
            },
        )
        workflow.add_edge("knowledge_search", "generate_response")
        workflow.add_edge("ticket_lookup", "generate_response")
        workflow.add_edge("ticket_creation", "generate_response")
        workflow.add_edge("issue_triage", "generate_response")
        workflow.add_edge("status_check", "generate_response")
        workflow.add_edge("generate_response", END)
        return workflow.compile()

    def _decision_node(self, state: WorkflowState) -> WorkflowState:
        if state.get("intent") == "awaiting_ticket_employee" and state.get("pending_ticket"):
            return {
                **state,
                "intent": "create_ticket",
                "employee_query": state["user_request"].strip(),
            }
        if state.get("intent") == "awaiting_ticket_details" and state.get("pending_ticket"):
            return {
                **state,
                "intent": "create_ticket",
                "pending_ticket": {
                    "issue": state["user_request"].strip(),
                    "priority": self._infer_priority(state["user_request"]),
                },
            }
        if state.get("intent") == "awaiting_issue_employee" and state.get("pending_issue"):
            return {
                **state,
                "intent": "issue_triage",
                "employee_query": state["user_request"].strip(),
            }
        if state.get("intent") == "awaiting_ticket_check_confirmation" and state.get("pending_issue"):
            if self._is_affirmative(state["user_request"]):
                employee = state.get("employee") or {}
                issue = str(state["pending_issue"].get("issue") or "")
                return {
                    **state,
                    "intent": "ticket_search",
                    "ticket_query": f"{employee.get('employee_id', '')} {issue}".strip(),
                }
            return {
                **state,
                "intent": "respond",
                "response": "Okay, I will not check tickets right now.",
            }

        request = state["user_request"]
        return {**state, "intent": self._classify_intent(request)}

    def _route_from_intent(self, state: WorkflowState) -> str:
        return state.get("intent", "knowledge")

    def _knowledge_search_node(self, state: WorkflowState) -> WorkflowState:
        result = self._run_tool("knowledge_search", knowledge_search, state["user_request"])
        return self._with_tool_result(state, result)

    def _ticket_lookup_node(self, state: WorkflowState) -> WorkflowState:
        result = self._run_tool("ticket_search", ticket_search, state.get("ticket_query") or state["user_request"])
        return self._with_tool_result(state, result)

    def _status_check_node(self, state: WorkflowState) -> WorkflowState:
        result = self._run_tool("system_status", system_status, state["user_request"])
        return self._with_tool_result(state, result)

    def _ticket_creation_node(self, state: WorkflowState) -> WorkflowState:
        request = state["user_request"]
        pending_ticket = state.get("pending_ticket")
        employee_query = state.get("employee_query") or self._extract_employee_query(request)
        issue = str((pending_ticket or {}).get("issue") or self._extract_issue(request))
        priority = str((pending_ticket or {}).get("priority") or self._infer_priority(request))

        if not self._has_required_issue_details(issue):
            return {
                **state,
                "intent": "awaiting_ticket_details",
                "pending_ticket": {"issue": issue, "priority": priority},
                "issue": issue,
                "priority": priority,
            }

        if not employee_query:
            return {
                **state,
                "intent": "awaiting_ticket_employee",
                "pending_ticket": {"issue": issue, "priority": priority},
                "issue": issue,
                "priority": priority,
            }

        employee_result = self._run_tool("employee_lookup", employee_lookup, employee_query)
        next_state = self._with_tool_result(state, employee_result)
        if employee_result.error:
            return {**next_state, "intent": "tool_error"}
        if not employee_result.data:
            return {
                **next_state,
                "intent": "awaiting_ticket_employee",
                "pending_ticket": {"issue": issue, "priority": priority},
                "employee_query": employee_query,
                "issue": issue,
                "priority": priority,
            }

        employee = employee_result.data[0]
        related_tickets = []
        related_result = self._run_tool(
            "ticket_search",
            ticket_search,
            f"{employee['employee_id']} {issue}",
        )
        related_tickets = related_result.data if not related_result.error else []
        next_state = self._with_tool_result(next_state, related_result)
        duplicate_ticket = self._find_active_duplicate(related_tickets, issue)
        if duplicate_ticket:
            return {
                **next_state,
                "intent": "duplicate_ticket",
                "employee": employee,
                "pending_ticket": None,
                "issue": issue,
                "priority": priority,
                "related_tickets": related_tickets,
                "duplicate_ticket": duplicate_ticket,
            }

        create_result = self._run_tool(
            "ticket_create",
            ticket_create,
            employee_id=employee["employee_id"],
            title=self._title_from_issue(issue),
            description=issue,
            priority=priority,
        )
        next_state = self._with_tool_result(next_state, create_result)
        return {
            **next_state,
            "employee": employee,
            "pending_ticket": None,
            "issue": issue,
            "priority": priority,
            "related_tickets": related_tickets,
        }

    def _issue_triage_node(self, state: WorkflowState) -> WorkflowState:
        request = state["user_request"]
        pending_issue = state.get("pending_issue") or {
            "issue": self._extract_issue(request),
            "priority": self._infer_priority(request),
        }
        employee_query = state.get("employee_query") or self._extract_employee_query(request)

        if not employee_query:
            return {
                **state,
                "intent": "awaiting_issue_employee",
                "pending_issue": pending_issue,
            }

        employee_result = self._run_tool("employee_lookup", employee_lookup, employee_query)
        next_state = self._with_tool_result(state, employee_result)
        if employee_result.error:
            return {**next_state, "intent": "tool_error"}
        if not employee_result.data:
            return {
                **next_state,
                "intent": "awaiting_issue_employee",
                "pending_issue": pending_issue,
                "employee_query": employee_query,
            }

        return {
            **next_state,
            "intent": "awaiting_ticket_check_confirmation",
            "employee": employee_result.data[0],
            "pending_issue": pending_issue,
        }

    def _response_generation_node(self, state: WorkflowState) -> WorkflowState:
        intent = state.get("intent", "knowledge")
        tool_history = state.get("tool_history", [])
        latest_result = tool_history[-1] if tool_history else None

        if intent == "awaiting_ticket_employee":
            response = self._format_missing_employee_response(state, latest_result)
        elif intent == "awaiting_ticket_details":
            response = "Please describe the IT issue before I create a ticket."
        elif intent == "awaiting_issue_employee":
            response = self._format_issue_employee_request(state, latest_result)
        elif intent == "awaiting_ticket_check_confirmation":
            response = self._format_ticket_check_confirmation(state)
        elif intent == "duplicate_ticket":
            response = self._format_duplicate_ticket_response(state)
        elif intent == "tool_error":
            response = self._format_tool_error_response(latest_result)
        elif intent == "respond":
            response = state.get("response", "Okay.")
        elif intent == "status":
            response = self._format_status_response(latest_result)
        elif intent == "ticket_search":
            response = self._format_ticket_lookup_response(latest_result)
        elif intent == "create_ticket":
            response = self._format_ticket_creation_response(state, latest_result)
        else:
            response = self._format_knowledge_response(latest_result)
        return {**state, "response": response}

    def _with_tool_result(self, state: WorkflowState, result: ToolResult) -> WorkflowState:
        return {**state, "tool_history": [*state.get("tool_history", []), result]}

    def _run_tool(self, tool_name: str, tool_func, *args, **kwargs) -> ToolResult:
        try:
            return tool_func(*args, **kwargs)
        except Exception as exc:
            return ToolResult(
                tool_name=tool_name,
                data=None,
                summary=f"{tool_name} failed.",
                error=str(exc),
            )

    def _classify_intent(self, request: str) -> str:
        text = request.lower()
        if re.search(r"\b(create|open|raise|log)\s+(an?\s+)?ticket\b", text):
            return "create_ticket"
        if any(term in text for term in ["my ticket", "ticket status", "existing ticket", "check ticket"]):
            return "ticket_search"
        if "status" in text and any(term in text for term in ["issue", "problem", "request", "laptop"]):
            return "ticket_search"
        if any(term in text for term in ["down", "outage", "status", "available", "working now"]):
            return "status"
        if any(term in text for term in ["issue", "problem", "not working", "cannot connect", "unable to connect"]):
            return "issue_triage"
        return "knowledge"

    def _format_knowledge_response(self, result: ToolResult | None) -> str:
        if result and result.error:
            return self._format_tool_error_response(result)
        if not result or not result.data:
            return (
                "I could not find a matching knowledge base article. "
                "Please share the application name, error message, and when the issue started."
            )

        article = result.data[0]
        steps = "\n".join(f"{index}. {step}" for index, step in enumerate(article["steps"], start=1))
        return (
            f"Retrieved knowledge article: {article['title']}\n\n"
            f"Retrieved information: {article['body']}\n\n"
            f"Generated recommendation based on the article:\n{steps}"
        )

    def _format_status_response(self, result: ToolResult | None) -> str:
        if result and result.error:
            return self._format_tool_error_response(result)
        if not result:
            return "I could not check system status right now."
        services = result.data
        lines = [f"Retrieved system status: {result.summary}", ""]
        for service in services:
            lines.append(
                f"- {service['service']}: {service['status']} "
                f"(last checked {service['last_checked']}) - {service['message']}"
            )
        return "\n".join(lines)

    def _format_ticket_lookup_response(self, result: ToolResult | None) -> str:
        if result and result.error:
            return self._format_tool_error_response(result)
        if not result or not result.data:
            return "I did not find an existing ticket matching that request."

        lines = [f"Retrieved ticket information: {result.summary}"]
        for ticket in result.data:
            lines.append(
                f"- {ticket['ticket_id']}: {ticket['title']} "
                f"[{ticket['status']}, {ticket['priority']}]"
            )
        return "\n".join(lines)

    def _format_issue_employee_request(
        self, state: WorkflowState, result: ToolResult | None
    ) -> str:
        employee_query = state.get("employee_query")
        if result and result.tool_name == "employee_lookup" and employee_query:
            return (
                f"I could not find an employee matching '{employee_query}'. "
                "Please provide your employee ID or company email."
            )
        return "What is your employee ID or company email?"

    def _format_ticket_check_confirmation(self, state: WorkflowState) -> str:
        employee = state.get("employee") or {}
        return (
            f"I found your profile: {employee.get('name')} "
            f"({employee.get('employee_id')}). Would you like me to check existing tickets?"
        )

    def _format_ticket_creation_response(self, state: WorkflowState, result: ToolResult | None) -> str:
        if result and result.error:
            return self._format_tool_error_response(result)
        if not result or result.tool_name != "ticket_create":
            return "I could not create the ticket. Please provide the employee name or email and issue details."
        employee = state.get("employee") or {}
        related_note = ""
        related_tickets = state.get("related_tickets") or []
        if related_tickets:
            related_ids = ", ".join(ticket["ticket_id"] for ticket in related_tickets[:3])
            related_note = f"\nRelated existing ticket(s): {related_ids}"

        ticket = result.data
        return (
            f"Created {ticket['ticket_id']} for {employee.get('name', ticket['employee_id'])} from validated information.\n"
            f"Priority: {ticket['priority']}\n"
            f"Issue: {ticket['description']}"
            f"{related_note}"
        )

    def _format_duplicate_ticket_response(self, state: WorkflowState) -> str:
        ticket = state["duplicate_ticket"]
        employee = state.get("employee") or {}
        return (
            "I found an existing active ticket for this employee and issue, so I did not create a duplicate.\n"
            f"Retrieved ticket information: {ticket['ticket_id']}: {ticket['title']} "
            f"[{ticket['status']}, {ticket['priority']}]\n"
            f"Employee: {employee.get('name', ticket['employee_id'])}"
        )

    def _format_tool_error_response(self, result: ToolResult | None) -> str:
        if not result:
            return "I could not complete that action because a tool failed."
        return (
            f"I could not complete that action because the {result.tool_name} tool failed. "
            "Please try again or contact IT support directly."
        )

    def _format_missing_employee_response(
        self, state: WorkflowState, result: ToolResult | None
    ) -> str:
        employee_query = state.get("employee_query")
        if result and result.tool_name == "employee_lookup" and employee_query:
            return (
                f"I could not find an employee matching '{employee_query}'. "
                "Please provide a full name or email."
            )
        return "Please provide the employee name or email so I can create the ticket."

    def _extract_employee_query(self, request: str) -> str:
        patterns = [
            r"\bfor\s+([^:]+):",
            r"\bfor\s+(.+?)\s+(?:about|because|regarding|with)\b",
            r"\bemployee\s+([\w.-]+@[\w.-]+)",
        ]
        for pattern in patterns:
            match = re.search(pattern, request, flags=re.IGNORECASE)
            if match:
                return match.group(1).strip()
        email_match = re.search(r"[\w.-]+@[\w.-]+", request)
        return email_match.group(0) if email_match else ""

    def _extract_issue(self, request: str) -> str:
        if ":" in request:
            return request.split(":", 1)[1].strip()
        issue = re.sub(r"^(create|open|raise|log)\s+(an?\s+)?ticket\s+", "", request, flags=re.IGNORECASE)
        issue = re.sub(r"\bfor\s+.+?\s+(about|because|regarding|with)\b", "", issue, flags=re.IGNORECASE)
        issue = re.sub(r"\bplease\s+(create|open|raise|log)\s+(an?\s+)?ticket\.?", "", issue, flags=re.IGNORECASE)
        issue = re.sub(r"\b(create|open|raise|log)\s+(an?\s+)?ticket\.?", "", issue, flags=re.IGNORECASE)
        return issue.strip() or request

    def _infer_priority(self, request: str) -> str:
        text = request.lower()
        if any(term in text for term in ["urgent", "critical", "blocked", "cannot work", "outage"]):
            return "high"
        if any(term in text for term in ["low", "minor", "when possible"]):
            return "low"
        return "medium"

    def _is_affirmative(self, request: str) -> bool:
        return request.lower().strip(" .,!") in {"yes", "y", "yeah", "sure", "ok", "okay", "please do"}

    def _has_required_issue_details(self, issue: str) -> bool:
        tokens = [token for token in re.findall(r"[a-z0-9]+", issue.lower()) if token not in {"please", "ticket"}]
        return len(tokens) >= 3

    def _find_active_duplicate(self, tickets: list[dict[str, Any]], issue: str) -> dict[str, Any] | None:
        issue_tokens = set(re.findall(r"[a-z0-9]+", issue.lower())) - {
            "the",
            "and",
            "for",
            "not",
            "working",
            "issue",
            "problem",
        }
        for ticket in tickets:
            ticket_text = f"{ticket.get('title', '')} {ticket.get('description', '')}"
            ticket_tokens = set(re.findall(r"[a-z0-9]+", ticket_text.lower())) - {
                "the",
                "and",
                "for",
                "not",
                "working",
                "issue",
                "problem",
            }
            shared_tokens = issue_tokens & ticket_tokens
            if ticket.get("status") in {"open", "in_progress"} and len(shared_tokens) >= 2:
                return ticket
        return None

    def _title_from_issue(self, issue: str) -> str:
        cleaned = issue.strip().rstrip(".")
        if len(cleaned) <= 60:
            return cleaned.capitalize()
        return f"{cleaned[:57].rstrip()}..."
