import pytest
import json
from src.classifier import classify
from unittest.mock import AsyncMock

@pytest.mark.asyncio
async def test_classifier_fallback_on_error(mocker):
    # Mock the LLM client to raise an exception
    mocker.patch("src.classifier.client.chat.completions.create", side_effect=Exception("API Error"))
    
    result = await classify("test query")
    
    assert result["agent"] == "general_support"
    assert result["intent"] == "unknown"
    assert result["entities"] == {}
    assert result["safety"]["is_risky"] is False

@pytest.mark.asyncio
async def test_classifier_successful_response(mocker):
    from unittest.mock import MagicMock, AsyncMock
    # Mock successful LLM response
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = json.dumps({
        "agent": "portfolio_health",
        "intent": "portfolio_query",
        "entities": {"tickers": ["NVDA"]},
        "safety": {"is_risky": False, "reason": None}
    })
    mock_response.choices = [MagicMock(message=mock_message)]
    
    mocker.patch("src.classifier.client.chat.completions.create", new_callable=AsyncMock, return_value=mock_response)
    
    result = await classify("How much do I own?")
    
    assert result["agent"] == "portfolio_health"
    assert result["intent"] == "portfolio_query"
    assert "NVDA" in result["entities"]["tickers"]
    assert result["safety"]["is_risky"] is False

@pytest.mark.asyncio
async def test_classifier_invalid_json_fallback(mocker):
    from unittest.mock import MagicMock, AsyncMock
    # Mock invalid JSON string from LLM
    mock_response = MagicMock()
    mock_message = MagicMock()
    mock_message.content = "This is not valid JSON"
    mock_response.choices = [MagicMock(message=mock_message)]
    
    mocker.patch("src.classifier.client.chat.completions.create", new_callable=AsyncMock, return_value=mock_response)
    
    result = await classify("What is AAPL?")
    
    assert result["agent"] == "general_support"
    assert result["intent"] == "unknown"
