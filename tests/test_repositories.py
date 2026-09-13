from __future__ import annotations

import unittest

from it_assistant.repositories import DynamoDBRepository


class FakeTable:
    def __init__(self, pages: list[dict] | None = None) -> None:
        self.pages = pages or [{"Items": []}]
        self.scan_calls: list[dict] = []
        self.put_items: list[dict] = []

    def scan(self, **kwargs):
        self.scan_calls.append(kwargs)
        if "ExclusiveStartKey" in kwargs:
            return self.pages[1]
        return self.pages[0]

    def put_item(self, Item):
        self.put_items.append(Item)
        return {"ResponseMetadata": {"HTTPStatusCode": 200}}


class FakeDynamoDB:
    def __init__(self) -> None:
        self.tables = {
            "demo-Tickets": FakeTable(
                [
                    {"Items": [{"ticket_id": "IT-0001"}], "LastEvaluatedKey": {"ticket_id": "IT-0001"}},
                    {"Items": [{"ticket_id": "IT-0002"}]},
                ]
            )
        }

    def Table(self, name: str):
        if name not in self.tables:
            self.tables[name] = FakeTable()
        return self.tables[name]


class DynamoDBRepositoryTests(unittest.TestCase):
    def test_scans_paginated_ticket_table(self) -> None:
        dynamodb = FakeDynamoDB()
        repository = DynamoDBRepository(table_prefix="demo", dynamodb_resource=dynamodb)

        tickets = repository.list_tickets()

        self.assertEqual(tickets, [{"ticket_id": "IT-0001"}, {"ticket_id": "IT-0002"}])
        self.assertEqual(
            dynamodb.tables["demo-Tickets"].scan_calls,
            [{}, {"ExclusiveStartKey": {"ticket_id": "IT-0001"}}],
        )

    def test_writes_ticket_to_dynamodb(self) -> None:
        dynamodb = FakeDynamoDB()
        repository = DynamoDBRepository(table_prefix="demo", dynamodb_resource=dynamodb)
        ticket = {"ticket_id": "IT-0003", "employee_id": "E1001"}

        repository.save_ticket(ticket)

        self.assertEqual(dynamodb.tables["demo-Tickets"].put_items, [ticket])


if __name__ == "__main__":
    unittest.main()
