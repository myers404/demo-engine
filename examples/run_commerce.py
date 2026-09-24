import json
from pathlib import Path
from uuid import UUID

from demo_engine import DemoEngine

engine = DemoEngine.load(Path(__file__).with_name("commerce_demo.yaml"))
primary = engine.create_state()
isolated = engine.create_state()

primary, search_result = engine.execute(
    primary,
    "search_products",
    {"query": "linen"},
)
products = search_result["products"]
assert [product["id"] for product in products] == ["prod_1"]

primary, _ = engine.execute(
    primary,
    "add_to_cart",
    {"product_id": "prod_1"},
)
try:
    engine.execute(
        primary,
        "add_to_cart",
        {"product_id": "prod_1"},
    )
except ValueError as error:
    assert str(error) == "Duplicate id: prod_1"
else:
    raise AssertionError("Duplicate cart item was accepted")

primary, _ = engine.execute(
    primary,
    "change_quantity",
    {"product_id": "prod_1", "quantity": 2},
)
primary, result = engine.execute(
    primary,
    "checkout",
    {"customer": "Jake"},
)

UUID(result["order"]["id"])
assert result["order"]["id"] == primary["orders"][0]["id"]
assert primary["cart"] == []
assert primary["orders"][0]["items"][0]["quantity"] == 2
assert isolated == engine.initial_state

print(json.dumps(result, indent=2))
print("All checks passed.")
