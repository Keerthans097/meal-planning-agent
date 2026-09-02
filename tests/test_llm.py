import pytest

from llm import AnthropicClient


def test_anthropic_client_requires_api_key():
    with pytest.raises(ValueError, match="ANTHROPIC_API_KEY"):
        AnthropicClient(api_key="", model="claude-sonnet-5")


def test_anthropic_client_stores_model_without_network_call():
    client = AnthropicClient(api_key="test-key", model="claude-sonnet-5")

    assert client._model == "claude-sonnet-5"
