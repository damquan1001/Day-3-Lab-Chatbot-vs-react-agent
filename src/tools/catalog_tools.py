from __future__ import annotations

import json
import re
import unicodedata
import zipfile
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from typing import Any
from xml.etree import ElementTree


DEFAULT_CATALOG_PATH = Path(__file__).resolve().parents[1] / "database" / "banggia.xlsx"

_SPREADSHEET_NS = {"xlsx": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_CELL_REF_PATTERN = re.compile(r"([A-Z]+)")

__all__ = [
    "CatalogTools",
    "ExcelCatalogRepository",
    "ProductOffer",
    "build_catalog_tools",
]


@dataclass(frozen=True)
class ProductOffer:
    """
    One offer row from banggia.xlsx.

    Prices are integer VND values to avoid floating-point money math.
    """

    category: str
    product_name: str
    shop_name: str
    price: int
    discount_percent: float
    price_after_discount: int
    rating: float
    max_delivery_days: int
    description: str

    @classmethod
    def from_row(cls, row: Mapping[str, Any]) -> "ProductOffer":
        return cls(
            category=str(row["category"]).strip(),
            product_name=str(row["product_name"]).strip(),
            shop_name=str(row["shop_name"]).strip(),
            price=_to_int(row["price"], field_name="price"),
            discount_percent=_to_float(
                row["discount_percent"], field_name="discount_percent"
            ),
            price_after_discount=_to_int(
                row["price_after_discount"], field_name="price_after_discount"
            ),
            rating=_to_float(row["rating"], field_name="rating"),
            max_delivery_days=_to_int(
                row["max_delivery_days"], field_name="max_delivery_days"
            ),
            description=str(row["description"]).strip(),
        )

    @property
    def discount_amount(self) -> int:
        return self.price - self.price_after_discount

    def to_dict(self) -> dict[str, Any]:
        return {
            "category": self.category,
            "product_name": self.product_name,
            "shop_name": self.shop_name,
            "price": self.price,
            "discount_percent": self.discount_percent,
            "discount_amount": self.discount_amount,
            "price_after_discount": self.price_after_discount,
            "rating": self.rating,
            "max_delivery_days": self.max_delivery_days,
            "description": self.description,
        }


class ExcelCatalogRepository:
    """
    Reads product offers from src/database/banggia.xlsx.

    This repository uses only Python standard library modules, so teammates do
    not need to install pandas or openpyxl just to call the tools.
    """

    def __init__(self, file_path: str | Path = DEFAULT_CATALOG_PATH):
        self.file_path = Path(file_path)
        self._offers_cache: list[ProductOffer] | None = None

    def list_offers(self) -> list[ProductOffer]:
        if self._offers_cache is None:
            self._offers_cache = self._load_offers()
        return list(self._offers_cache)

    def search(
        self,
        query: str = "",
        category: str | None = None,
        max_results: int = 10,
    ) -> list[ProductOffer]:
        return _search_offers(
            self.list_offers(),
            query=query,
            category=category,
            max_results=max_results,
        )

    def find_product(
        self,
        product_name: str,
        shop_name: str | None = None,
    ) -> list[ProductOffer]:
        product_name = product_name.strip()
        if not product_name:
            return []

        matches = self.search(query=product_name, max_results=50)
        exact_matches = [
            offer
            for offer in matches
            if normalize_text(offer.product_name) == normalize_text(product_name)
        ]
        if exact_matches:
            matches = exact_matches

        if shop_name:
            normalized_shop_name = normalize_text(shop_name)
            matches = [
                offer
                for offer in matches
                if normalize_text(offer.shop_name) == normalized_shop_name
            ]

        return sorted(
            matches,
            key=lambda offer: (
                offer.price_after_discount,
                -offer.rating,
                offer.max_delivery_days,
            ),
        )

    def _load_offers(self) -> list[ProductOffer]:
        if not self.file_path.exists():
            raise FileNotFoundError(f"Catalog file not found: {self.file_path}")

        rows = _read_first_worksheet(self.file_path)
        if not rows:
            return []

        headers = [_normalize_header(value) for value in rows[0]]
        _validate_headers(headers)

        offers: list[ProductOffer] = []
        for index, row in enumerate(rows[1:], start=2):
            if not any(value not in (None, "") for value in row):
                continue

            record = {
                header: row[position] if position < len(row) else ""
                for position, header in enumerate(headers)
            }
            try:
                offers.append(ProductOffer.from_row(record))
            except ValueError as exc:
                raise ValueError(f"Invalid catalog row {index}: {exc}") from exc

        return offers


class CatalogTools:
    """
    Tool facade for the ReAct agent.

    Methods return dictionaries for direct Python usage. as_agent_tools() returns
    tool dictionaries whose func callables return JSON strings for Observation.
    """

    def __init__(self, repository: ExcelCatalogRepository | None = None):
        self.repository = repository or ExcelCatalogRepository()

    def search_products(
        self,
        query: str = "",
        category: str | None = None,
        max_results: int = 20,
    ) -> dict[str, Any]:
        max_results = _bounded_max_results(max_results)
        offers = self.repository.search(
            query=query,
            category=category,
            max_results=max_results,
        )
        return {
            "query": query,
            "category": category,
            "count": len(offers),
            "products": [_offer_to_tool_dict(offer) for offer in offers],
        }

    def get_product_price(
        self,
        product_name: str,
        shop_name: str | None = None,
    ) -> dict[str, Any]:
        product_name = product_name.strip()
        if not product_name:
            return {
                "product_name": product_name,
                "shop_name": shop_name,
                "found": False,
                "best_offer": None,
                "offers": [],
                "error": "product_name is required",
            }

        offers = self.repository.find_product(
            product_name=product_name,
            shop_name=shop_name,
        )
        best_offer = offers[0] if offers else None
        return {
            "product_name": product_name,
            "shop_name": shop_name,
            "found": bool(best_offer),
            "best_offer": _offer_to_tool_dict(best_offer) if best_offer else None,
            "offers": [_offer_to_tool_dict(offer) for offer in offers[:10]],
        }

    def compare_products(
        self,
        query: str = "",
        category: str | None = None,
        sort_by: str = "price_after_discount",
        max_results: int = 20,
    ) -> dict[str, Any]:
        max_results = _bounded_max_results(max_results)
        offers = self.repository.search(
            query=query,
            category=category,
            max_results=50,
        )
        sorted_offers = _sort_offers(offers, sort_by=sort_by)[:max_results]
        return {
            "query": query,
            "category": category,
            "sort_by": sort_by,
            "count": len(sorted_offers),
            "products": [_offer_to_tool_dict(offer) for offer in sorted_offers],
        }

    def calculate_cart_total(
        self,
        items: Sequence[Mapping[str, Any]] | Mapping[str, Any] | str | None,
    ) -> dict[str, Any]:
        items = _normalize_items(items)
        if not items:
            return {
                "currency": "VND",
                "total": 0,
                "lines": [],
                "errors": [
                    {
                        "error": (
                            "items must be a non-empty list of objects with "
                            "product_name and quantity"
                        )
                    }
                ],
                "success": False,
            }

        lines: list[dict[str, Any]] = []
        errors: list[dict[str, Any]] = []
        total = 0

        for index, item in enumerate(items, start=1):
            product_name = str(item.get("product_name", "")).strip()
            shop_name = _optional_str(item.get("shop_name"))
            quantity = _safe_quantity(item.get("quantity", 1))

            if not product_name:
                errors.append({"line": index, "error": "product_name is required"})
                continue
            if quantity <= 0:
                errors.append(
                    {
                        "line": index,
                        "product_name": product_name,
                        "error": "quantity must be greater than 0",
                    }
                )
                continue

            offers = self.repository.find_product(product_name, shop_name=shop_name)
            if not offers:
                errors.append(
                    {
                        "line": index,
                        "product_name": product_name,
                        "shop_name": shop_name,
                        "error": "product not found",
                    }
                )
                continue

            selected_offer = offers[0]
            line_total = selected_offer.price_after_discount * quantity
            total += line_total
            lines.append(
                {
                    "line": index,
                    "product_name": selected_offer.product_name,
                    "shop_name": selected_offer.shop_name,
                    "quantity": quantity,
                    "unit_price": selected_offer.price_after_discount,
                    "line_total": line_total,
                    "rating": selected_offer.rating,
                    "max_delivery_days": selected_offer.max_delivery_days,
                }
            )

        return {
            "currency": "VND",
            "total": total,
            "lines": lines,
            "errors": errors,
            "success": not errors,
        }

    def as_agent_tools(self) -> list[dict[str, Any]]:
        return [
            {
                "name": "search_products",
                "description": (
                    "Search products in banggia.xlsx by product name, description, "
                    "shop, or category. Args: query string, optional category, "
                    "optional max_results."
                ),
                "parameters": {
                    "query": "string",
                    "category": "optional string",
                    "max_results": "optional integer, default 20, max 50",
                },
                "func": lambda **kwargs: _to_json(self.search_products(**kwargs)),
            },
            {
                "name": "get_product_price",
                "description": (
                    "Get price details for one product. Args: product_name string, "
                    "optional shop_name. Returns the cheapest matching offer first."
                ),
                "parameters": {
                    "product_name": "string",
                    "shop_name": "optional string",
                },
                "func": lambda **kwargs: _to_json(self.get_product_price(**kwargs)),
            },
            {
                "name": "compare_products",
                "description": (
                    "Compare matching products by price_after_discount, rating, "
                    "discount_percent, or max_delivery_days. Args: query string, "
                    "optional category, optional sort_by, optional max_results."
                ),
                "parameters": {
                    "query": "string",
                    "category": "optional string",
                    "sort_by": (
                        "optional string: price_after_discount, rating, "
                        "discount_percent, max_delivery_days"
                    ),
                    "max_results": "optional integer, default 20, max 50",
                },
                "func": lambda **kwargs: _to_json(self.compare_products(**kwargs)),
            },
            {
                "name": "calculate_cart_total",
                "description": (
                    "Calculate total VND for cart items. Args: items list of objects "
                    "with product_name, quantity, and optional shop_name. Uses the "
                    "cheapest matching offer when shop_name is not provided."
                ),
                "parameters": {
                    "items": (
                        "list of {product_name: string, quantity: integer, "
                        "shop_name?: string}"
                    )
                },
                "func": lambda **kwargs: _to_json(self.calculate_cart_total(**kwargs)),
            },
        ]


def build_catalog_tools(
    repository: ExcelCatalogRepository | None = None,
) -> list[dict[str, Any]]:
    return CatalogTools(repository).as_agent_tools()


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFD", value or "")
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    return " ".join(without_accents.lower().split())


def _search_offers(
    offers: Sequence[ProductOffer],
    query: str = "",
    category: str | None = None,
    max_results: int = 10,
) -> list[ProductOffer]:
    normalized_query = normalize_text(query)
    normalized_category = normalize_text(category or "")
    terms = normalized_query.split()

    scored: list[tuple[int, ProductOffer]] = []
    for offer in offers:
        if normalized_category and normalized_category not in normalize_text(
            offer.category
        ):
            continue

        score, matched_terms = _score_offer(offer, normalized_query, terms)
        minimum_matches = max(1, ceil(len(terms) * 0.6)) if terms else 0
        if terms and matched_terms < minimum_matches:
            continue
        if normalized_query and score <= 0:
            continue

        scored.append((score, offer))

    scored.sort(
        key=lambda item: (
            -item[0],
            item[1].price_after_discount,
            -item[1].rating,
            item[1].max_delivery_days,
            normalize_text(item[1].product_name),
        )
    )
    return [offer for _, offer in scored[: max(0, max_results)]]


def _score_offer(
    offer: ProductOffer,
    normalized_query: str,
    terms: list[str],
) -> tuple[int, int]:
    if not normalized_query:
        return 1, 0

    product_name = normalize_text(offer.product_name)
    category = normalize_text(offer.category)
    shop_name = normalize_text(offer.shop_name)
    description = normalize_text(offer.description)
    searchable_text = f"{category} {product_name} {shop_name} {description}"

    score = 0
    matched_terms = 0
    if normalized_query in product_name:
        score += 100
    if normalized_query in category:
        score += 70
    if normalized_query in description:
        score += 45
    if normalized_query in shop_name:
        score += 30

    for term in terms:
        if term in product_name:
            score += 15
            matched_terms += 1
        elif term in category:
            score += 10
            matched_terms += 1
        elif term in description:
            score += 6
            matched_terms += 1
        elif term in shop_name:
            score += 4
            matched_terms += 1
        elif term in searchable_text:
            score += 1
            matched_terms += 1

    return score, matched_terms


def _read_first_worksheet(file_path: Path) -> list[list[Any]]:
    with zipfile.ZipFile(file_path) as archive:
        shared_strings = _read_shared_strings(archive)
        worksheet_names = [
            name
            for name in archive.namelist()
            if name.startswith("xl/worksheets/sheet") and name.endswith(".xml")
        ]
        if not worksheet_names:
            raise ValueError(f"No worksheet found in catalog file: {file_path}")

        worksheet_names.sort()
        root = ElementTree.fromstring(archive.read(worksheet_names[0]))

    rows: list[list[Any]] = []
    for row_node in root.findall(".//xlsx:sheetData/xlsx:row", _SPREADSHEET_NS):
        row_values: list[Any] = []
        for cell_node in row_node.findall("xlsx:c", _SPREADSHEET_NS):
            column_index = _column_index(cell_node.attrib.get("r", ""))
            while len(row_values) <= column_index:
                row_values.append(None)
            row_values[column_index] = _cell_value(cell_node, shared_strings)
        rows.append(row_values)
    return rows


def _read_shared_strings(archive: zipfile.ZipFile) -> list[str]:
    if "xl/sharedStrings.xml" not in archive.namelist():
        return []

    root = ElementTree.fromstring(archive.read("xl/sharedStrings.xml"))
    strings: list[str] = []
    for item in root.findall(".//xlsx:si", _SPREADSHEET_NS):
        strings.append(
            "".join(
                text_node.text or ""
                for text_node in item.findall(".//xlsx:t", _SPREADSHEET_NS)
            )
        )
    return strings


def _cell_value(cell_node: ElementTree.Element, shared_strings: list[str]) -> Any:
    cell_type = cell_node.attrib.get("t")
    if cell_type == "inlineStr":
        return "".join(
            text_node.text or ""
            for text_node in cell_node.findall(".//xlsx:t", _SPREADSHEET_NS)
        )

    value_node = cell_node.find("xlsx:v", _SPREADSHEET_NS)
    if value_node is None:
        return ""

    raw_value = value_node.text or ""
    if cell_type == "s":
        return shared_strings[int(raw_value)]
    if cell_type == "b":
        return raw_value == "1"
    return raw_value


def _column_index(cell_ref: str) -> int:
    match = _CELL_REF_PATTERN.match(cell_ref)
    if not match:
        return 0

    index = 0
    for char in match.group(1):
        index = index * 26 + ord(char) - ord("A") + 1
    return index - 1


def _validate_headers(headers: list[str]) -> None:
    required_headers = {
        "category",
        "product_name",
        "shop_name",
        "price",
        "discount_percent",
        "price_after_discount",
        "rating",
        "max_delivery_days",
        "description",
    }
    missing_headers = required_headers.difference(headers)
    if missing_headers:
        missing = ", ".join(sorted(missing_headers))
        raise ValueError(f"Catalog file is missing required columns: {missing}")


def _normalize_header(value: Any) -> str:
    return str(value or "").strip().lower()


def _offer_to_tool_dict(offer: ProductOffer) -> dict[str, Any]:
    data = offer.to_dict()
    data["currency"] = "VND"
    return data


def _sort_offers(offers: Sequence[ProductOffer], sort_by: str) -> list[ProductOffer]:
    sort_keys: dict[str, Callable[[ProductOffer], Any]] = {
        "price_after_discount": lambda offer: (
            offer.price_after_discount,
            -offer.rating,
            offer.max_delivery_days,
        ),
        "rating": lambda offer: (
            -offer.rating,
            offer.price_after_discount,
            offer.max_delivery_days,
        ),
        "discount_percent": lambda offer: (
            -offer.discount_percent,
            offer.price_after_discount,
            -offer.rating,
        ),
        "max_delivery_days": lambda offer: (
            offer.max_delivery_days,
            offer.price_after_discount,
            -offer.rating,
        ),
    }
    return sorted(offers, key=sort_keys.get(sort_by, sort_keys["price_after_discount"]))


def _bounded_max_results(value: int) -> int:
    try:
        parsed = int(value)
    except (TypeError, ValueError):
        parsed = 20
    return max(1, min(parsed, 50))


def _safe_quantity(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 0


def _optional_str(value: Any) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    return text or None


def _normalize_items(
    items: Sequence[Mapping[str, Any]] | Mapping[str, Any] | str | None,
) -> list[Mapping[str, Any]]:
    if items is None:
        return []

    if isinstance(items, str):
        try:
            parsed = json.loads(items)
        except json.JSONDecodeError:
            return []
        if isinstance(parsed, Mapping):
            return [parsed]
        if isinstance(parsed, list):
            return [item for item in parsed if isinstance(item, Mapping)]
        return []

    if isinstance(items, Mapping):
        return [items]

    try:
        return [item for item in items if isinstance(item, Mapping)]
    except TypeError:
        return []


def _to_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, ensure_ascii=False)


def _to_int(value: Any, field_name: str) -> int:
    try:
        return int(float(value))
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid integer value for {field_name}: {value!r}") from exc


def _to_float(value: Any, field_name: str) -> float:
    try:
        return float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"Invalid float value for {field_name}: {value!r}") from exc
