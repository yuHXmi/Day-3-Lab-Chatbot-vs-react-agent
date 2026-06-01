# Individual Report: Lab 3 - Chatbot vs ReAct Agent

- **Student Name**: [Fill in your name]
- **Student ID**: [Fill in your student ID]
- **Date**: 2026-06-01

---

## I. Technical Contribution (15 Points)

My contribution focused on making the ReAct agent work reliably for an e-commerce workflow that requires real tool usage instead of guessing. The main goal was to move beyond a simple chatbot answer and build an agent that can check product data, validate discounts, calculate shipping, and combine all observations into a final answer.

### Modules Implemented / Improved

- `src/agent/agent.py`
  - Implemented the main `Thought -> Action -> Observation -> Final Answer` loop.
  - Built the prompt dynamically from the user question and previous observations.
  - Added `max_steps` to prevent infinite loops.
  - Connected parsed tool calls to actual Python functions through `_execute_tool`.
  - Developed Agent v2 validation before tool execution, including unknown tool detection, missing argument detection, and invalid argument detection.
  - Returned structured correction observations so the LLM can retry with the correct tool schema instead of failing immediately.
  - Logged agent start, each reasoning step, tool calls, latency, usage, and agent end events.
  - Added `TOOL_VALIDATION_ERROR` logging for invalid tool calls.

- `src/agent/parsers.py`
  - Used regular expressions to parse `Final Answer:` and `Action: tool_name(...)`.
  - Converted tool arguments from strings into suitable Python values such as `int`, `float`, and `bool`.
  - Supported tool calls such as `check_stock(item_name="iPhone")`, `get_discount(coupon_code="WINNER")`, and `calc_shipping(weight=0.7, destination="Hanoi")`.

- `src/tools/check_stock.py`
  - Provided inventory lookup for products such as iPhone 15, MacBook Air M3, and AirPods Pro 2.
  - Returned structured information including product name, stock, unit price in VND, and weight in kilograms.
  - Added product name normalization so inputs like `iPhone`, `iphone`, and partial names can still be resolved.

- `src/tools/get_discount.py`
  - Implemented coupon validation for codes such as `WINNER` and `VIP`.
  - Returned discount rate and validity status so the agent can calculate order totals correctly.

- `src/tools/calc_shipping.py`
  - Implemented shipping fee calculation based on total package weight and destination.
  - Added validation for invalid weight and empty destination.
  - Supported city-specific rates for Hanoi, Ho Chi Minh / HCMC, and Da Nang, with a default fallback rate.

- `src/tools/registry.py`
  - Registered all tools in one central `TOOL_SPECS` list.
  - Documented each tool's purpose, parameters, and example usage so the LLM can call tools with the correct syntax.

- `tests/test_agent_v2.py`
  - Added a fake LLM provider test so Agent v2 can be verified without calling Gemini, OpenAI, or a local model.
  - Tested the exact failure pattern `calc_shipping(weight_kg=0.7, destination="Hanoi")`.
  - Confirmed that the agent returns an observation listing valid arguments and then succeeds when the model retries with `weight=0.7`.

### Code Highlights

The most important implementation detail is that the agent rebuilds the prompt at every step using the original user question and the accumulated history:

```python
current_prompt = self._build_prompt(user_input)
result = self.llm.generate(current_prompt, system_prompt=self.get_system_prompt())
```

After the LLM produces an action, the agent parses it, executes the corresponding tool, and appends the result as an observation:

```python
action = parse_action(content)
if action:
    tool_name, kwargs = action
    observation = self._execute_tool(tool_name, kwargs)
    self.history.append(f"Observation: {observation}")
```

This is the key difference from the baseline chatbot. The chatbot can only generate an answer from model knowledge, while the ReAct agent can ground its answer in real tool outputs.

Agent v2 adds one more reliability layer before execution. Instead of directly calling a Python function with any arguments produced by the LLM, the agent checks the function signature first:

```python
validation_error = self._validate_tool_args(tool_name, tool_function, kwargs)
if validation_error:
    return validation_error
```

