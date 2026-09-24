from copy import deepcopy
from uuid import uuid4

import yaml
from jsonschema import Draft202012Validator, validate


def load_config(path):
    with open(path) as config_file:
        config = yaml.safe_load(config_file)
    if not isinstance(config, dict):
        raise ValueError("Demo config must be an object")

    Draft202012Validator.check_schema(config["state_schema"])
    validate(config["state"], config["state_schema"])

    names = [tool["name"] for tool in config["tools"]]
    if len(names) != len(set(names)):
        raise ValueError("Duplicate tool name")

    for tool in config["tools"]:
        Draft202012Validator.check_schema(tool["input_schema"])
        if "output_schema" in tool:
            Draft202012Validator.check_schema(tool["output_schema"])

    return config


class DemoEngine:
    def __init__(self, config):
        self.initial_state = deepcopy(config["state"])
        self.state_schema = config["state_schema"]
        self.collection_identities = {
            name: settings["identity"]
            for name, settings in config.get("collections", {}).items()
        }
        self.tools = {tool["name"]: tool for tool in config["tools"]}

        validate(self.initial_state, self.state_schema)
        self._validate_identities(self.initial_state)
        if len(self.tools) != len(config["tools"]):
            raise ValueError("Duplicate tool name")

    @classmethod
    def load(cls, path):
        return cls(load_config(path))

    def create_state(self):
        return deepcopy(self.initial_state)

    def execute(self, current_state, tool_name, args):
        if tool_name not in self.tools:
            raise ValueError("Unknown tool")

        tool = self.tools[tool_name]
        validate(args, tool["input_schema"])
        validate(current_state, self.state_schema)
        self._validate_identities(current_state)

        state = deepcopy(current_state)
        action_result = self._run(tool["action"], state, args, {})
        validate(state, self.state_schema)
        self._validate_identities(state)
        result = self._resolve(
            tool["result"],
            state,
            args,
            {},
            action_result,
        )
        if "output_schema" in tool:
            validate(result, tool["output_schema"])
        return state, result

    def _collection(self, state, target):
        if target not in state or not isinstance(state[target], list):
            raise ValueError(f"Unknown collection: {target}")
        return state[target]

    def _validate_identities(self, state):
        for target, identity in self.collection_identities.items():
            seen = set()
            for item in self._collection(state, target):
                if identity not in item:
                    raise ValueError(f"Missing identity {identity!r} in {target}")
                value = item[identity]
                if value in seen:
                    raise ValueError(f"Duplicate {identity}: {value}")
                seen.add(value)

    def _resolve(self, value, state, args, steps, action=None):
        if isinstance(value, str) and value.startswith("$"):
            root, *path = value[1:].split(".")
            roots = {
                "action": action,
                "args": args,
                "state": state,
                "steps": steps,
            }
            if root not in roots:
                raise ValueError(f"Unknown reference: {value}")

            current = roots[root]
            for part in path:
                if isinstance(current, list):
                    if not part.isdecimal() or int(part) >= len(current):
                        raise ValueError(f"Unknown reference: {value}")
                    current = current[int(part)]
                elif isinstance(current, dict) and part in current:
                    current = current[part]
                else:
                    raise ValueError(f"Unknown reference: {value}")
            return deepcopy(current)
        if isinstance(value, dict):
            return {
                key: self._resolve(item, state, args, steps, action)
                for key, item in value.items()
            }
        if isinstance(value, list):
            return [
                self._resolve(item, state, args, steps, action)
                for item in value
            ]
        return deepcopy(value)

    def _select(self, selector, state, args, steps, default_expect="any"):
        collection = self._collection(state, selector["target"])
        where = self._resolve(selector.get("where", {}), state, args, steps)
        matches = [
            item
            for item in collection
            if all(item.get(key) == value for key, value in where.items())
        ]

        if contains := selector.get("contains"):
            query = str(
                self._resolve(contains["value"], state, args, steps),
            ).casefold()
            fields = contains.get("fields")
            matches = [
                item
                for item in matches
                if any(
                    query in str(value).casefold()
                    for value in (
                        (item.get(field, "") for field in fields)
                        if fields
                        else item.values()
                    )
                )
            ]

        expect = selector.get("expect", default_expect)
        if expect == "one" and len(matches) != 1:
            raise ValueError(f"Expected one match, found {len(matches)}")
        if expect == "some" and not matches:
            raise ValueError(selector.get("message", "Expected at least one match"))
        if expect == "none" and matches:
            raise ValueError(f"Expected no matches, found {len(matches)}")
        if expect not in {"any", "one", "some", "none"}:
            raise ValueError(f"Unknown expectation: {expect}")

        return matches

    def _run(self, action, state, args, steps):
        action_type = action["type"]

        if action_type == "steps":
            results = {}
            for index, step in enumerate(action["steps"]):
                result = self._run(step, state, args, results)
                results[step.get("id", str(index))] = result
            return results

        if action_type == "select":
            return deepcopy(self._select(action, state, args, steps))

        if action_type == "assert":
            return deepcopy(
                self._select(action, state, args, steps, "some"),
            )

        if action_type == "generate_id":
            return str(uuid4())

        target = action["target"]
        collection = self._collection(state, target)

        if action_type == "add":
            item = {}
            if source := action.get("source"):
                item.update(
                    deepcopy(
                        self._select(source, state, args, steps, "one")[0],
                    ),
                )

            item.update(
                self._resolve(action.get("value", {}), state, args, steps),
            )
            collection.append(item)
            return deepcopy(item)

        if action_type == "update":
            item = self._select(action, state, args, steps, "one")[0]
            item.update(
                self._resolve(action["changes"], state, args, steps),
            )
            return deepcopy(item)

        if action_type == "remove":
            matches = self._select(action, state, args, steps, "one")
            for item in matches:
                collection.remove(item)
            return deepcopy(matches)

        raise ValueError(f"Unknown action type: {action_type}")
