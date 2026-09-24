# Demo Engine

Demo Engine is a small YAML-driven framework for building stateful MCP tools. I
built it for demos, prototypes, workshops, and tests where writing a one-off
server is more work than the demo itself.

The YAML owns the state, schemas, tools, and behavior. The Python engine stays
generic and interprets that definition.

One process is one demo session. State lives in memory, and restarting the
process resets it. This is deliberately not a hosted, multi-user backend.

## Quick start

The project requires Python 3.12 or newer and uses
[uv](https://docs.astral.sh/uv/).

```sh
uv sync
uv run python examples/run_commerce.py
```

That runs the commerce example directly against the engine. To exercise the
same demo through a real MCP stdio connection:

```sh
uv run python examples/manual_stdio.py
```

You can also run the server yourself:

```sh
uv run demo-mcp examples/commerce_demo.yaml
```

For an MCP host, replace the two paths in this configuration:

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

`DemoEngine` does not own a live session. Give it a state value and it returns
the next state plus the tool result:

```python
from demo_engine import DemoEngine

engine = DemoEngine.load("examples/commerce_demo.yaml")
state = engine.create_state()
state, result = engine.execute(state, "search_products", {"query": "linen"})
```

Execution happens on a deep copy. If an action or validation fails, the state
you passed in is untouched.

## Demo files

A demo YAML file has five main parts:

- `server`: MCP name, version, title, and cross-tool instructions.
- `state`: the initial application state.
- `state_schema`: JSON Schema Draft 2020-12 for the full state.
- `collections`: optional identity fields for top-level lists.
- `tools`: MCP metadata, schemas, actions, and result mappings.

The engine supports `select`, `assert`, `add`, `update`, `remove`,
`generate_id`, and ordered `steps`.

Values can reference `$args`, `$state`, `$steps`, or `$action`. References use
dot paths and non-negative list indexes:

```yaml
product_id: $steps.matches.0.id
```

Selectors support exact `where` matches, case-insensitive `contains` searches,
and `any`, `one`, `some`, or `none` match expectations. Exact fields and
explicit search fields can also use nested paths:

```yaml
where:
  customer.id: $args.customer_id
contains:
  value: $args.query
  fields:
    - customer.name
    - contacts.0.email
```

A missing nested path behaves like a missing top-level field. A `contains`
search without `fields` still searches top-level values only.

State, tool inputs, tool outputs, and collection identities are validated
around every execution. See
[examples/commerce_demo.yaml](examples/commerce_demo.yaml) for a complete demo.

## Development

Run the full test suite from the repository root:

```sh
uv run python -m unittest discover -s tests -v
```

The engine intentionally has no persistence, authentication, tenancy, or
session abstraction. If shared hosting ever becomes a real requirement, state
ownership belongs outside `DemoEngine`.

## License

[MIT](LICENSE)
