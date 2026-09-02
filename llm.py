"""Claude Messages API client."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ToolCall:
    """Normalized tool request from an LLM turn."""

    id: str
    name: str
    input: dict


@dataclass
class LLMResult:
    """Normalized result of one LLM turn."""

    text: str | None
    tool_calls: list[ToolCall] = field(default_factory=list)
    raw_assistant_content: list = field(default_factory=list)

    @property
    def has_tool_calls(self) -> bool:
        return len(self.tool_calls) > 0


class LLMClient(Protocol):
    """Structural interface implemented by AnthropicClient."""

    def complete(
        self,
        messages: list[dict],
        tool_schemas: list[dict],
        system: str | None = None,
    ) -> LLMResult: ...


class AnthropicClient:
    """Claude Messages API client."""

    def __init__(self, api_key: str, model: str) -> None:
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY is required. Set it in .env.")

        import anthropic

        self._client = anthropic.Anthropic(api_key=api_key)
        self._model = model

    def complete(
        self,
        messages: list[dict],
        tool_schemas: list[dict],
        system: str | None = None,
    ) -> LLMResult:
        """Send messages and tool schemas to Claude and return a normalized result."""
        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": 4096,
            "messages": messages,
            "tools": tool_schemas,
        }
        if system:
            kwargs["system"] = system

        response = self._client.messages.create(**kwargs)

        tool_calls: list[ToolCall] = []
        text_parts: list[str] = []
        raw_content: list[dict] = []

        for block in response.content:
            if block.type == "text":
                text_parts.append(block.text)
                raw_content.append({"type": "text", "text": block.text})
            elif block.type == "tool_use":
                tool_calls.append(
                    ToolCall(id=block.id, name=block.name, input=block.input)
                )
                raw_content.append(
                    {
                        "type": "tool_use",
                        "id": block.id,
                        "name": block.name,
                        "input": block.input,
                    }
                )

        text = "".join(text_parts) if text_parts else None
        return LLMResult(
            text=text,
            tool_calls=tool_calls,
            raw_assistant_content=raw_content,
        )
