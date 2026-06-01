from src.agent.agent import ReActAgent


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
    assert "Final Answer is too short" in llm.prompts[1][0]
