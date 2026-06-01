"""Input guards and shared scope/safety prompt blocks for agent and baseline."""
from __future__ import annotations

import re
import unicodedata
from typing import Optional

OUT_OF_SCOPE_MESSAGE_VI = (
    "Mình là trợ lý tư vấn mua sắm sản phẩm công nghệ "
    "(chuột, bàn phím, màn hình, laptop, tai nghe...). "
    "Mình không có thông tin để trả lời câu hỏi này. "
    "Bạn có thể hỏi về sản phẩm, giá, so sánh, giao hàng hoặc tổng đơn hàng."
)

SAFETY_MESSAGE_VI = (
    "Vì lý do bảo mật, vui lòng không gửi API key, mật khẩu, token hoặc thông tin thẻ qua chat. "
    "Cấu hình key trên server, không qua giao diện này."
)

GREETING_HINT_VI = (
    "Xin chào! Mình là trợ lý tư vấn mua sắm sản phẩm công nghệ "
    "(chuột, bàn phím, màn hình, laptop...). "
    "Bạn muốn tìm sản phẩm gì?"
)

SCOPE_SAFETY_PROMPT = """
Scope and safety:
- You are a tech shopping assistant for Lab 3: mice, keyboards, monitors, laptops, headphones, webcams, and similar gear.
- This catalog does NOT contain clothing, food, or general household items — never suggest those.
- Use only catalog/tool observations internally. Do not claim world knowledge outside those observations.
- NEVER mention file names, paths, spreadsheets, databases, or lab internals in user-facing text
  (no banggia.xlsx, XLSX, src/database, .env, "catalog file", tool names, etc.).
- If the question is unrelated to tech shopping (weather, news, homework, politics, medical advice, etc.),
  respond with a short Vietnamese refusal and suggest asking about tech products we sell.
- Never ask the user to send API keys, passwords, OTPs, card numbers, or other secrets.
  If they paste a secret, do not repeat it; tell them keys belong in server configuration.
- Do not give dangerous or illegal advice.
Examples:
- "xin chao" -> brief greeting + describe tech shopping assistant role (no file names).
- "thoi tiet hom nay" -> out-of-scope refusal in Vietnamese; do not invent product suggestions.
- user pastes sk-... key -> safety refusal (Vietnamese).
""".strip()

_CATALOG_KEYWORDS = (
    "gia",
    "giá",
    "tong",
    "tổng",
    "so sanh",
    "so sánh",
    "mua",
    "san pham",
    "sản phẩm",
    "shop",
    "cua hang",
    "cửa hàng",
    "giao",
    "rating",
    "cart",
    "quantity",
    "coupon",
    "re nhat",
    "rẻ nhất",
    "keyboard",
    "mouse",
    "chuot",
    "chuột",
    "ban phim",
    "bàn phím",
    "iphone",
    "laptop",
    "catalog",
    "banggia",
    "don hang",
    "đơn hàng",
    "price",
    "compare",
    "product",
    "delivery",
    "discount",
)

_OUT_OF_SCOPE_KEYWORDS = (
    "thoi tiet",
    "thời tiết",
    "weather",
    "tin tuc",
    "tin tức",
    "news",
    "bitcoin",
    "crypto",
    "viet code",
    "viết code",
    "python tutorial",
    "bai tap",
    "bài tập",
    "homework",
    "chinh tri",
    "chính trị",
    "y te",
    "y tế",
    "medical",
    "what day is today",
    "ngay hom nay",
    "ngày hôm nay",
    "may manh",
    "mấy mạnh",
    "nhiet do",
    "nhiệt độ",
    "temperature",
)

_SENSITIVE_PATTERNS = [
    (re.compile(r"\bsk-[a-zA-Z0-9]{10,}\b", re.I), "sk_prefix"),
    (re.compile(r"\bAIza[a-zA-Z0-9_-]{20,}\b"), "google_api_key"),
    (re.compile(r"\bBearer\s+[a-zA-Z0-9._-]{10,}\b", re.I), "bearer_token"),
    (re.compile(r"\b(api[_-]?key|apikey)\s*[:=]", re.I), "api_key_field"),
    (re.compile(r"\b(password|mat khau|mật khẩu|otp)\s*[:=]", re.I), "password_field"),
    (re.compile(r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b"), "card_number"),
]

_GREETING_ONLY = re.compile(
    r"^(xin\s*chào|xin\s*chao|hello|hi|chào|chao|hey)[\s!.?]*$",
    re.I,
)


def _normalize(text: str) -> str:
    normalized = unicodedata.normalize("NFD", text or "")
    without_accents = "".join(
        char for char in normalized if unicodedata.category(char) != "Mn"
    )
    without_accents = without_accents.replace("đ", "d").replace("Đ", "d")
    return " ".join(without_accents.lower().split())


def requires_catalog_tools(user_input: str) -> bool:
    normalized = _normalize(user_input)
    return any(keyword in normalized for keyword in _CATALOG_KEYWORDS)


def contains_sensitive_input(text: str) -> Optional[str]:
    for pattern, reason in _SENSITIVE_PATTERNS:
        if pattern.search(text):
            return reason
    return None


def is_greeting_only(text: str) -> bool:
    return bool(_GREETING_ONLY.match((text or "").strip()))


def is_out_of_scope(text: str) -> bool:
    if is_greeting_only(text):
        return False
    if requires_catalog_tools(text):
        return False
    normalized = _normalize(text)
    return any(keyword in normalized for keyword in _OUT_OF_SCOPE_KEYWORDS)


def check_input_guards(user_input: str) -> Optional[str]:
    """
    Return a canned Vietnamese reply if the message should not reach the LLM.
    Order: sensitive > greeting-only > out-of-scope.
    """
    sensitive = contains_sensitive_input(user_input)
    if sensitive:
        return SAFETY_MESSAGE_VI
    if is_greeting_only(user_input):
        return GREETING_HINT_VI
    if is_out_of_scope(user_input):
        return OUT_OF_SCOPE_MESSAGE_VI
    return None
