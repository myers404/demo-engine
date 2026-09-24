import tempfile
import unittest
from pathlib import Path
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
                    "name": "list_items",
                    "description": "List items",
                    "input_schema": {"type": "object"},
                    "action": {"type": "select", "target": "items"},
                    "result": {"items": "$action"},
                },
            ],
        }

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
        state = engine.create_state()

        with self.assertRaises(ValidationError):
            engine.execute(state, "list_items", {})

    def test_references_can_traverse_list_indexes(self):
        config = self._config()
        config["state"] = {"items": [{"id": "item_1"}], "selections": []}
        config["tools"][0]["action"] = {
            "type": "steps",
            "steps": [
                {
                    "id": "matches",
                    "type": "select",
                    "target": "items",
                    "expect": "some",
                },
                {
                    "id": "selected",
                    "type": "add",
                    "target": "selections",
                    "value": {"item_id": "$steps.matches.0.id"},
                },
            ],
        }
        config["tools"][0]["result"] = "$action.selected"
        engine = DemoEngine(config)
        state = engine.create_state()

        _, result = engine.execute(state, "list_items", {})

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
                config = self._config()
                config["state"]["items"] = [{"id": "item_1"}]
                config["tools"][0]["result"] = reference
                engine = DemoEngine(config)
                state = engine.create_state()

                with self.assertRaisesRegex(ValueError, "Unknown reference"):
                    engine.execute(state, "list_items", {})

    def test_generated_id_can_be_used_by_a_later_step(self):
        config = self._config()
        config["state"] = {"items": [], "generated": []}
        config["tools"][0]["action"] = {
            "type": "steps",
            "steps": [
                {"id": "generated_id", "type": "generate_id"},
                {
                    "id": "saved",
                    "type": "add",
                    "target": "generated",
                    "value": {"id": "$steps.generated_id"},
                },
            ],
        }
        config["tools"][0]["result"] = "$action.saved"
        engine = DemoEngine(config)
        original = engine.create_state()

        state, result = engine.execute(original, "list_items", {})

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

    def test_failed_execution_does_not_mutate_input_state(self):
        config = self._config()
        config["state"] = {"items": [], "generated": []}
        config["tools"][0]["action"] = {
            "type": "steps",
            "steps": [
                {
                    "type": "add",
                    "target": "generated",
                    "value": {"id": "temporary"},
                },
                {
                    "type": "assert",
                    "target": "items",
                    "expect": "some",
                    "message": "No items",
                },
            ],
        }
        engine = DemoEngine(config)
        state = engine.create_state()

        with self.assertRaisesRegex(ValueError, "No items"):
            engine.execute(state, "list_items", {})

        self.assertEqual([], state["generated"])


if __name__ == "__main__":
    unittest.main()
