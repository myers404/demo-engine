"""Smoke-test the YAML demo through a real MCP stdio connection."""

import asyncio
import json
import sys
from pathlib import Path

from mcp import Client, StdioServerParameters


async def main():
    root = Path(__file__).parents[1]
    config = Path(__file__).with_name("commerce_demo.yaml")
    server = StdioServerParameters(
        command=sys.executable,
        args=["-m", "demo_engine.mcp_server", str(config)],
        cwd=root,
    )

    async with Client(server) as client:
        listed = await client.list_tools()
        print("Tools:", ", ".join(tool.name for tool in listed.tools))

        await call(client, "search_products", {"query": "linen"})
        await call(client, "add_to_cart", {"product_id": "prod_1"})
        await call(
            client,
            "change_quantity",
            {"product_id": "prod_1", "quantity": 2},
        )
        await call(
            client,
            "checkout",
            {"customer": "Manual Test"},
        )


async def call(client, name, arguments):
    result = await client.call_tool(name, arguments)
    if result.is_error:
        raise RuntimeError(result.content[0].text)
    print(f"\n{name}:")
    print(json.dumps(result.structured_content, indent=2))
    return result.structured_content


if __name__ == "__main__":
    asyncio.run(main())
