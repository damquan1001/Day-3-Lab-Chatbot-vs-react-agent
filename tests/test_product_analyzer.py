from src.core.product_analyzer import (
    analyze_products,
    normalize_products,
    parse_llm_json,
    react_analysis_node,
)


class FakeLLM:
    model_name = "fake-model"

    def __init__(self, content):
        self.content = content
        self.last_prompt = None
        self.last_system_prompt = None

    def generate(self, prompt, system_prompt=None):
        self.last_prompt = prompt
        self.last_system_prompt = system_prompt
        return {
            "content": self.content,
            "usage": {"prompt_tokens": 10, "completion_tokens": 5, "total_tokens": 15},
            "latency_ms": 1,
            "provider": "fake",
        }

    def stream(self, prompt, system_prompt=None):
        yield self.content


def test_analyze_products_uses_llm_choice_without_formula_ranking():
    rows = [
        {
            "shop_name": "CheapShop",
            "product_name": "Keyboard A",
            "final_price": 100000,
            "rating": 4.9,
            "max_delivery_days": 1,
            "description": "hang cu no-box khong bao hanh",
        },
        {
            "shop_name": "SafeShop",
            "product_name": "Keyboard B",
            "final_price": 130000,
            "rating": 4.7,
            "max_delivery_days": 2,
            "description": "hang chinh hang bao hanh 24 thang",
        },
    ]
    llm = FakeLLM(
        """
        {
          "selected_shop": "SafeShop",
          "product_name": "Keyboard B",
          "final_price": "130000",
          "reasoning": "Dat hon nhung chinh hang va co bao hanh.",
          "warnings": []
        }
        """
    )

    result = analyze_products(rows, llm)

    assert result["selected_shop"] == "SafeShop"
    assert result["product_name"] == "Keyboard B"
    assert result["final_price"] == 130000
    assert result["llm_used"] is True
    assert "Khong dung cong thuc diem cung" in llm.last_system_prompt


def test_parse_llm_json_accepts_code_fences_and_extra_text():
    parsed = parse_llm_json(
        """
        Ghi chu:
        ```json
        {"selected_shop": "A", "final_price": "100000", "reasoning": "ok", "warnings": []}
        ```
        """
    )

    assert parsed["selected_shop"] == "A"


def test_normalize_products_accepts_vietnamese_column_names():
    rows = [
        {
            "ten_shop": "GearVN",
            "ten_san_pham": "DareU EK87",
            "gia_kem_sales": "527.120 VND",
            "rating": "4.6",
            "max_delivery_days": "3",
            "mo_ta": "Ban phim co switch blue",
        }
    ]

    products = normalize_products(rows)

    assert products[0]["shop_name"] == "GearVN"
    assert products[0]["product_name"] == "DareU EK87"
    assert products[0]["final_price"] == 527120
    assert products[0]["rating"] == 4.6


def test_react_analysis_node_returns_state_delta():
    llm = FakeLLM(
        '{"selected_shop":"GearVN","product_name":"DareU EK87","final_price":"527120",'
        '"reasoning":"P/P tot.","warnings":[]}'
    )
    state = {
        "query": "tim ban phim",
        "calculated_data": [
            {
                "shop_name": "GearVN",
                "product_name": "DareU EK87",
                "final_price": 527120,
                "rating": 4.6,
                "max_delivery_days": 3,
                "description": "Ban phim co layout TKL switch blue",
            }
        ],
    }

    delta = react_analysis_node(state, llm)

    assert delta["final_analysis"]["selected_shop"] == "GearVN"
