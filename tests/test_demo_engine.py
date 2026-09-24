import tempfile
import unittest
from pathlib import Path
from textwrap import dedent
from uuid import UUID

import yaml
from jsonschema import ValidationError
from jsonschema.exceptions import SchemaError

from demo_engine import DemoEngine, load_config


class DemoEngineTests(unittest.TestCase):
    @staticmethod
    def _config():
        return {
            "state": {"items": []},
            "state_schema": {
                "type": "object",
                "required": ["items"],
                "properties": {"items": {"type": "array"}},
            },
            "tools": [
                {
                    "name": "test_tool",
                    "description": "Test tool",
                    "input_schema": {"type": "object"},
                    "action": {"type": "select", "target": "items"},
                    "result": "$action",
                },
            ],
        }

    @classmethod
    def _engine(
        cls,
        action_yaml,
        *,
        state=None,
        result="$action",
        input_schema=None,
        state_schema=None,
        collections=None,
    ):
        config = cls._config()
        if state is not None:
            config["state"] = state
        if state_schema is not None:
            config["state_schema"] = state_schema
        if collections is not None:
            config["collections"] = collections
        if input_schema is not None:
            config["tools"][0]["input_schema"] = input_schema
        config["tools"][0]["action"] = yaml.safe_load(dedent(action_yaml))
        config["tools"][0]["result"] = result
        return DemoEngine(config)

    @staticmethod
    def _load(config):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "demo.yaml"
            path.write_text(yaml.safe_dump(config))
            return load_config(path)

    def test_output_schema_is_optional_but_checked_when_present(self):
        config = self._config()
        self._load(config)

        config["tools"][0]["output_schema"] = {}
        self._load(config)

        config["tools"][0]["output_schema"] = []
        with self.assertRaises(SchemaError):
            self._load(config)

    def test_false_output_schema_rejects_every_result(self):
        config = self._config()
        config["tools"][0]["output_schema"] = False
        engine = DemoEngine(self._load(config))

        with self.assertRaises(ValidationError):
            engine.execute(engine.create_state(), "test_tool", {})

    def test_select_filters_with_where_and_contains(self):
        state = {
            "items": [
                {"id": "a", "group": "clothing", "name": "Blue Linen Shirt"},
                {"id": "b", "group": "clothing", "name": "Black Wool Coat"},
                {"id": "c", "group": "home", "name": "Blue Linen Pillow"},
            ],
        }
        engine = self._engine(
            """
            type: select
            target: items
            where:
              group: $args.group
            contains:
              value: $args.query
              fields: [name]
            expect: some
            """,
            state=state,
        )

        new_state, result = engine.execute(
            engine.create_state(),
            "test_tool",
            {"group": "clothing", "query": "LINEN"},
        )

        self.assertEqual(["a"], [item["id"] for item in result])
        self.assertEqual(state, new_state)

    def test_select_expectations_are_enforced(self):
        cases = (
            ("one", "missing", "Expected one match"),
            ("some", "missing", "Expected at least one match"),
            ("none", "a", "Expected no matches"),
            ("invalid", "a", "Unknown expectation"),
        )
        for expect, item_id, message in cases:
            with self.subTest(expect=expect):
                engine = self._engine(
                    f"""
                    type: select
                    target: items
                    where:
                      id: {item_id}
                    expect: {expect}
                    """,
                    state={"items": [{"id": "a"}]},
                )

                with self.assertRaisesRegex(ValueError, message):
                    engine.execute(engine.create_state(), "test_tool", {})

    def test_add_copies_a_source_item_and_overlays_values(self):
        engine = self._engine(
            """
            type: add
            target: cart
            source:
              target: items
              where:
                id: $args.id
              expect: one
            value:
              quantity: $args.quantity
            """,
            state={
                "items": [{"id": "a", "name": "Shirt"}],
                "cart": [],
            },
        )
        original = engine.create_state()

        state, result = engine.execute(
            original,
            "test_tool",
            {"id": "a", "quantity": 2},
        )

        expected = {"id": "a", "name": "Shirt", "quantity": 2}
        self.assertEqual(expected, result)
        self.assertEqual([expected], state["cart"])
        self.assertEqual([], original["cart"])

    def test_update_changes_exactly_one_selected_item(self):
        engine = self._engine(
            """
            type: update
            target: items
            where:
              id: $args.id
            changes:
              status: $args.status
            """,
            state={
                "items": [
                    {"id": "a", "status": "old"},
                    {"id": "b", "status": "old"},
                ],
            },
        )

        state, result = engine.execute(
            engine.create_state(),
            "test_tool",
            {"id": "a", "status": "new"},
        )

        self.assertEqual({"id": "a", "status": "new"}, result)
        self.assertEqual("new", state["items"][0]["status"])
        self.assertEqual("old", state["items"][1]["status"])

    def test_remove_can_delete_multiple_selected_items(self):
        engine = self._engine(
            """
            type: remove
            target: items
            where:
              discard: true
            expect: any
            """,
            state={
                "items": [
                    {"id": "a", "discard": True},
                    {"id": "b", "discard": False},
                    {"id": "c", "discard": True},
                ],
            },
        )

        state, result = engine.execute(engine.create_state(), "test_tool", {})

        self.assertEqual(["a", "c"], [item["id"] for item in result])
        self.assertEqual(["b"], [item["id"] for item in state["items"]])

    def test_references_can_traverse_list_indexes(self):
        engine = self._engine(
            """
            type: steps
            steps:
              - id: matches
                type: select
                target: items
                expect: some
              - id: selected
                type: add
                target: selections
                value:
                  item_id: $steps.matches.0.id
            """,
            state={"items": [{"id": "item_1"}], "selections": []},
            result="$action.selected",
        )

        _, result = engine.execute(engine.create_state(), "test_tool", {})

        self.assertEqual({"item_id": "item_1"}, result)

    def test_invalid_references_raise_value_error(self):
        references = (
            "$unknown.value",
            "$state.missing",
            "$state.items.first",
            "$state.items.1",
        )
        for reference in references:
            with self.subTest(reference=reference):
                engine = self._engine(
                    """
                    type: select
                    target: items
                    """,
                    state={"items": [{"id": "item_1"}]},
                    result=reference,
                )

                with self.assertRaisesRegex(ValueError, "Unknown reference"):
                    engine.execute(engine.create_state(), "test_tool", {})

    def test_generated_id_can_be_used_by_a_later_step(self):
        engine = self._engine(
            """
            type: steps
            steps:
              - id: generated_id
                type: generate_id
              - id: saved
                type: add
                target: generated
                value:
                  id: $steps.generated_id
            """,
            state={"items": [], "generated": []},
            result="$action.saved",
        )
        original = engine.create_state()

        state, result = engine.execute(original, "test_tool", {})

        UUID(result["id"])
        self.assertEqual([], original["generated"])
        self.assertEqual(result, state["generated"][0])

    def test_created_states_are_independent(self):
        engine = DemoEngine(self._config())
        first = engine.create_state()
        second = engine.create_state()

        first["items"].append("changed")

        self.assertEqual([], second["items"])
        self.assertEqual([], engine.initial_state["items"])

    def test_execute_validates_tool_arguments_and_current_state(self):
        engine = self._engine(
            """
            type: select
            target: items
            """,
            input_schema={
                "type": "object",
                "required": ["query"],
                "additionalProperties": False,
                "properties": {"query": {"type": "string"}},
            },
        )

        with self.assertRaisesRegex(ValueError, "Unknown tool"):
            engine.execute(engine.create_state(), "missing", {"query": "x"})
        with self.assertRaises(ValidationError):
            engine.execute(engine.create_state(), "test_tool", {})
        with self.assertRaises(ValidationError):
            engine.execute({"items": "not a list"}, "test_tool", {"query": "x"})

    def test_collection_identities_are_enforced_atomically(self):
        engine = self._engine(
            """
            type: add
            target: items
            value:
              id: a
            """,
            state={"items": [{"id": "a"}]},
            collections={"items": {"identity": "id"}},
        )
        original = engine.create_state()

        with self.assertRaisesRegex(ValueError, "Duplicate id: a"):
            engine.execute(original, "test_tool", {})

        self.assertEqual([{"id": "a"}], original["items"])

    def test_failed_state_validation_does_not_mutate_input_state(self):
        state_schema = {
            "type": "object",
            "required": ["items"],
            "properties": {
                "items": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "required": ["id"],
                    },
                },
            },
        }
        engine = self._engine(
            """
            type: add
            target: items
            value:
              name: missing-id
            """,
            state_schema=state_schema,
        )
        original = engine.create_state()

        with self.assertRaises(ValidationError):
            engine.execute(original, "test_tool", {})

        self.assertEqual([], original["items"])

    def test_failed_action_does_not_mutate_input_state(self):
        engine = self._engine(
            """
            type: steps
            steps:
              - type: add
                target: generated
                value:
                  id: temporary
              - type: assert
                target: items
                expect: some
                message: No items
            """,
            state={"items": [], "generated": []},
        )
        original = engine.create_state()

        with self.assertRaisesRegex(ValueError, "No items"):
            engine.execute(original, "test_tool", {})

        self.assertEqual([], original["generated"])

    def test_unknown_actions_and_collections_raise_value_error(self):
        cases = (
            (
                """
                type: unknown
                target: items
                """,
                "Unknown action type",
            ),
            (
                """
                type: select
                target: missing
                """,
                "Unknown collection",
            ),
        )
        for action, message in cases:
            with self.subTest(message=message):
                engine = self._engine(action)
                with self.assertRaisesRegex(ValueError, message):
                    engine.execute(engine.create_state(), "test_tool", {})


if __name__ == "__main__":
    unittest.main()
