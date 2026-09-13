from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import it_assistant.tools as tools
from it_assistant.agent import ITSupportAgent
from it_assistant.repositories import JsonRepository


class ITSupportAgentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.data_dir = Path(self.temp_dir.name)
        source_dir = Path(__file__).resolve().parent.parent / "data"
        for source in source_dir.glob("*.json"):
            shutil.copy(source, self.data_dir / source.name)
        self.repository = JsonRepository(self.data_dir)
        self.patch_repository = patch.object(tools, "get_repository", return_value=self.repository)
        self.patch_repository.start()

    def tearDown(self) -> None:
        self.patch_repository.stop()
        self.temp_dir.cleanup()

    def test_routes_to_knowledge_search(self) -> None:
        agent = ITSupportAgent()
        response = agent.handle("How do I reset my VPN password?")

        self.assertIn("Reset a VPN password", response)
        self.assertIn("Retrieved information:", response)
        self.assertIn("Generated recommendation based on the article:", response)
        self.assertEqual(agent.state.intent, "knowledge")
        self.assertEqual([result.tool_name for result in agent.state.tool_history], ["knowledge_search"])

    def test_routes_to_system_status(self) -> None:
        agent = ITSupportAgent()
        response = agent.handle("Is email down?")

        self.assertIn("Email: degraded", response)
        self.assertEqual(agent.state.intent, "status")
        self.assertEqual([result.tool_name for result in agent.state.tool_history], ["system_status"])

    def test_routes_to_ticket_lookup(self) -> None:
        agent = ITSupportAgent()
        response = agent.handle("What is the status of my laptop issue?")

        self.assertIn("Found 1 related ticket(s)", response)
        self.assertIn("IT-0001", response)
        self.assertEqual(agent.state.intent, "ticket_search")
        self.assertEqual([result.tool_name for result in agent.state.tool_history], ["ticket_search"])

    def test_multi_step_ticket_creation(self) -> None:
        agent = ITSupportAgent()
        response = agent.handle(
            "Create a ticket for Priya Nair: laptop will not connect to wifi"
        )

        self.assertIn("Created IT-0002 for Priya Nair", response)
        self.assertEqual(agent.state.intent, "create_ticket")
        self.assertEqual(agent.state.employee["employee_id"], "E1001")
        self.assertEqual(
            [result.tool_name for result in agent.state.tool_history],
            ["employee_lookup", "ticket_search", "ticket_create"],
        )
        tickets = json.loads((self.data_dir / "tickets.json").read_text(encoding="utf-8"))
        self.assertEqual(tickets[-1]["employee_id"], "E1001")
        self.assertEqual(tickets[-1]["status"], "open")

    def test_ticket_creation_collects_missing_employee(self) -> None:
        agent = ITSupportAgent()

        first_response = agent.handle("My VPN is not working. Please raise a ticket.")
        second_response = agent.handle("Alex Morgan")

        self.assertIn("Please provide the employee name or email", first_response)
        self.assertIn("Created IT-0002 for Alex Morgan", second_response)
        self.assertEqual(agent.state.intent, "create_ticket")
        self.assertIsNone(agent.state.pending_ticket)
        self.assertEqual(
            [result.tool_name for result in agent.state.tool_history],
            ["employee_lookup", "ticket_search", "ticket_create"],
        )
        tickets = json.loads((self.data_dir / "tickets.json").read_text(encoding="utf-8"))
        self.assertEqual(tickets[-1]["description"], "My VPN is not working.")

    def test_issue_triage_retains_state_until_ticket_lookup_confirmation(self) -> None:
        agent = ITSupportAgent()

        first_response = agent.handle("I have a VPN issue.")
        second_response = agent.handle("E1002.")
        third_response = agent.handle("Yes.")

        self.assertIn("What is your employee ID", first_response)
        self.assertIn("I found your profile: Alex Morgan (E1002)", second_response)
        self.assertIn("Would you like me to check existing tickets?", second_response)
        self.assertIn("Found 1 related ticket(s)", third_response)
        self.assertIn("IT-0001", third_response)
        self.assertEqual(agent.state.employee["employee_id"], "E1002")
        self.assertEqual(agent.state.pending_issue["issue"], "I have a VPN issue.")
        self.assertEqual(
            [result.tool_name for result in agent.state.tool_history],
            ["employee_lookup", "ticket_search"],
        )

    def test_issue_triage_supports_example_employee_id(self) -> None:
        agent = ITSupportAgent()

        first_response = agent.handle("I have a VPN issue.")
        second_response = agent.handle("EMP1024.")
        third_response = agent.handle("Yes.")

        self.assertIn("What is your employee ID", first_response)
        self.assertIn("I found your profile: Jordan Lee (EMP1024)", second_response)
        self.assertIn("I did not find an existing ticket", third_response)

    def test_ticket_creation_requires_issue_details(self) -> None:
        agent = ITSupportAgent()

        response = agent.handle("Please raise a ticket.")

        self.assertIn("Please describe the IT issue", response)
        self.assertEqual(agent.state.intent, "awaiting_ticket_details")
        self.assertEqual(agent.state.tool_history, [])

    def test_ticket_creation_does_not_create_duplicate_active_ticket(self) -> None:
        agent = ITSupportAgent()

        response = agent.handle("Create a ticket for Alex Morgan: VPN disconnects every hour")

        self.assertIn("I found an existing active ticket", response)
        self.assertIn("IT-0001", response)
        self.assertEqual(agent.state.intent, "duplicate_ticket")
        self.assertEqual(
            [result.tool_name for result in agent.state.tool_history],
            ["employee_lookup", "ticket_search"],
        )
        tickets = json.loads((self.data_dir / "tickets.json").read_text(encoding="utf-8"))
        self.assertEqual(len(tickets), 1)

    def test_tool_failure_is_handled_gracefully(self) -> None:
        agent = ITSupportAgent()

        with patch("it_assistant.agent.knowledge_search", side_effect=OSError("missing kb")):
            response = agent.handle("How do I reset my VPN password?")

        self.assertIn("knowledge_search tool failed", response)
        self.assertEqual(agent.state.tool_history[-1].tool_name, "knowledge_search")
        self.assertEqual(agent.state.tool_history[-1].error, "missing kb")


if __name__ == "__main__":
    unittest.main()
