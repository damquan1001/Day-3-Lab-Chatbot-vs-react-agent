from src.agent.agent import ReActAgent
from src.agent.guards import (
    GREETING_HINT_VI,
    OUT_OF_SCOPE_MESSAGE_VI,
    SAFETY_MESSAGE_VI,
)


class FakeLLM:
    model_name = "fake-model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def generate(self, prompt, system_prompt=None):
        self.prompts.append((prompt, system_prompt))
        return {
            "content": self.responses.pop(0),
            "usage": {"prompt_tokens": 10, "completion_tokens": 3, "total_tokens": 13},
            "latency_ms": 1,
            "provider": "fake",
        }

    def stream(self, prompt, system_prompt=None):
        yield ""


LONG_FINAL = (
    "Final Answer: Mình chốt DareU EK87 vì đây là lựa chọn có giá sau giảm 527120 VND, "
    "phù hợp nếu bạn muốn một bàn phím cơ TKL trong tầm giá dễ chịu. Rating của sản phẩm "
    "đạt 4.6 nên đủ tốt để cân bằng giữa chi phí và độ tin cậy. Thời gian giao tối đa 3 ngày "
    "cũng không quá chậm cho nhu cầu mua dùng sớm. So với các lựa chọn cao cấp hơn, DareU EK87 "
    "không cố thắng bằng nhiều tính năng phụ mà thắng ở p/p. Mô tả nói rõ switch blue cho gõ nhanh, "
    "nhưng bạn nên cân nhắc nếu không thích tiếng clicky. Nếu ưu tiên tiết kiệm mà vẫn muốn trải nghiệm "
    "bàn phím cơ, đây là deal nên chọn."
)


def test_react_agent_calls_tool_and_returns_final_answer():
    calls = []

    def search_products(**kwargs):
        calls.append(kwargs)
        return {"products": [{"product_name": "DareU EK87", "price_after_discount": 527120}]}

    llm = FakeLLM(
        [
            'Thought: Need catalog lookup.\nAction: search_products({"query": "keyboard", "max_results": 1})',
            (
                "Thought: I have the observation.\n"
                "Final Answer: Mình chốt DareU EK87 vì đây là lựa chọn có giá sau giảm 527120 VND, "
                "phù hợp nếu bạn muốn một bàn phím cơ TKL trong tầm giá dễ chịu. Rating của sản phẩm "
                "đạt 4.6 nên đủ tốt để cân bằng giữa chi phí và độ tin cậy. Thời gian giao tối đa 3 ngày "
                "cũng không quá chậm cho nhu cầu mua dùng sớm. So với các lựa chọn cao cấp hơn, DareU EK87 "
                "không cố thắng bằng nhiều tính năng phụ mà thắng ở p/p. Mô tả nói rõ switch blue cho gõ nhanh, "
                "nhưng bạn nên cân nhắc nếu không thích tiếng clicky. Nếu ưu tiên tiết kiệm mà vẫn muốn trải nghiệm "
                "bàn phím cơ, đây là deal nên chọn."
            ),
        ]
    )
    agent = ReActAgent(
        llm,
        tools=[
            {
                "name": "search_products",
                "description": "Search products.",
                "func": search_products,
            }
        ],
    )

    answer = agent.run("tim ban phim")

    assert "Mình chốt DareU EK87" in answer
    assert calls == [{"query": "keyboard", "max_results": 1}]
    assert "Observation:" in llm.prompts[1][0]


def test_react_agent_supports_keyword_action_args():
    calls = []

    def compare_products(**kwargs):
        calls.append(kwargs)
        return "ok"

    llm = FakeLLM(
        [
            'Thought: Compare.\nAction: compare_products(query="mouse", max_results=2)',
            (
                "Final Answer: Mình đã so sánh nhanh các lựa chọn chuột theo giá, rating và dữ liệu trả về từ tool. "
                "Lựa chọn nên ưu tiên là mẫu có tổng thể cân bằng nhất thay vì chỉ nhìn giá thấp nhất. Nếu một sản phẩm "
                "rẻ hơn nhưng rating hoặc mô tả kém rõ ràng, mình sẽ không chốt vội vì rủi ro trải nghiệm sau mua cao hơn. "
                "Trong nhóm đang xét, sản phẩm được đề xuất có lợi thế vì giữ được mức giá hợp lý trong khi vẫn đáp ứng "
                "nhu cầu chính của người dùng. Bạn nên chọn phương án này nếu cần một deal an toàn, dễ mua và ít phải đánh đổi."
            ),
        ]
    )
    agent = ReActAgent(
        llm,
        tools=[
            {
                "name": "compare_products",
                "description": "Compare products.",
                "func": compare_products,
            }
        ],
    )

    assert "deal an toàn" in agent.run("so sanh mouse")
    assert calls == [{"query": "mouse", "max_results": 2}]


