# Catalog tools

This module exposes ReAct-ready tools backed by `src/database/banggia.xlsx`.
All catalog code is intentionally kept in one file: `src/tools/catalog_tools.py`.

## Tool list

- `search_products`: search by product name, category, shop, or description.
- `get_product_price`: get the cheapest matching offer for one product.
- `compare_products`: compare products by price, rating, discount, or delivery.
- `calculate_cart_total`: calculate VND total for cart items.

## Agent usage

```python
from src.tools.catalog_tools import build_catalog_tools

tools = build_catalog_tools()
result_json = tools[0]["func"](query="ban phim khong day", max_results=3)
```

Each tool dictionary contains:

```python
{
    "name": "...",
    "description": "...",
    "parameters": {...},
    "func": callable_returning_json_string,
}
```

## Direct usage

```python
from src.tools.catalog_tools import CatalogTools, ExcelCatalogRepository

repository = ExcelCatalogRepository()
catalog_tools = CatalogTools(repository)

catalog_tools.search_products(query="mouse", max_results=2)
catalog_tools.get_product_price(product_name="Logitech G304")
catalog_tools.calculate_cart_total(
    items=[{"product_name": "Logitech K120", "quantity": 2}]
)
```