This means malformed actions become useful feedback inside the ReAct loop. For example, if the model calls `calc_shipping(weight_kg=0.7, destination="Hanoi")`, the agent responds with an observation explaining that `weight_kg` is unknown and that the valid arguments are `weight` and `destination`.

### Documentation

The group report documents the final architecture, tool specs, evaluation metrics, failure traces, and final demo evidence. The final demo used two representative test cases:

- Multi-step order: buy 2 iPhones, apply coupon `WINNER`, ship to Hanoi, and calculate total price.
- Stock lookup: ask for MacBook Air M3 stock and unit price.

The final ReAct agent completed both cases successfully.

---

## II. Debugging Case Study (10 Points)

### Problem Description

One important failure happened when the agent tried to calculate shipping for the multi-step iPhone order. The model called:

```text
Action: calc_shipping(weight_kg=0.7, destination="Hanoi")
```

However, the actual Python function was defined as:

```python
def calc_shipping(weight: float, destination: str) -> int:
```

This caused an argument mismatch because the tool expected `weight`, not `weight_kg`.

### Log Source / Evidence

The failure appeared during the multi-step order task:

```text
User input:
I want to buy 2 iPhones using code 'WINNER' and ship to Hanoi.
What is the total price in VND? Show your calculation step by step.

Failed tool call:
calc_shipping(weight_kg=0.7, destination="Hanoi")

Expected tool call:
calc_shipping(weight=0.7, destination="Hanoi")
```

The final corrected trace was:

```text
check_stock(item_name="iPhone")
-> product=iPhone 15; stock=42; unit_price_vnd=25990000; weight_kg=0.35

get_discount(coupon_code="WINNER")
-> discount=0.1

calc_shipping(weight=0.7, destination="Hanoi")
-> 25600
```

### Diagnosis

The root cause was not the shipping function itself. The problem came from inconsistency between the prompt/tool specification and the real function signature.

From the model's point of view, `weight_kg` was a reasonable argument name because the observation from `check_stock` returned `weight_kg=0.35`. But the executable function accepted `weight`. This shows that in a ReAct system, the tool contract must be extremely precise. Even a small mismatch in parameter names can break the whole reasoning chain.

### Solution

The first fix was to align the system prompt and tool registry with the real function signature:

```text
calc_shipping(weight=0.7, destination="Hanoi")
```

For Agent v2, I added a stronger fix: argument validation before tool execution. With this improvement, the agent can detect the same mistake even if the LLM repeats it later.

V2 recovery example:

```text
Thought: I need shipping.
Action: calc_shipping(weight_kg=0.7, destination="Hanoi")

Observation: Error: Invalid arguments for calc_shipping. Unknown arguments: weight_kg.
Missing required arguments: weight. Valid arguments are: weight, destination.
Retry using the exact tool schema.

Thought: I should use the valid argument name.
Action: calc_shipping(weight=0.7, destination="Hanoi")

Observation: 25600
```

After the prompt/spec correction, the normal final run no longer needed an extra recovery step. The multi-step order was completed in 4 LLM steps with 3 tool calls:

1. Check iPhone price, weight, and stock.
2. Validate coupon `WINNER`.
3. Calculate shipping for `0.7 kg` to Hanoi.
4. Produce the final answer with step-by-step calculation.

Final calculation:

```text
Subtotal: 25,990,000 * 2 = 51,980,000 VND
Discount: 51,980,000 * 10% = 5,198,000 VND
After discount: 51,980,000 - 5,198,000 = 46,782,000 VND
Shipping: 25,600 VND
Total: 46,782,000 + 25,600 = 46,807,600 VND
```

### Lesson Learned

Telemetry was important because it made the failure visible at the exact step where it happened. Without step-by-step logs, the final wrong answer might look like a reasoning issue, but the real issue was a tool interface mismatch. For production agents, logs should capture model output, parsed action, tool arguments, tool result, latency, and termination status.

The V2 improvement also showed that ReAct agents should not trust LLM-generated tool calls blindly. Tool validation turns a runtime exception into a controlled observation, which gives the model a chance to self-correct while keeping the system stable.

