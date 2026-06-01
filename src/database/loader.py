"""Load price catalog from src/database for chatbot context."""
from pathlib import Path

import pandas as pd

DATABASE_DIR = Path(__file__).resolve().parent
DEFAULT_CATALOG = DATABASE_DIR / "banggia.xlsx"

_catalog_cache: str | None = None


def load_price_catalog(path: Path | None = None) -> str:
    global _catalog_cache
    if _catalog_cache is not None and path is None:
        return _catalog_cache

    catalog_path = path or DEFAULT_CATALOG
    if not catalog_path.exists():
        raise FileNotFoundError(f"Price catalog not found: {catalog_path}")

    df = pd.read_excel(catalog_path)
    lines: list[str] = []
    for _, row in df.iterrows():
        lines.append(
            f"- {row['product_name']} ({row['category']}) | "
            f"shop: {row['shop_name']} | "
            f"giá: {int(row['price']):,} VND | "
            f"sau giảm: {int(row['price_after_discount']):,} VND "
            f"({int(row['discount_percent'])}%) | "
            f"rating: {row['rating']} | "
            f"giao tối đa {int(row['max_delivery_days'])} ngày | "
            f"{row['description']}"
        )

    text = "\n".join(lines)
    if path is None:
        _catalog_cache = text
    return text


def build_system_prompt() -> str:
    catalog = load_price_catalog()
    return (
        "Chatbot hỗ trợ truy xuất giá.\n"
        "Trả lời bằng tiếng Việt, chỉ dựa trên bảng giá bên dưới. "
        "Không bịa thông tin không có trong dữ liệu.\n\n"
        f"Bảng giá:\n{catalog}"
    )
