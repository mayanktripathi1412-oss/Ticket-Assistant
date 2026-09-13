from __future__ import annotations

from typing import Any

import streamlit as st

from it_assistant.agent import ITSupportAgent
from it_assistant.models import ToolResult


def _init_session() -> None:
    if "agent" not in st.session_state:
        st.session_state.agent = ITSupportAgent()
    if "messages" not in st.session_state:
        st.session_state.messages = []
    if "tool_events" not in st.session_state:
        st.session_state.tool_events = []


def _reset_session() -> None:
    st.session_state.agent = ITSupportAgent()
    st.session_state.messages = []
    st.session_state.tool_events = []


def _summarize_tool_result(result: ToolResult) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tool": result.tool_name,
        "summary": result.summary,
        "status": "failed" if result.error else "success",
    }
    if result.error:
        row["error"] = result.error
    if isinstance(result.data, list):
        row["records"] = len(result.data)
    elif isinstance(result.data, dict):
        row["record_id"] = result.data.get("ticket_id") or result.data.get("employee_id") or result.data.get("article_id")
    return row


def _capture_new_tool_events(agent: ITSupportAgent, previous_count: int) -> list[dict[str, Any]]:
    new_results = agent.state.tool_history[previous_count:]
    return [_summarize_tool_result(result) for result in new_results]


def main() -> None:
    st.set_page_config(page_title="AI IT Support Assistant", page_icon="IT", layout="centered")
    _init_session()

    st.title("AI IT Support Assistant")
    st.caption("LangGraph workflow with local tools, conversation state, validation, and ticket safety checks.")

    with st.sidebar:
        st.subheader("Session")
        st.write(f"Current intent: `{st.session_state.agent.state.intent}`")
        employee = st.session_state.agent.state.employee
        if employee:
            st.write(f"Employee: `{employee['name']} ({employee['employee_id']})`")
        if st.session_state.agent.state.pending_issue:
            st.write("Pending issue retained.")
        if st.session_state.agent.state.pending_ticket:
            st.write("Pending ticket details retained.")
        if st.button("Clear conversation", use_container_width=True):
            _reset_session()
            st.rerun()

        st.subheader("Tool Actions")
        if st.session_state.tool_events:
            for index, event in enumerate(reversed(st.session_state.tool_events), start=1):
                with st.expander(f"{event['tool']} - {event['status']}", expanded=index == 1):
                    st.json(event)
        else:
            st.caption("No tools have run yet.")

    for message in st.session_state.messages:
        with st.chat_message(message["role"]):
            st.markdown(message["content"])

    prompt = st.chat_input("Ask for IT help, ticket status, or ticket creation")
    if not prompt:
        return

    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    with st.chat_message("assistant"):
        try:
            previous_count = len(st.session_state.agent.state.tool_history)
            response = st.session_state.agent.handle(prompt)
            st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.tool_events.extend(
                _capture_new_tool_events(st.session_state.agent, previous_count)
            )
        except Exception as exc:
            response = (
                "I could not complete that request because the application encountered an error. "
                "Please try again or reset the conversation."
            )
            st.error(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
            st.session_state.tool_events.append(
                {"tool": "streamlit_app", "summary": "UI request handling failed.", "status": "failed", "error": str(exc)}
            )


if __name__ == "__main__":
    main()
