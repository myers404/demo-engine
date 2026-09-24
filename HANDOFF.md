# Demo Engine Handoff

Use this document to restore project context in a new chat. Inspect the current
code before making changes; this file records decisions and status, but the code
is authoritative.

## Purpose

Demo Engine is a small YAML-configured framework for creating stateful demo MCP
tools that resemble the tools used by enterprise conversational agents. Its
primary use case is local development, prototyping, workshops, CI, and isolated
demo processes—not a hosted multi-tenant application.

A YAML file defines:

- MCP server metadata and cross-tool instructions.
- Initial application state and its JSON Schema.
- Collection identity fields.
- MCP tool names, descriptions, annotations, input/output schemas, actions,
  and result mappings.

`commerce_demo.yaml` is the current example. It supports catalog search, adding
products to a cart, changing quantities, and checkout with a server-generated
order ID.

## Current architecture

### Configuration

`load_config(path)` loads YAML and validates:

- The initial state against `state_schema`.
- Input and optional output schemas as JSON Schema Draft 2020-12.
- Duplicate tool names.

An output schema is checked by presence, not truthiness, so `{}` and boolean
JSON Schemas behave correctly.

### Stateless interpreter

`DemoEngine` owns definitions but no runtime sessions or persistence:

```python
engine = DemoEngine(config)
state = engine.create_state()
state, result = engine.execute(state, tool_name, arguments)
```

Execution deep-copies the supplied state. A successful call returns the new
state and tool result. A failed call cannot mutate the caller's state.

Supported action primitives:

- `select`
- `assert`
- `add`
- `update`
- `remove`
- `steps`
- `generate_id` (returns a UUID string)

References use dot paths rooted at `$args`, `$state`, `$steps`, or `$action`.
They traverse dictionary keys and numeric list indexes, for example:

```yaml
product_id: "$steps.matches.0.id"
```

Negative list indexes are intentionally unsupported. Unknown roots, missing
keys, invalid indexes, and out-of-range indexes raise `ValueError`.

Collections may declare an identity field. Identity presence and uniqueness
are validated before and after execution.

### MCP runtime

`MCPDemoServer` exposes configured tools over MCP stdio. It owns one in-memory
state value for the lifetime of the isolated server process:

```python
self.state = self.engine.create_state()
self.state, result = self.engine.execute(self.state, name, arguments)
```

State is assigned only after successful execution. Tool results include both
text JSON and MCP `structuredContent`.

This is intentionally not a multi-user runtime. A local agent normally launches
one stdio server process, which naturally isolates its state. If shared hosting
is added later, state ownership belongs outside `DemoEngine`, either in a
per-demo process/container or a store keyed by an authenticated principal or
opaque demo-run ID.

## Design decisions

- Keep the interpreter generic; commerce is only an example configuration.
- Keep tool contracts self-contained and robust. Tool descriptions explain
  when to call a tool, parameters, side effects, and important failures.
- Put cross-tool workflow guidance in MCP server instructions.
- Put only generic agent behavior in the host's system prompt.
- Enforce correctness in schemas and execution, never only in prompts.
- Generate authoritative identifiers server-side; models must not invent them.
- Do not add a skill yet. A skill is optional host-specific packaging for richer
  procedures, not a requirement for correct tool use.
- Do not add `definition.py`; JSON Schema in YAML is sufficient for now.
- Do not add `StateStore`, authentication, Redis, tenancy, or locks until a
  shared HTTP deployment is a real requirement.
- Do not reconstruct MCP metadata inside `DemoEngine`; the MCP runtime already
  retains the complete configuration.
- Do not add YAML/S3 source abstractions until there is a second real source.
- Rich UI is the MCP host's responsibility. Tools return structured data and
  presentation hints; custom MCP Apps can be considered later.
- The previous bespoke eval runner and duplicated JSON scenarios were deleted.
  If evals return, they should exercise the real YAML + MCP + Interlock path,
  start with fresh state, and assert traces, state, and outcomes.

## Extraction status

The project was moved from the Interlock repository to:

```text
/Users/jakemyers/PycharmProjects/demo_engine
```

The moved files currently include the engine, MCP server, commerce YAML, demo
scripts, TODO, and a minimal `pyproject.toml`.

Before the move, the complete Interlock test suite passed: 77 tests.

Two relevant test modules still need to be moved from the Interlock repository:

```text
/Users/jakemyers/PycharmProjects/interlock/tests/test_demo_engine.py
/Users/jakemyers/PycharmProjects/interlock/tests/test_demo_mcp_server.py
```

The new `pyproject.toml` is incomplete. Runtime dependencies are currently:

```toml
dependencies = ["jsonschema>=4.23", "mcp>=1.0", "PyYAML>=6.0"]
```

The old repository also exposed this console script:

```toml
demo-mcp = "demo_engine.mcp_server:main"
```

The current flat repository/package layout may need adjustment before editable
installation or publication. Decide the package layout once, then update imports,
the console script, and tests together.

## Useful checks

From the original Interlock environment, these passed immediately before the
move:

```sh
.venv/bin/python -m unittest tests.test_demo_engine tests.test_demo_mcp_server tests.test_mcp_tools
.venv/bin/python -m demo_engine.demo_script
.venv/bin/python -m unittest discover -s tests
```

After extraction, restore equivalent commands in the new repository rather
than depending on Interlock's virtual environment.

## Next work

1. Choose and configure the installable package layout.
2. Add the runtime dependencies and `demo-mcp` console script to `pyproject.toml`.
3. Move the two demo-engine test modules and make them pass independently.
4. Add an OSS license, `.gitignore`, and README.
5. Document the YAML format and provide copy-paste MCP host configuration.
6. Improve configuration errors with useful YAML paths.
7. Add a deterministic state-reset command for demo runs.
8. Add non-commerce examples such as IT service management, CRM/support, and
   procurement.
9. Run the official MCP server conformance tests before release.

Avoid adding persistence or multi-user infrastructure during extraction. The
first milestone is an independently installable, tested local demo MCP server.

## Suggested prompt for a new chat

> Read `HANDOFF.md` and inspect the repository before changing anything. First,
> make the extracted project independently installable and restore its tests.
> Preserve the stateless `DemoEngine` API and the intentionally local,
> single-instance MCP runtime. Keep changes minimal and do not introduce a
> state-store abstraction or multi-user infrastructure.
