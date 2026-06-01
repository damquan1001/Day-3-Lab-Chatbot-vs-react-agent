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
            "Thought: I have the observation.\nFinal Answer: DareU EK87 costs 527120 VND.",
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

    assert answer == "DareU EK87 costs 527120 VND."
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
            "Final Answer: done",
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

    assert agent.run("so sanh mouse") == "done"
    assert calls == [{"query": "mouse", "max_results": 2}]
