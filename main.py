"""CLI entrypoint: load configuration, create an LLM client, and run the agent."""

import json
import os
import sys
from typing import Any

from dotenv import load_dotenv

from agent import run_agent
from llm import AnthropicClient


def load_config() -> dict:
    """Load runtime settings from environment / .env."""
    load_dotenv(override=True)
    return {
        "api_key": os.getenv("ANTHROPIC_API_KEY", ""),
        "model": os.getenv("ANTHROPIC_MODEL", "claude-sonnet-5"),
        "max_steps": int(os.getenv("MAX_AGENT_STEPS", "8")),
    }


def read_user_request() -> str:
    """Read a multi-line request from stdin until a blank line or EOF."""
    print("Enter your meal request (blank line to finish):")
    lines: list[str] = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if not line.strip() and lines:
            break
        if line.strip():
            lines.append(line)
    return "\n".join(lines).strip()


def _truncate(value: Any, limit: int = 300) -> str:
    """Truncate long values for terminal logging."""
    text = value if isinstance(value, str) else json.dumps(value, indent=2)
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


def make_logger() -> Any:
    """Return an on_step callback that prints agent progress to stdout."""

    def on_step(event: str, payload: Any) -> None:
        if event == "step":
            print(f"\n[STEP {payload}]")
        elif event == "tool_call":
            print(f"[TOOL CALL] {payload['name']}")
            print(f"  args: {_truncate(payload['input'])}")
        elif event == "tool_result":
            print(f"[TOOL RESULT] {payload['name']}")
            print(f"  result: {_truncate(payload['result'])}")
        elif event == "final":
            print("\n[AGENT]")
            print(payload)
        elif event == "max_steps":
            print("\n[AGENT]")
            print(payload)

    return on_step


def main() -> None:
    config = load_config()

    user_request = read_user_request()
    if not user_request:
        print("No request provided. Exiting.")
        return

    print(f"\n[USER]\n{user_request}\n")
    print(
        f"[CONFIG] ANTHROPIC_MODEL={config['model']}, "
        f"MAX_AGENT_STEPS={config['max_steps']}"
    )

    try:
        llm_client = AnthropicClient(
            api_key=config["api_key"],
            model=config["model"],
        )
    except ValueError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1) from exc

    run_agent(
        user_request=user_request,
        llm_client=llm_client,
        max_steps=config["max_steps"],
        on_step=make_logger(),
    )


if __name__ == "__main__":
    main()
