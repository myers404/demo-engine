import argparse
import asyncio
import json

import mcp.types as types
from jsonschema import ValidationError
from mcp.server import Server
from mcp.server.stdio import stdio_server

from .engine import DemoEngine, load_config


class MCPDemoServer:
    def __init__(self, config):
        self.config = config
        self.engine = DemoEngine(config)
        self.state = self.engine.create_state()

        metadata = config["server"]
        self.server = Server(
            metadata["name"],
            version=metadata["version"],
            title=metadata.get("title"),
            instructions=metadata.get("instructions"),
            on_list_tools=self._list_tools,
            on_call_tool=self._call_tool,
        )

    async def _list_tools(self, _context, _params):
        return types.ListToolsResult(
            tools=[
                types.Tool(
                    name=tool["name"],
                    title=tool.get("title"),
                    description=tool["description"],
                    inputSchema=tool["input_schema"],
                    outputSchema=tool.get("output_schema"),
                    annotations=tool.get("annotations"),
                )
                for tool in self.config["tools"]
            ],
        )

    async def _call_tool(self, _context, params):
        try:
            state, result = self.engine.execute(
                self.state,
                params.name,
                params.arguments or {},
            )
            self.state = state
        except (KeyError, ValidationError, ValueError) as error:
            return types.CallToolResult(
                content=[types.TextContent(type="text", text=str(error))],
                isError=True,
            )

        return types.CallToolResult(
            content=[
                types.TextContent(
                    type="text",
                    text=json.dumps(result, indent=2),
                ),
            ],
            structuredContent=result,
        )

    async def run_stdio(self):
        async with stdio_server() as (read_stream, write_stream):
            await self.server.run(
                read_stream,
                write_stream,
                self.server.create_initialization_options(),
            )


def main():
    parser = argparse.ArgumentParser(
        description="Run a YAML-configured demo MCP server",
    )
    parser.add_argument("config", help="Path to the demo YAML file")
    args = parser.parse_args()

    config = load_config(args.config)
    asyncio.run(MCPDemoServer(config).run_stdio())


if __name__ == "__main__":
    main()