def test_react_agent_reasks_when_final_answer_is_too_short():
    llm = FakeLLM(
        [
            "Final Answer: Keychron K2 V2 là lựa chọn tốt.",
            (
                "Final Answer: Mình chốt Keychron K2 V2 vì nó cân bằng tốt giữa giá, rating và thời gian giao. "
                "Giá sau giảm 2151000 VND không phải thấp nhất tuyệt đối, nhưng hợp lý cho một bàn phím cơ không dây. "
                "Rating 4.7 cho thấy độ tin cậy khá ổn trong nhóm sản phẩm được so sánh. Thời gian giao tối đa 3 ngày "
                "đáp ứng đúng nhu cầu không phải chờ quá lâu. So với AKKO 3098B Plus, Keychron K2 V2 nhỉnh hơn ở tốc độ giao "
                "và hỗ trợ Mac/Windows rõ trong mô tả. Mô tả không nêu rủi ro như hàng cũ hay không bảo hành, nhưng cũng chưa nói "
                "nhiều về switch nên bạn nên kiểm tra thêm nếu có gu gõ cụ thể. Nếu cần một lựa chọn an toàn cho làm việc đa thiết bị, "
                "đây là deal nên mua."
            ),
        ]
    )
    agent = ReActAgent(llm, tools=[])

    answer = agent.run("tim ban phim khong day")

    assert "Mình chốt Keychron K2 V2" in answer
    assert "Thin final answer that must be improved" in llm.prompts[1][0]


def _search_tool(func):
    return {
        "name": "search_products",
        "description": "Search products.",
        "func": func,
    }


def test_v2_parse_action_with_trailing_text():
    calls = []

    def search_products(**kwargs):
        calls.append(kwargs)
        return {"products": []}

    llm = FakeLLM(
        [
            (
                'Thought: search.\n'
                'Action: search_products({"query": "mouse"})\n'
                "Note: extra line after action should not break parser."
            ),
            LONG_FINAL,
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(search_products)], version=2)
    answer = agent.run("tim chuot")

    assert calls == [{"query": "mouse"}]
    assert "DareU EK87" in answer


def test_v2_parse_action_inside_code_fence():
    calls = []

    def search_products(**kwargs):
        calls.append(kwargs)
        return "ok"

    llm = FakeLLM(
        [
            'Action: search_products(```json\n{"query": "keyboard"}\n```)\nTrailing text.',
            LONG_FINAL,
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(search_products)], version=2)
    agent.run("ban phim")

    assert calls == [{"query": "keyboard"}]


def test_v2_parse_retry_hint_in_scratchpad():
    llm = FakeLLM(
        [
            "Thought: confused format only.",
            'Action: search_products({"query": "mouse"})',
            LONG_FINAL,
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(lambda **k: "ok")], version=2)
    agent.run("tim chuot")

    assert "RETRY:" in llm.prompts[1][0]


def test_v2_blocks_duplicate_tool_calls():
    calls = []

    def search_products(**kwargs):
        calls.append(kwargs)
        return "ok"

    duplicate_action = 'Action: search_products({"query": "mouse"})'
    llm = FakeLLM(
        [
            duplicate_action,
            duplicate_action,
            LONG_FINAL,
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(search_products)], version=2)
    agent.run("tim chuot")

    assert len(calls) == 1
    assert any("Duplicate action blocked" in prompt[0] for prompt in llm.prompts)


def test_v2_blocks_final_without_tools_for_catalog_question():
    calls = []

    def search_products(**kwargs):
        calls.append(kwargs)
        return {"products": [{"product_name": "Mouse A", "price_after_discount": 100000}]}

    llm = FakeLLM(
        [
            "Final Answer: Tổng là 200000 VND.",
            'Action: search_products({"query": "chuot"})',
            (
                "Final Answer: Mình đã tính tổng dựa trên catalog sau khi gọi tool search_products. "
                "Hai chuột với giá 100000 VND mỗi con cho tổng 200000 VND trước phí ship. "
                "Rating và thời gian giao đều ở mức chấp nhận được cho đơn nhỏ. "
                "So với mua lẻ từng cái, gom đơn giúp kiểm soát chi phí tốt hơn. "
                "Không thấy red flag trong mô tả sản phẩm. Nếu cần mua nhanh hai con, đây là deal nên chọn. "
                "Bạn có thể hỏi thêm coupon hoặc shop khác nếu muốn tối ưu thêm chi phí cuối cùng."
            ),
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(search_products)], version=2)
    answer = agent.run("tổng tiền 2 chuột")

    assert len(calls) == 1
    assert "must call at least one catalog tool" in llm.prompts[1][0]
    assert "200000" in answer


def test_v2_greeting_does_not_call_llm():
    llm = FakeLLM(["should not run"])
    agent = ReActAgent(llm, tools=[], version=2)

    assert agent.run("xin chào") == GREETING_HINT_VI
    assert llm.prompts == []


def test_v2_out_of_scope_does_not_call_llm():
    llm = FakeLLM(["should not run"])
    agent = ReActAgent(llm, tools=[], version=2)

    assert agent.run("thời tiết Hà Nội") == OUT_OF_SCOPE_MESSAGE_VI
    assert llm.prompts == []


def test_v2_temperature_out_of_scope_does_not_call_llm():
    llm = FakeLLM(["should not run"])
    agent = ReActAgent(llm, tools=[], version=2)

    assert agent.run("nhiệt độ Hà Nội") == OUT_OF_SCOPE_MESSAGE_VI
    assert llm.prompts == []


def test_v2_safety_does_not_call_llm():
    llm = FakeLLM(["should not run"])
    agent = ReActAgent(llm, tools=[], version=2)

    assert agent.run("sk-test123456789012345678") == SAFETY_MESSAGE_VI
    assert llm.prompts == []


def test_v2_catalog_question_still_calls_llm():
    llm = FakeLLM(
        [
            'Action: search_products({"query": "chuot"})',
            LONG_FINAL,
        ]
    )
    agent = ReActAgent(llm, tools=[_search_tool(lambda **k: "ok")], version=2)
    agent.run("giá chuột")

    assert len(llm.prompts) >= 1
