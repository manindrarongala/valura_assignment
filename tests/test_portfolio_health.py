import pytest
from src.portfolio_health import analyze_portfolio

def test_empty_portfolio():
    user_data = {
        "user_id": "usr_004",
        "base_currency": "USD",
        "positions": [],
        "preferences": {"preferred_benchmark": "S&P 500"}
    }
    
    result = analyze_portfolio(user_data)
    
    assert result["concentration_risk"] is None
    assert result["performance"] is None
    assert result["benchmark_comparison"] is None
    assert len(result["observations"]) == 1
    assert result["observations"][0]["severity"] == "info"
    assert "no investments" in result["observations"][0]["text"].lower()
    assert "This is not investment advice" in result["disclaimer"]

def test_concentrated_portfolio(mocker):
    # Mock yfinance calls
    mocker.patch("src.portfolio_health._get_current_prices", return_value={
        "NVDA": 800.0,
        "VTI": 250.0,
        "VXUS": 60.0,
        "BND": 75.0,
        "AAPL": 175.0
    })
    mocker.patch("src.portfolio_health._get_1yr_benchmark_return", return_value=15.0)
    mocker.patch("src.portfolio_health._get_fx_rate", return_value=1.0)
    
    user_data = {
        "base_currency": "USD",
        "positions": [
            {"ticker": "NVDA", "quantity": 180, "avg_cost": 218.40, "currency": "USD"},
            {"ticker": "VTI", "quantity": 25, "avg_cost": 218.50, "currency": "USD"},
            {"ticker": "VXUS", "quantity": 30, "avg_cost": 56.10, "currency": "USD"},
            {"ticker": "BND", "quantity": 20, "avg_cost": 72.30, "currency": "USD"},
            {"ticker": "AAPL", "quantity": 8, "avg_cost": 168.20, "currency": "USD"}
        ],
        "preferences": {"preferred_benchmark": "S&P 500"}
    }
    
    result = analyze_portfolio(user_data)
    
    # Check concentration
    assert result["concentration_risk"]["flag"] == "high"
    assert result["concentration_risk"]["top_position_pct"] > 50.0
    
    # Check performance calculation (Total cost vs total value)
    # Value = 180*800 + 25*250 + 30*60 + 20*75 + 8*175 = 144000 + 6250 + 1800 + 1500 + 1400 = 154950
    # Cost = 180*218.4 + 25*218.5 + 30*56.1 + 20*72.3 + 8*168.2 = 39312 + 5462.5 + 1683 + 1446 + 1345.6 = 49249.1
    # Return = (154950 - 49249.1) / 49249.1 = 214.6%
    assert result["performance"]["total_return_pct"] > 200.0
    
    # Check benchmark
    assert result["benchmark_comparison"]["benchmark"] == "S&P 500"
    assert result["benchmark_comparison"]["benchmark_return_pct"] == 15.0
    assert result["benchmark_comparison"]["alpha_pct"] > 100.0
    
    # Observations
    assert any(obs["severity"] == "warning" and "high concentration" in obs["text"] for obs in result["observations"])

def test_multi_currency_portfolio(mocker):
    mocker.patch("src.portfolio_health._get_current_prices", return_value={
        "AAPL": 150.0,
        "SAP.DE": 100.0  # EUR
    })
    mocker.patch("src.portfolio_health._get_1yr_benchmark_return", return_value=10.0)
    
    # Mock EUR -> USD as 1.1
    def mock_fx(f_curr, t_curr):
        if f_curr == "EUR" and t_curr == "USD":
            return 1.1
        return 1.0
        
    mocker.patch("src.portfolio_health._get_fx_rate", side_effect=mock_fx)
    
    user_data = {
        "base_currency": "USD",
        "positions": [
            {"ticker": "AAPL", "quantity": 10, "avg_cost": 100.0, "currency": "USD"},
            {"ticker": "SAP.DE", "quantity": 10, "avg_cost": 80.0, "currency": "EUR"}
        ],
        "preferences": {"preferred_benchmark": "S&P 500"}
    }
    
    result = analyze_portfolio(user_data)
    
    # Cost = 10*100 (USD) + 10*80*1.1 (USD) = 1000 + 880 = 1880
    # Value = 10*150 (USD) + 10*100*1.1 (USD) = 1500 + 1100 = 2600
    # Return = 720 / 1880 = 38.3%
    
    assert abs(result["performance"]["total_return_pct"] - 38.3) < 0.2
