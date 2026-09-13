from __future__ import annotations

import argparse
import json
import time
from pathlib import Path
from typing import Any

import boto3
from botocore.exceptions import ClientError


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"


TABLES = {
    "KnowledgeBase": {
        "key_name": "article_id",
        "seed_file": "knowledge_base.json",
    },
    "Employees": {
        "key_name": "employee_id",
        "seed_file": "employees.json",
    },
    "SystemStatus": {
        "key_name": "service",
        "seed_file": "system_status.json",
    },
    "Tickets": {
        "key_name": "ticket_id",
        "seed_file": "tickets.json",
    },
}


def create_table(dynamodb, table_name: str, key_name: str) -> None:
    try:
        dynamodb.create_table(
            TableName=table_name,
            KeySchema=[{"AttributeName": key_name, "KeyType": "HASH"}],
            AttributeDefinitions=[{"AttributeName": key_name, "AttributeType": "S"}],
            BillingMode="PAY_PER_REQUEST",
        )
        print(f"Creating {table_name}...")
        dynamodb.meta.client.get_waiter("table_exists").wait(TableName=table_name)
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ResourceInUseException":
            raise
        print(f"{table_name} already exists.")


def seed_table(dynamodb, table_name: str, records: list[dict[str, Any]]) -> None:
    table = dynamodb.Table(table_name)
    with table.batch_writer() as batch:
        for record in records:
            batch.put_item(Item=record)
    print(f"Seeded {len(records)} record(s) into {table_name}.")


def load_seed_records(seed_file: str) -> list[dict[str, Any]]:
    with (DATA_DIR / seed_file).open("r", encoding="utf-8") as file:
        return json.load(file)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create and seed DynamoDB tables for the IT assistant.")
    parser.add_argument("--region", default="us-east-1", help="AWS region")
    parser.add_argument("--prefix", default="ticket-assistant", help="DynamoDB table prefix")
    parser.add_argument("--skip-seed", action="store_true", help="Create tables without loading seed data")
    args = parser.parse_args()

    dynamodb = boto3.resource("dynamodb", region_name=args.region)
    for suffix, config in TABLES.items():
        table_name = f"{args.prefix}-{suffix}"
        create_table(dynamodb, table_name, config["key_name"])
        if not args.skip_seed:
            records = load_seed_records(config["seed_file"])
            seed_table(dynamodb, table_name, records)
        time.sleep(0.2)

    print("DynamoDB bootstrap complete.")


if __name__ == "__main__":
    main()
