import json
import re
from typing import Any, Dict, Iterable, List, Mapping, Optional

from src.core.llm_provider import LLMProvider
from src.telemetry.logger import logger


SHOP_KEYS = ("shop_name", "shop", "seller", "ten_shop", "tên shop")
PRODUCT_KEYS = ("product_name", "product", "name", "ten_san_pham", "tên sản phẩm")
PRICE_KEYS = ("price", "gia", "giá")
SALE_PRICE_KEYS = ("price_after_discount", "sale_price", "gia_kem_sales", "giá kèm sales")
FINAL_PRICE_KEYS = ("final_price", "final_payment", "total_price", "gia_cuoi", "giá cuối")
RATING_KEYS = ("rating", "rate", "stars", "sao")
DELIVERY_KEYS = ("max_delivery_days", "delivery_days", "ship_days", "max_ship_days")
DESCRIPTION_KEYS = ("description", "desc", "mo_ta", "mô tả")


def analyze_products(
    calculated_data: Iterable[Mapping[str, Any]],
    llm: LLMProvider,
    user_query: str = "",
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    Part 3: semantic product analysis.

    This function intentionally does not rank products with a fixed score formula.
    Node 1 and Node 2 already filtered/calculated the hard facts; here the LLM acts
    as the judge that weighs price, rating, delivery, and description nuance.
    """
    products = normalize_products(calculated_data, limit=top_n)
    if not products:
        return {
            "selected_shop": "",
            "product_name": "",
            "final_price": "",
            "reasoning": "Không có sản phẩm đủ dữ liệu để phân tích.",
            "warnings": ["calculated_data trống hoặc thiếu giá/rating cơ bản"],
            "llm_used": False,
        }

    prompt = build_llm_prompt(products, user_query=user_query)
    system_prompt = get_analysis_system_prompt()

    try:
        response = llm.generate(prompt, system_prompt=system_prompt)
        content = str(response.get("content", "")).strip()
        parsed = parse_llm_json(content)
        result = validate_analysis(parsed, products)
        result["llm_used"] = True
        result["llm_metadata"] = {
            "provider": response.get("provider"),
            "usage": response.get("usage", {}),
            "latency_ms": response.get("latency_ms"),
        }
        _track_llm_request(llm, response)
        logger.log_event(
            "PRODUCT_ANALYSIS_DONE",
            {
                "products": len(products),
                "selected_shop": result.get("selected_shop"),
                "llm_used": True,
            },
        )
        return result
    except Exception as exc:
        logger.error(f"PRODUCT_ANALYSIS_LLM_FAILED: {exc}")
        return {
            "selected_shop": "",
            "product_name": "",
            "final_price": "",
            "reasoning": "LLM chưa trả về được JSON hợp lệ nên chưa thể chốt sản phẩm.",
            "warnings": [str(exc)],
            "llm_used": False,
            "candidates": products,
        }


def analyze_descriptions_and_compare(
    calculated_data: Iterable[Mapping[str, Any]],
    llm: LLMProvider,
    user_query: str = "",
    top_n: int = 10,
) -> Dict[str, Any]:
    """
    ReAct-friendly tool name for Node 3.

    A LangGraph node can bind this function as the action behind
    `analyze_descriptions_and_compare`.
    """
    return analyze_products(calculated_data, llm, user_query=user_query, top_n=top_n)


def compare_products(
    calculated_data: Iterable[Mapping[str, Any]],
    llm: Optional[LLMProvider] = None,
    user_query: str = "",
    top_n: int = 10,
) -> Any:
    """
    Backward-compatible comparison entrypoint.

    If an LLM is provided, comparison is semantic and handled by the model.
    Without an LLM, this only normalizes candidates in their existing order.
    """
    if llm is None:
        return normalize_products(calculated_data, limit=top_n)
    return analyze_products(calculated_data, llm, user_query=user_query, top_n=top_n)


def normalize_product_row(row: Mapping[str, Any], index: int = 0) -> Dict[str, Any]:
    products = normalize_products([row], limit=1)
    if not products:
        return {
            "candidate_id": index + 1,
            "shop_name": "",
            "product_name": "",
            "price": "",
            "price_after_discount": "",
            "final_price": "",
            "rating": "",
            "max_delivery_days": "",
            "description": "",
        }
    products[0]["candidate_id"] = index + 1
    return products[0]


def react_analysis_node(state: Mapping[str, Any], llm: LLMProvider) -> Dict[str, Any]:
    """
    Drop-in Node 3 for a LangGraph StateGraph.

    Expected state keys:
    - query
    - calculated_data

    Returns only the state delta for Node 4/UI to consume.
    """
    analysis = analyze_products(
        state.get("calculated_data", []),
        llm,
        user_query=str(state.get("query", "")),
    )
    return {"final_analysis": analysis}


def get_analysis_system_prompt() -> str:
    return """
Bạn là một Chuyên gia Phân tích Thương mại điện tử Cấp cao.
Nhiệm vụ của bạn là chọn đúng 1 sản phẩm đáng mua nhất từ danh sách đã được lọc và tính giá cuối.

Nguyên tắc bắt buộc:
- Chỉ dùng dữ liệu trong calculated_data, không bịa thêm thông tin ngoài DB.
- Không dùng công thức điểm cứng. Hãy cân nhắc trade-off bằng ngữ nghĩa: giá cuối, rating, tốc độ giao, và description.
- Đọc kỹ description để phát hiện red flags như: không bảo hành, hàng cũ, no-box, xách tay, giao chậm, lỗi nhẹ, đổi trả kém.
- Nếu giá rẻ nhưng description có rủi ro, phải nói rõ rủi ro và có thể chọn sản phẩm khác đáng tin hơn.
- Nếu description không đủ chi tiết, hãy xem đó là độ bất định và đưa vào warnings khi cần.

Tư duy ReAct nội bộ:
Thought: hiểu nhu cầu người dùng và các ứng viên.
Action: phân tích description và so sánh p/p.
Observation: ghi nhận điểm mạnh/rủi ro/trade-off.
Final: trả về JSON duy nhất.

Định dạng đầu ra bắt buộc:
Trả về DUY NHẤT một JSON object hợp lệ, không markdown, không giải thích ngoài JSON.
Schema:
{
  "selected_shop": "Tên shop",
  "product_name": "Tên sản phẩm",
  "final_price": "Giá cuối, giữ đúng con số từ input",
  "reasoning": "Lý do chọn, dựa trên giá cuối + rating + ship + description",
  "warnings": ["Các lưu ý nếu có"]
}
""".strip()


def build_llm_prompt(products: List[Dict[str, Any]], user_query: str = "") -> str:
    payload = {
        "user_query": user_query or "N/A",
        "calculated_data": products,
    }
    return (
        "Hãy phân tích các sản phẩm sau và chọn 1 sản phẩm đáng mua nhất.\n"
        "Dữ liệu đã qua Node 2, vì vậy final_price/price_after_discount là giá đáng tin cậy.\n"
        "Trả về đúng JSON theo schema trong system prompt.\n\n"
        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
    )


def normalize_products(
    rows: Iterable[Mapping[str, Any]],
    limit: Optional[int] = None,
) -> List[Dict[str, Any]]:
    products: List[Dict[str, Any]] = []
    for index, row in enumerate(rows):
        if limit is not None and len(products) >= limit:
            break

        normalized_row = dict(row)
        final_price = _first_value(normalized_row, FINAL_PRICE_KEYS)
        sale_price = _first_value(normalized_row, SALE_PRICE_KEYS)
        price = _first_value(normalized_row, PRICE_KEYS)

        product = {
            "candidate_id": index + 1,
            "shop_name": _string_or_empty(_first_value(normalized_row, SHOP_KEYS)),
            "product_name": _string_or_empty(_first_value(normalized_row, PRODUCT_KEYS)),
            "price": _normalize_number(price),
            "price_after_discount": _normalize_number(sale_price),
            "final_price": _normalize_number(final_price if final_price not in (None, "") else sale_price),
            "rating": _normalize_number(_first_value(normalized_row, RATING_KEYS)),
            "max_delivery_days": _normalize_number(_first_value(normalized_row, DELIVERY_KEYS)),
            "description": _truncate(_string_or_empty(_first_value(normalized_row, DESCRIPTION_KEYS)), 800),
        }

        if product["final_price"] in (None, ""):
            product["final_price"] = product["price_after_discount"] or product["price"]

        if product["shop_name"] or product["product_name"]:
            products.append(product)

    return products


def parse_llm_json(content: str) -> Dict[str, Any]:
    cleaned = _strip_code_fence(content)
    try:
        parsed = json.loads(cleaned)
    except json.JSONDecodeError:
        parsed = json.loads(_extract_json_object(cleaned))

    if not isinstance(parsed, dict):
        raise ValueError("LLM output must be a JSON object.")
    return parsed


def validate_analysis(result: Mapping[str, Any], products: List[Dict[str, Any]]) -> Dict[str, Any]:
    selected_shop = _string_or_empty(result.get("selected_shop"))
    product_name = _string_or_empty(result.get("product_name"))
    matched = _find_product(products, selected_shop, product_name)

    warnings = result.get("warnings", [])
    if isinstance(warnings, str):
        warnings = [warnings]
    if not isinstance(warnings, list):
        warnings = []

    if matched is None:
        warnings.append("LLM chọn sản phẩm không khớp hoàn toàn với dữ liệu đầu vào; cần kiểm tra lại.")

    final_price = result.get("final_price")
    if matched is not None:
        final_price = matched.get("final_price")
        selected_shop = matched.get("shop_name", selected_shop)
        product_name = matched.get("product_name", product_name)

    return {
        "selected_shop": selected_shop,
        "product_name": product_name,
        "final_price": final_price if final_price is not None else "",
        "reasoning": _string_or_empty(result.get("reasoning")),
        "warnings": [_string_or_empty(item) for item in warnings if _string_or_empty(item)],
    }


def _find_product(
    products: List[Dict[str, Any]],
    selected_shop: str,
    product_name: str,
) -> Optional[Dict[str, Any]]:
    shop_key = _normalize_text(selected_shop)
    product_key = _normalize_text(product_name)

    for product in products:
        same_shop = shop_key and shop_key == _normalize_text(product.get("shop_name"))
        same_product = product_key and product_key == _normalize_text(product.get("product_name"))
        if same_shop and (same_product or not product_key):
            return product

    return None


def _first_value(row: Mapping[str, Any], keys: Iterable[str], default: Any = "") -> Any:
    normalized = {_normalize_key(key): value for key, value in row.items()}
    for key in keys:
        value = normalized.get(_normalize_key(key))
        if value not in (None, ""):
            return value
    return default


def _normalize_key(value: Any) -> str:
    return _normalize_text(str(value)).replace(" ", "_")


def _normalize_text(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").casefold()).strip()


def _normalize_number(value: Any) -> Any:
    if value in (None, ""):
        return ""
    if isinstance(value, bool):
        return int(value)
    if isinstance(value, (int, float)):
        return int(value) if float(value).is_integer() else float(value)

    text = str(value).strip()
    match = re.search(r"-?[\d.,]+", text)
    if not match:
        return text

    number = match.group(0)
    if "," in number and "." in number:
        decimal_sep = "," if number.rfind(",") > number.rfind(".") else "."
        thousand_sep = "." if decimal_sep == "," else ","
        number = number.replace(thousand_sep, "").replace(decimal_sep, ".")
    elif "," in number:
        number = _normalize_single_separator(number, ",")
    elif "." in number:
        number = _normalize_single_separator(number, ".")

    parsed = float(number)
    return int(parsed) if parsed.is_integer() else parsed


def _normalize_single_separator(number: str, separator: str) -> str:
    parts = number.split(separator)
    if len(parts[-1]) == 3 and all(len(part) <= 3 for part in parts[1:]):
        return "".join(parts)
    return ".".join(parts)


def _strip_code_fence(content: str) -> str:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?\s*", "", cleaned, flags=re.IGNORECASE)
        cleaned = re.sub(r"\s*```$", "", cleaned)
    return cleaned.strip()


def _extract_json_object(content: str) -> str:
    start = content.find("{")
    end = content.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("LLM output does not contain a JSON object.")
    return content[start : end + 1]


def _string_or_empty(value: Any) -> str:
    return "" if value is None else str(value).strip()


def _truncate(value: str, limit: int) -> str:
    if len(value) <= limit:
        return value
    return value[: limit - 3].rstrip() + "..."


def _track_llm_request(llm: LLMProvider, response: Mapping[str, Any]) -> None:
    try:
        from src.telemetry.metrics import tracker

        tracker.track_request(
            provider=str(response.get("provider") or llm.__class__.__name__),
            model=getattr(llm, "model_name", "unknown"),
            usage=dict(response.get("usage") or {}),
            latency_ms=int(response.get("latency_ms") or 0),
        )
    except Exception as exc:
        logger.error(f"Failed to track LLM metric: {exc}")
