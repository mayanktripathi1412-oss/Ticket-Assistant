from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .models import ToolResult
from .repositories import SupportRepository, get_repository


def _tokenize(text: str) -> set[str]:
    cleaned = "".join(char.lower() if char.isalnum() else " " for char in text)
    return {token for token in cleaned.split() if len(token) > 2}


def knowledge_search(query: str, limit: int = 2, repository: SupportRepository | None = None) -> ToolResult:
    articles = (repository or get_repository()).list_knowledge_articles()
    query_tokens = _tokenize(query)
    scored_articles = []
    for article in articles:
        haystack = " ".join(
            [
                article["title"],
                article["category"],
                " ".join(article["tags"]),
                article["body"],
            ]
        )
        score = len(query_tokens & _tokenize(haystack))
        if score:
            scored_articles.append((score, article))

    matches = [article for _, article in sorted(scored_articles, key=lambda item: item[0], reverse=True)[:limit]]
    if not matches:
        return ToolResult("knowledge_search", [], "No matching knowledge base article was found.")

    top = matches[0]
    return ToolResult(
        "knowledge_search",
        matches,
        f"Found article '{top['title']}' with {len(top['steps'])} recommended steps.",
    )


def employee_lookup(query: str, repository: SupportRepository | None = None) -> ToolResult:
    employees = (repository or get_repository()).list_employees()
    query_lower = query.lower().strip(" .,:;")
    matches = [
        employee
        for employee in employees
        if query_lower in employee["name"].lower()
        or query_lower in employee["email"].lower()
        or query_lower == employee["employee_id"].lower()
    ]

    if not matches:
        return ToolResult("employee_lookup", [], "No employee matched the request.")

    employee = matches[0]
    return ToolResult(
        "employee_lookup",
        matches,
        f"Matched {employee['name']} from {employee['department']} ({employee['employee_id']}).",
    )


def system_status(service_query: str, repository: SupportRepository | None = None) -> ToolResult:
    services = (repository or get_repository()).list_system_statuses()
    tokens = _tokenize(service_query)
    matches = []
    for service in services:
        text = f"{service['service']} {' '.join(service['aliases'])}"
        if tokens & _tokenize(text):
            matches.append(service)

    if not matches:
        matches = services

    impacted = [service for service in matches if service["status"] != "operational"]
    if impacted:
        summary = "; ".join(f"{service['service']}: {service['status']}" for service in impacted)
    else:
        summary = "All matched services are operational."

    return ToolResult("system_status", matches, summary)


def ticket_search(query: str, repository: SupportRepository | None = None) -> ToolResult:
    tickets = (repository or get_repository()).list_tickets()
    tokens = _tokenize(query)
    employee_ids = {token for token in tokens if token.startswith("e") or token.startswith("emp")}
    matches = []
    for ticket in tickets:
        if employee_ids and ticket["employee_id"].lower() not in employee_ids:
            continue
        text = f"{ticket['ticket_id']} {ticket['employee_id']} {ticket['title']} {ticket['description']} {ticket['status']}"
        if tokens & _tokenize(text):
            matches.append(ticket)

    if not matches:
        return ToolResult("ticket_search", [], "No related tickets found.")

    return ToolResult("ticket_search", matches, f"Found {len(matches)} related ticket(s).")


def ticket_create(
    employee_id: str,
    title: str,
    description: str,
    priority: str = "medium",
    repository: SupportRepository | None = None,
) -> ToolResult:
    repo = repository or get_repository()
    tickets = repo.list_tickets()
    next_number = 1
    if tickets:
        next_number = max(int(ticket["ticket_id"].split("-")[-1]) for ticket in tickets) + 1

    ticket = {
        "ticket_id": f"IT-{next_number:04d}",
        "employee_id": employee_id,
        "title": title,
        "description": description,
        "priority": priority,
        "status": "open",
        "created_at": datetime.now(timezone.utc).isoformat(),
    }
    repo.save_ticket(ticket)
    return ToolResult("ticket_create", ticket, f"Created ticket {ticket['ticket_id']} for {employee_id}.")