### Verification

I verified Agent v2 with:

```bash
python -m pytest tests\test_agent_v2.py
```

Result:

```text
2 passed
```

---

## III. Personal Insights: Chatbot vs ReAct (10 Points)

### 1. Reasoning

The baseline chatbot is good for general explanation, but it cannot reliably answer questions that require live or structured data. For example, if the user asks for stock, price, coupon discount, and shipping fee, a chatbot may produce a fluent answer but it has no guarantee that the numbers are correct.

The ReAct agent is stronger because it separates reasoning from acting. The `Thought` step helps the model decide what information is missing. The `Action` step forces it to call a real tool. The `Observation` step brings the result back into the context, so the next step can depend on actual data instead of guessing.

In the final demo, this made a clear difference. The agent calculated the iPhone order total correctly because it gathered the required facts in order:

- Unit price and weight from `check_stock`.
- Discount rate from `get_discount`.
- Shipping fee from `calc_shipping`.

### 2. Reliability

The agent is not always better than the chatbot. For simple questions, the ReAct agent can be slower and more expensive because it may spend extra tokens deciding whether to use tools. A direct chatbot answer is often enough for general questions such as explaining what a coupon is or describing how shipping usually works.

The agent can also fail in more complex ways. A chatbot usually fails by hallucinating an answer. A ReAct agent can fail through parser errors, invalid tool names, wrong argument names, repeated tool calls, or exceeding `max_steps`. This means agent reliability depends not only on model quality, but also on prompt design, parser robustness, tool schema clarity, validation, and telemetry.

Agent v2 improved this reliability by checking the tool call before execution. This did not make the model smarter, but it made the system safer. The important lesson is that production agents need software guardrails around the LLM.

### 3. Observation

Observations are what make the ReAct loop practical. Each observation becomes new evidence for the next decision. In the iPhone order case, the observation from `check_stock` gave the unit price and weight. That directly influenced both the discount calculation and the shipping calculation.

This made the agent's reasoning auditable. Instead of only seeing a final answer, we can inspect every intermediate step and verify whether the final number came from correct data.

My main insight is that a ReAct agent is closer to a small software system than a single chatbot prompt. The LLM is only one component. The surrounding system, including tools, parser, logs, validation, and stopping rules, determines whether the agent can be trusted.

---

## IV. Future Improvements (5 Points)

### Scalability

For a production-level system, tool execution should become asynchronous. Some tools may call databases, payment services, shipping APIs, or external inventory systems. An async queue would allow the agent to handle slow tools without blocking the whole application.

If the number of tools grows, the agent should not receive every tool in the prompt. A tool retrieval layer could select only relevant tools based on the user request. This would reduce token usage and lower the chance of calling the wrong tool.

### Safety

The agent should include stronger guardrails before executing sensitive actions. For example, checking stock and calculating totals are safe read-only operations, but placing an order or charging payment should require explicit confirmation.

Agent v2 already adds the first layer of safety by validating tool names and arguments before execution. A future supervisor layer could extend this idea by validating higher-risk actions:

- Is the tool name allowed?
- Are the arguments valid?
- Is the requested operation safe?
- Does the final answer match the tool observations?

### Performance

The telemetry system already logs latency and token usage. The next improvement is to convert token usage into estimated cost per task. This would make it easier to compare chatbot, ReAct v1, and ReAct v2 in terms of both accuracy and operating cost.

Caching could also improve performance. Product data, coupon validation, and shipping rates often repeat across users. Caching these tool results would reduce latency and repeated API/tool calls.

### Toward RAG / Multi-Agent

To scale this into a production RAG or multi-agent system, I would add:

- A vector database for product manuals, policy documents, warranty terms, and FAQ retrieval.
- A planner agent for deciding the workflow.
- Specialized agents for inventory, pricing, shipping, and customer support.
- A final verifier agent that checks whether the answer is supported by observations and retrieved documents.

This would make the system more reliable for larger e-commerce workflows while keeping each component easier to test and monitor.
