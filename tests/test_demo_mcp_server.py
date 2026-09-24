import unittest
from pathlib import Path
from uuid import UUID

from mcp import Client

from demo_engine import load_config
from demo_engine.mcp_server import MCPDemoServer


class MCPDemoServerTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        config = Path(__file__).parents[1] / "demo_engine" / "commerce_demo.yaml"
        self.demo = MCPDemoServer(load_config(config))

    async def test_lists_and_executes_yaml_tools(self):
        async with Client(self.demo.server, raise_exceptions=True) as client:
            listed = await client.list_tools()
            self.assertEqual(
                [
                    "search_products",
                    "add_to_cart",
                    "change_quantity",
                    "checkout",
                ],
                [tool.name for tool in listed.tools],
            )

            search = await client.call_tool("search_products", {"query": "linen"})
            self.assertFalse(search.is_error)
            self.assertEqual("prod_1", search.structured_content["products"][0]["id"])

            await client.call_tool("add_to_cart", {"product_id": "prod_1"})
            duplicate = await client.call_tool(
                "add_to_cart",
                {"product_id": "prod_1"},
            )
            self.assertTrue(duplicate.is_error, duplicate)

            await client.call_tool(
                "change_quantity",
                {"product_id": "prod_1", "quantity": 2},
            )
            checkout = await client.call_tool(
                "checkout",
                {"customer": "Jake"},
            )
            order = checkout.structured_content["order"]
            saved_order = self.demo.state["orders"][0]
            UUID(order["id"])
            self.assertEqual(order["id"], saved_order["id"])
            self.assertEqual(
                2,
                order["items"][0]["quantity"],
            )

    async def test_server_instances_have_isolated_state(self):
        async with Client(self.demo.server, raise_exceptions=True) as first:
            await first.call_tool("add_to_cart", {"product_id": "prod_1"})

        config = Path(__file__).parents[1] / "demo_engine" / "commerce_demo.yaml"
        fresh_demo = MCPDemoServer(load_config(config))
        async with Client(fresh_demo.server, raise_exceptions=True) as second:
            checkout = await second.call_tool(
                "checkout",
                {"customer": "Jake"},
            )
            self.assertTrue(checkout.is_error)
            self.assertEqual("Cart is empty", checkout.content[0].text)


if __name__ == "__main__":
    unittest.main()
