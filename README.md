# Demo Engine

Demo Engine turns a YAML definition into a small, stateful MCP server for local
demos, prototypes, workshops, and tests. The YAML defines the initial state,
JSON Schemas, tools, actions, and result mappings; the Python engine interprets
those definitions without containing domain-specific behavior.

Each server process owns one in-memory state value. Restarting the process
resets the demo. Demo Engine is intentionally not a hosted multi-user runtime.

## Quick start

Python 3.12 or newer and [uv](https://docs.astral.sh/uv/) are recommended.

```sh
uv sync
uv run python examples/run_commerce.py
uv run python examples/manual_stdio.py
```

Run the commerce MCP server directly:

```sh
uv run demo-mcp examples/commerce_demo.yaml
```

An MCP host can launch it with a configuration like this, replacing both paths:

```json
{
  "mcpServers": {
    "commerce-demo": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/demo-engine",
        "run",
        "demo-mcp",
        "/path/to/demo-engine/examples/commerce_demo.yaml"
      ]
    }
  }
}
```

## Python API

`DemoEngine` is stateless. Callers provide the current state and receive a new
state with the tool result:

```python
from demo_engine import DemoEngine

engine = DemoEngine.load("examples/commerce_demo.yaml")
state = engine.create_state()
state, result = engine.execute(state, "search_products", {"query": "linen"})
```

Execution uses a deep copy, so a failed call cannot mutate the caller's state.

## YAML format

A definition contains:

- `server`: MCP name, version, optional title, and cross-tool instructions.
- `state`: initial JSON-compatible application state.
- `state_schema`: JSON Schema Draft 2020-12 for the complete state.
- `collections`: optional identity fields for top-level list collections.
- `tools`: MCP metadata, schemas, an action, and a result mapping.

Supported actions are `select`, `assert`, `add`, `update`, `remove`,
`generate_id`, and ordered `steps`. Values may reference `$args`, `$state`,
`$steps`, or `$action` with dot paths and non-negative list indexes, such as
`$steps.matches.0.id`.

Selections support exact `where` matches, case-insensitive `contains` searches,
and `any`, `one`, `some`, or `none` cardinality expectations. State, inputs,
outputs, and configured collection identities are validated around execution.

See [examples/commerce_demo.yaml](examples/commerce_demo.yaml) for a complete
definition.

## Development

Run the tests and build distributions with:

```sh
uv run python -m unittest discover -s tests -v
uv build
```

The core interpreter deliberately owns no persistence, authentication, or
session management. A local MCP process provides isolation; any future shared
deployment should keep state ownership outside `DemoEngine`.

## License

MIT
