from typing import Any, Dict, Generator, Optional

from src.agent.agent import ReActAgent
from src.core.llm_provider import LLMProvider
from src.tools.registry import TOOL_SPECS


class FakeLLMProvider(LLMProvider):
    def __init__(self, responses):
        super().__init__(model_name="fake-v2")
        self.responses = responses
        self.prompts = []

    def generate(self, prompt: str, system_prompt: Optional[str] = None) -> Dict[str, Any]:
        self.prompts.append(prompt)
        content = self.responses.pop(0)
        return {
            "content": content,
            "usage": {"prompt_tokens": 0, "completion_tokens": 0},
            "latency_ms": 0,
        }

    def stream(self, prompt: str, system_prompt: Optional[str] = None) -> Generator[str, None, None]:
        yield self.generate(prompt, system_prompt)["content"]


def test_agent_v2_reports_invalid_tool_arguments_and_self_corrects():
    llm = FakeLLMProvider([
        'Thought: I need shipping.\nAction: calc_shipping(weight_kg=0.7, destination="Hanoi")',
        'Thought: I should use the valid argument name.\nAction: calc_shipping(weight=0.7, destination="Hanoi")',
        "Final Answer: Shipping fee is 25,600 VND.",
    ])
    agent = ReActAgent(llm=llm, tools=TOOL_SPECS, max_steps=3)

    answer = agent.run("Calculate shipping for 0.7 kg to Hanoi.")

    assert answer == "Shipping fee is 25,600 VND."
    assert "Unknown arguments: weight_kg" in llm.prompts[1]
    assert "Valid arguments are: weight, destination" in llm.prompts[1]


def test_agent_v2_reports_unknown_tool_with_valid_tool_list():
    llm = FakeLLMProvider([
        'Thought: I need product info.\nAction: lookup_product(item_name="iPhone")',
        "Final Answer: I should use check_stock for product lookup.",
    ])
    agent = ReActAgent(llm=llm, tools=TOOL_SPECS, max_steps=2)

    answer = agent.run("How many iPhones are in stock?")

    assert answer == "I should use check_stock for product lookup."
    assert "Tool 'lookup_product' not found" in llm.prompts[1]
    assert "check_stock" in llm.prompts[1]
