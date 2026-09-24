import unittest
from textwrap import dedent

import yaml

from demo_engine import DemoEngine


class NestedFieldTests(unittest.TestCase):
    def test_select_matches_nested_dictionary_and_list_fields(self):
        action = yaml.safe_load(
            dedent(
                """
                type: select
                target: items
                where:
                  customer.id: $args.customer_id
                contains:
                  value: $args.query
                  fields:
                    - customer.name
                    - contacts.0.email
                expect: one
                """,
            ),
        )
        config = {
            "state": {
                "items": [
                    {
                        "id": "a",
                        "customer": {"id": "customer_1", "name": "Acme"},
                        "contacts": [{"email": "support@acme.example"}],
                    },
                    {
                        "id": "b",
                        "customer": {"id": "customer_2", "name": "Other"},
                        "contacts": [],
                    },
                    {"id": "c"},
                ],
            },
            "state_schema": {
                "type": "object",
                "required": ["items"],
                "properties": {"items": {"type": "array"}},
            },
            "tools": [
                {
                    "name": "find_item",
                    "description": "Find an item",
                    "input_schema": {"type": "object"},
                    "action": action,
                    "result": "$action",
                },
            ],
        }
        engine = DemoEngine(config)

        state, result = engine.execute(
            engine.create_state(),
            "find_item",
            {"customer_id": "customer_1", "query": "SUPPORT@"},
        )

        self.assertEqual(["a"], [item["id"] for item in result])
        self.assertEqual(config["state"], state)


if __name__ == "__main__":
    unittest.main()
