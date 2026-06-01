from src.chat.baseline import (
    ChatbotBaseline,
    build_catalog_context,
    build_prompt,
    load_catalog_context,
)


class FakeLLM:
    model_name = "fake-model"

    def __init__(self, content="ok"):
        self.content = content
        self.last_prompt = None
        self.last_system_prompt = None

    def generate(self, prompt, system_prompt=None):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return {
            "content": self.content,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2, "total_tokens": 12},
            "latency_ms": 1,
            "provider": "fake",
        }

    def stream(self, prompt, system_prompt=None):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        yield self.content


def test_build_catalog_context_keeps_full_rows_as_csv():
    context = build_catalog_context(
        [
            {
                "category": "keyboard",
                "product_name": "DareU EK87",
                "shop_name": "GearVN",
                "price": 599000,
                "discount_percent": 12,
                "price_after_discount": 527120,
                "rating": 4.6,
                "max_delivery_days": 3,
                "description": "Ban phim co switch blue",
            }
        ]
    )

    assert "category,product_name,shop_name" in context
    assert "DareU EK87" in context
    assert "527120" in context


def test_load_catalog_context_reads_full_xlsx_file():
    context = load_catalog_context()

    assert "Logitech K120" in context
    assert "Asus ROG Falchion" in context
    assert context.count("\n") >= 50


def test_build_prompt_injects_catalog_without_tools():
    prompt = build_prompt([], "tim ban phim", "category,product_name\nkeyboard,K120")

    assert "FULL XLSX CATALOG" in prompt
    assert "category,product_name" in prompt
    assert "User: tim ban phim" in prompt


def test_chatbot_baseline_sends_catalog_to_llm():
    llm = FakeLLM("baseline answer")
    bot = ChatbotBaseline(
        llm,
        catalog_context="category,product_name,shop_name\nkeyboard,Logitech K120,TechZone",
    )

    result = bot.complete("ban phim nao re?")

    assert result["reply"] == "baseline answer"
    assert "Logitech K120" in llm.last_prompt
    assert "do not have access to tools" in llm.last_system_prompt
