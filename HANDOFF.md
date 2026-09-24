# Demo Engine Handoff

Use this document to restore development context. Inspect the current code
before making changes; the code is authoritative.

## Purpose

Demo Engine is a YAML-configured framework for stateful demo MCP tools. It is
intended for local development, prototypes, workshops, CI, and isolated demo
processes—not hosted multi-user operation.

The commerce example supports catalog search, cart changes, and checkout with
a server-generated order ID.

## Architecture

`DemoEngine` is a stateless interpreter:

```python
engine = DemoEngine(config)
state = engine.create_state()
state, result = engine.execute(state, tool_name, arguments)
```

Execution deep-copies state and validates schemas and collection identities
before and after configured actions. Supported actions are `select`, `assert`,
`add`, `update`, `remove`, `steps`, and `generate_id`. References are dot paths
rooted at `$args`, `$state`, `$steps`, or `$action`.

`MCPDemoServer` is the stateful transport adapter. One stdio server process owns
one in-memory state value and assigns a new value only after successful
execution. Tool results include text JSON and MCP structured content.

## Package layout

```text
src/demo_engine/       Installable interpreter and MCP server
examples/              Commerce YAML and executable examples
tests/                 Standard-library unittest suite
```

The distribution is `demo-engine`, the import package is `demo_engine`, and the
installed command is `demo-mcp`. Packaging uses setuptools with a `src` layout;
uv manages the development environment and lockfile.

## Design constraints

- Keep the interpreter domain-neutral; commerce is only an example.
- Keep `DemoEngine` stateless and persistence-free.
- Enforce invariants in schemas and execution, not only prompts.
- Generate authoritative identifiers server-side.
- Prefer JSON Schema in YAML over parallel Python model definitions.
- Do not add state stores, authentication, tenancy, locks, source abstractions,
  or hosted infrastructure until a real deployment requires them.
- Keep rich presentation in the MCP host.
- Future evals should exercise the real YAML, MCP, and agent path with fresh
  state instead of duplicating scenarios.

## Development

```sh
uv sync
uv run python -m unittest discover -s tests -v
uv run python examples/run_commerce.py
uv run python examples/manual_stdio.py
uv build
```

## Next work

1. Improve configuration errors with useful YAML paths.
2. Add a deterministic state-reset command.
3. Add IT service management, CRM/support, and procurement examples.
4. Run official MCP server conformance tests.
5. Add CI and publish an initial release when ready.
