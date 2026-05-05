import pytest
import json
from httpx import AsyncClient, ASGITransport
from src.main import app
from src.safety import SafetyVerdict

@pytest.mark.asyncio
async def test_api_safety_block(mocker):
    mocker.patch("src.main.check_safety", return_value=SafetyVerdict(blocked=True, category="fraud", message="Blocked"))
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/query", json={
            "session_id": "123",
            "query": "How to commit fraud",
            "user_id": "usr_001"
        })
        
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "This request is not allowed" in response.text

@pytest.mark.asyncio
async def test_api_portfolio_health_routing(mocker):
    mocker.patch("src.main.check_safety", return_value=SafetyVerdict(blocked=False, category=None, message="OK"))
    mocker.patch("src.main.classify", return_value={
        "agent": "portfolio_health",
        "intent": "check_health",
        "entities": {}
    })
    mocker.patch("src.main.analyze_portfolio", return_value={"concentration_risk": "high"})
    mocker.patch("src.main.load_user_profile", return_value={})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/query", json={
            "session_id": "123",
            "query": "How is my portfolio doing?",
            "user_id": "usr_001"
        })
        
        assert response.status_code == 200
        assert "event: status" in response.text
        assert "Analyzing your request" in response.text
        assert "event: message" in response.text
        
        # Verify JSON payload inside message event
        lines = response.text.split("\n")
        data_line = next(line for line in lines if line.startswith("data:") and "portfolio_health" in line)
        data_json = json.loads(data_line.replace("data: ", ""))
        
        assert data_json["agent"] == "portfolio_health"
        assert data_json["data"]["concentration_risk"] == "high"

@pytest.mark.asyncio
async def test_api_stub_routing(mocker):
    mocker.patch("src.main.check_safety", return_value=SafetyVerdict(blocked=False, category=None, message="OK"))
    mocker.patch("src.main.classify", return_value={
        "agent": "market_research",
        "intent": "get_price",
        "entities": {"tickers": ["AAPL"]}
    })
    mocker.patch("src.main.load_user_profile", return_value={})
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/query", json={
            "session_id": "123",
            "query": "What is the price of AAPL?",
            "user_id": "usr_001"
        })
        
        assert response.status_code == 200
        assert "event: message" in response.text
        
        lines = response.text.split("\n")
        data_line = next(line for line in lines if line.startswith("data:") and "market_research" in line)
        data_json = json.loads(data_line.replace("data: ", ""))
        
        assert data_json["status"] == "not_implemented"
        assert data_json["agent"] == "market_research"
        assert data_json["message"] == "This agent is not implemented yet."

@pytest.mark.asyncio
async def test_api_timeout(mocker):
    import asyncio
    mocker.patch("src.main.check_safety", return_value=SafetyVerdict(blocked=False, category=None, message="OK"))
    
    # Mock classify to sleep longer than the timeout
    async def slow_classify(*args, **kwargs):
        await asyncio.sleep(6.0)
        return {}
        
    mocker.patch("src.main.classify", side_effect=slow_classify)
    mocker.patch("src.main.load_user_profile", return_value={})
    
    # We override the timeout in main for the test so it doesn't take 5.5s
    mocker.patch("src.main.asyncio.wait_for", side_effect=asyncio.TimeoutError())
    
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        response = await client.post("/query", json={
            "session_id": "123",
            "query": "This will timeout",
            "user_id": "usr_001"
        })
        
        assert response.status_code == 200
        assert "event: error" in response.text
        assert "Request timed out" in response.text
