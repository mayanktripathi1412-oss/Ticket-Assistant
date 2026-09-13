from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Protocol


DATA_DIR = Path(__file__).resolve().parent.parent / "data"


class SupportRepository(Protocol):
    def list_knowledge_articles(self) -> list[dict[str, Any]]:
        ...

    def list_employees(self) -> list[dict[str, Any]]:
        ...

    def list_system_statuses(self) -> list[dict[str, Any]]:
        ...

    def list_tickets(self) -> list[dict[str, Any]]:
        ...

    def save_ticket(self, ticket: dict[str, Any]) -> None:
        ...


class JsonRepository:
    def __init__(self, data_dir: Path = DATA_DIR) -> None:
        self.data_dir = data_dir

    def list_knowledge_articles(self) -> list[dict[str, Any]]:
        return self._load("knowledge_base.json")

    def list_employees(self) -> list[dict[str, Any]]:
        return self._load("employees.json")

    def list_system_statuses(self) -> list[dict[str, Any]]:
        return self._load("system_status.json")

    def list_tickets(self) -> list[dict[str, Any]]:
        return self._load("tickets.json")

    def save_ticket(self, ticket: dict[str, Any]) -> None:
        tickets = self.list_tickets()
        tickets.append(ticket)
        self._save("tickets.json", tickets)

    def _load(self, file_name: str) -> list[dict[str, Any]]:
        with (self.data_dir / file_name).open("r", encoding="utf-8") as file:
            return json.load(file)

    def _save(self, file_name: str, payload: list[dict[str, Any]]) -> None:
        with (self.data_dir / file_name).open("w", encoding="utf-8") as file:
            json.dump(payload, file, indent=2)
            file.write("\n")


class DynamoDBRepository:
    def __init__(
        self,
        *,
        region_name: str | None = None,
        table_prefix: str | None = None,
        dynamodb_resource: Any | None = None,
    ) -> None:
        if dynamodb_resource is None:
            import boto3

            dynamodb_resource = boto3.resource(
                "dynamodb",
                region_name=region_name or os.getenv("AWS_REGION", "us-east-1"),
            )
        self.dynamodb = dynamodb_resource
        self.table_prefix = table_prefix or os.getenv("DYNAMODB_TABLE_PREFIX", "ticket-assistant")

    def list_knowledge_articles(self) -> list[dict[str, Any]]:
        return self._scan_table("KnowledgeBase")

    def list_employees(self) -> list[dict[str, Any]]:
        return self._scan_table("Employees")

    def list_system_statuses(self) -> list[dict[str, Any]]:
        return self._scan_table("SystemStatus")

    def list_tickets(self) -> list[dict[str, Any]]:
        return self._scan_table("Tickets")

    def save_ticket(self, ticket: dict[str, Any]) -> None:
        self._table("Tickets").put_item(Item=ticket)

    def _scan_table(self, table_suffix: str) -> list[dict[str, Any]]:
        table = self._table(table_suffix)
        items: list[dict[str, Any]] = []
        response = table.scan()
        items.extend(response.get("Items", []))
        while "LastEvaluatedKey" in response:
            response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
            items.extend(response.get("Items", []))
        return items

    def _table(self, table_suffix: str):
        return self.dynamodb.Table(f"{self.table_prefix}-{table_suffix}")


def get_repository() -> SupportRepository:
    backend = os.getenv("STORAGE_BACKEND", "json").lower()
    if backend == "dynamodb":
        return DynamoDBRepository()
    if backend == "json":
        return JsonRepository()
    raise ValueError(f"Unsupported STORAGE_BACKEND '{backend}'. Use 'json' or 'dynamodb'.")
