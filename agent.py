"""Agent loop: call the LLM, execute requested tools, append observations, repeat."""

import json
from typing import Any, Callable

from llm import LLMClient
from tools import TOOL_SCHEMAS, TOOLS, get_tool_schemas

SYSTEM_PROMPT = """You are a helpful meal planning assistant with access to recipe tools.

Your job is to help users find recipes that match their constraints (dietary needs,
available ingredients, time limits, and serving size).

Rules:
- Use the provided tools to search recipes, check ingredients, estimate cooking time,
  and scale recipes. Do not invent recipe data.
- Respect user constraints such as vegetarian/vegan, time limits, and serving counts.
- When the user lists available ingredients, pass them to check_ingredients.
- Scale the final recipe to the requested number of servings when applicable.
- Give a concise final recommendation summarizing the chosen recipe, cooking time,
  ingredient gaps, and scaled quantities.
- Do not expose internal reasoning or chain-of-thought. Reply with direct answers only.
"""

MAX_STEPS_MESSAGE = (
    "I reached the maximum number of agent steps without a final answer. "
    "Please try a simpler request or increase MAX_AGENT_STEPS."
)


def execute_tool(name: str, args: dict) -> dict:
    """Dispatch a tool call by name. Returns the tool result or an error dict."""
    if name not in TOOLS:
        return {"error": f"Unknown tool: {name}"}

    schema = next((item for item in TOOL_SCHEMAS if item["name"] == name), None)
    if schema:
        required = schema["input_schema"].get("required", [])
        missing = [field for field in required if field not in args]
        if missing:
            return {"error": f"Missing required arguments: {', '.join(missing)}"}

    try:
        return TOOLS[name](**args)
    except Exception as exc:
        return {"error": str(exc)}


def run_agent(
    user_request: str,
    llm_client: LLMClient,
    max_steps: int = 8,
    on_step: Callable[[str, Any], None] | None = None,
) -> str:
    """Run the tool-use loop until a final text answer or max_steps is reached."""
    messages: list[dict] = [{"role": "user", "content": user_request}]
    tool_schemas = get_tool_schemas()

    for step in range(1, max_steps + 1):
        if on_step:
            on_step("step", step)

        response = llm_client.complete(messages, tool_schemas, system=SYSTEM_PROMPT)

        if response.has_tool_calls:
            messages.append(
                {"role": "assistant", "content": response.raw_assistant_content}
            )

            tool_result_blocks: list[dict] = []
            for tool_call in response.tool_calls:
                if on_step:
                    on_step(
                        "tool_call",
                        {"name": tool_call.name, "input": tool_call.input},
                    )

                result = execute_tool(tool_call.name, tool_call.input)

                if on_step:
                    on_step(
                        "tool_result",
                        {"name": tool_call.name, "result": result},
                    )

                tool_result_blocks.append(
                    {
                        "type": "tool_result",
                        "tool_use_id": tool_call.id,
                        "content": json.dumps(result),
                    }
                )

            messages.append({"role": "user", "content": tool_result_blocks})
            continue

        if response.text:
            if on_step:
                on_step("final", response.text)
            return response.text

    if on_step:
        on_step("max_steps", MAX_STEPS_MESSAGE)
    return MAX_STEPS_MESSAGE
