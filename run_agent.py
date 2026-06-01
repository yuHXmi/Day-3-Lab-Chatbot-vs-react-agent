"""
Lab 3 — Phase 3: ReAct Agent v2 (Smart E-commerce Assistant).
  python run_agent.py
  python run_agent.py --interactive
"""

import os
import sys

from dotenv import load_dotenv

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

if sys.platform == "win32" and hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.agent.agent import ReActAgent
from src.core.local_provider import validate_model_file
from src.core.provider_factory import get_llm_provider
from src.tools.registry import TOOL_SPECS

TEST_CASES = [
    {
        "id": "multi_step",
        "label": "Multi-step order (agent should use tools)",
        "prompt": (
            "I want to buy 2 iPhones using code 'WINNER' and ship to Hanoi. "
            "What is the total price in VND? Show your calculation step by step."
        ),
    },
    {
        "id": "stock_check",
        "label": "Single tool — stock lookup",
        "prompt": "How many MacBook Air M3 units are in stock and what is the unit price in VND?",
    },
]


def _resolve_local_model_path() -> str:
    return os.path.abspath(
        os.getenv("LOCAL_MODEL_PATH", "./models/Phi-3-mini-4k-instruct-q4.gguf")
    )


def _validate_env(provider: str) -> None:
    if provider == "local":
        try:
            validate_model_file(_resolve_local_model_path())
        except (FileNotFoundError, ValueError) as exc:
            print(f"Error: {exc}")
            sys.exit(1)
        return

    if provider in ("google", "gemini"):
        key = os.getenv("GEMINI_API_KEY", "")
        if not key or key.startswith("your_"):
            print("Error: Set GEMINI_API_KEY in .env")
            sys.exit(1)
        return

    if provider == "openai":
        key = os.getenv("OPENAI_API_KEY", "")
        if not key or key.startswith("your_"):
            print("Error: Set OPENAI_API_KEY in .env")
            sys.exit(1)
        return

    print(f"Error: Unknown DEFAULT_PROVIDER='{provider}'")
    sys.exit(1)


def run_demo(agent: ReActAgent) -> None:
    print("=" * 60)
    print("Lab 3 — ReAct Agent v2")
    print("=" * 60)

    for case in TEST_CASES:
        print(f"\n[{case['id']}] {case['label']}")
        print(f"User: {case['prompt']}\n")
        print("Assistant:\n")
        print(agent.run(case["prompt"]))
        print("-" * 60)


def run_interactive(agent: ReActAgent) -> None:
    print("Interactive ReAct agent. Type 'quit' to exit.\n")
    while True:
        user_input = input("You: ").strip()
        if not user_input:
            continue
        if user_input.lower() in ("quit", "exit", "q"):
            break
        print("\nAssistant:\n")
        print(agent.run(user_input))
        print()


def main() -> None:
    load_dotenv()
    provider = os.getenv("DEFAULT_PROVIDER", "google").lower()
    _validate_env(provider)

    max_steps = int(os.getenv("AGENT_MAX_STEPS", "8"))
    llm = get_llm_provider()
    agent = ReActAgent(llm=llm, tools=TOOL_SPECS, max_steps=max_steps)

    print(f"Provider: {provider} | Model: {llm.model_name} | max_steps: {max_steps}\n")

    if len(sys.argv) > 1 and sys.argv[1] == "--interactive":
        run_interactive(agent)
    else:
        run_demo(agent)
        print("\nTip: python run_agent.py --interactive")
        print("Logs: logs/ (AGENT_*, TOOL_CALL, LLM_METRIC)")


if __name__ == "__main__":
    main()
