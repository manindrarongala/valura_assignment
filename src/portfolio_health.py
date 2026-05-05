import yfinance as yf
import pandas as pd
from typing import Dict, Any
from datetime import datetime, timedelta

def _get_fx_rate(from_currency: str, to_currency: str) -> float:
    if from_currency.upper() == to_currency.upper():
        return 1.0
    # yfinance uses pairs like "EURUSD=X"
    pair = f"{from_currency.upper()}{to_currency.upper()}=X"
    try:
        ticker = yf.Ticker(pair)
        # Fetch latest fast
        hist = ticker.history(period="1d")
        if not hist.empty:
            return float(hist["Close"].iloc[-1])
    except Exception:
        pass
    
    # Try inverse
    inverse_pair = f"{to_currency.upper()}{from_currency.upper()}=X"
    try:
        ticker = yf.Ticker(inverse_pair)
        hist = ticker.history(period="1d")
        if not hist.empty:
            return 1.0 / float(hist["Close"].iloc[-1])
    except Exception:
        pass

    # Fallback to 1.0 if both fail
    return 1.0

def _get_benchmark_ticker(benchmark_name: str) -> str:
    mapping = {
        "S&P 500": "^GSPC",
        "FTSE 100": "^FTSE",
        "Nikkei 225": "^N225",
        "MSCI World": "URTH" # ETF proxy for MSCI World
    }
    return mapping.get(benchmark_name, "^GSPC")

def _get_1yr_benchmark_return(benchmark_name: str) -> float:
    ticker_sym = _get_benchmark_ticker(benchmark_name)
    try:
        ticker = yf.Ticker(ticker_sym)
        hist = ticker.history(period="1y")
        if not hist.empty and len(hist) > 1:
            start_price = float(hist["Close"].iloc[0])
            end_price = float(hist["Close"].iloc[-1])
            return ((end_price - start_price) / start_price) * 100.0
    except Exception:
        pass
    return 0.0

def _get_current_prices(tickers: list) -> Dict[str, float]:
    if not tickers:
        return {}
    
    # yfinance download works best with space-separated string
    tickers_str = " ".join(set(tickers))
    try:
        data = yf.download(tickers_str, period="1d", progress=False)
        prices = {}
        if len(tickers) == 1:
            if not data.empty and "Close" in data:
                prices[tickers[0]] = float(data["Close"].iloc[-1])
        else:
            if not data.empty and "Close" in data:
                close_data = data["Close"]
                for t in tickers:
                    if t in close_data:
                        prices[t] = float(close_data[t].iloc[-1])
        return prices
    except Exception:
        return {}

def analyze_portfolio(user_profile: Dict[str, Any]) -> Dict[str, Any]:
    positions = user_profile.get("positions", [])
    base_currency = user_profile.get("base_currency", "USD")
    preferences = user_profile.get("preferences", {})
    benchmark_name = preferences.get("preferred_benchmark", "S&P 500")
    
    # 1. Handle empty portfolio
    if not positions:
        return {
            "concentration_risk": None,
            "performance": None,
            "benchmark_comparison": None,
            "observations": [
                {"severity": "info", "text": "You currently have no investments. A good starting point is a diversified ETF to begin building your wealth."}
            ],
            "disclaimer": "This is not investment advice. Please consult a financial advisor or conduct your own research before investing."
        }

    # 2. Fetch market data
    tickers = [p["ticker"] for p in positions]
    current_prices = _get_current_prices(tickers)
    
    # Fetch FX rates if needed
    fx_rates = {}
    for p in positions:
        curr = p.get("currency", "USD")
        if curr != base_currency and curr not in fx_rates:
            fx_rates[curr] = _get_fx_rate(curr, base_currency)

    # 3. Calculate value and performance
    total_value = 0.0
    total_cost = 0.0
    weighted_holding_days = 0.0
    now = datetime.now()
    
    position_stats = []
    
    for p in positions:
        ticker = p["ticker"]
        qty = float(p.get("quantity", 0))
        avg_cost = float(p.get("avg_cost", 0))
        curr = p.get("currency", "USD")
        
        # fallback to avg_cost if price fetch failed
        price_in_local = current_prices.get(ticker, avg_cost)
        
        fx = fx_rates.get(curr, 1.0) if curr != base_currency else 1.0
        
        current_value_base = qty * price_in_local * fx
        cost_basis_base = qty * avg_cost * fx
        
        total_value += current_value_base
        total_cost += cost_basis_base
        
        # Holding period for annualized return approximation
        purchased_at = p.get("purchased_at")
        days_held = 365
        if purchased_at:
            try:
                p_date = datetime.strptime(purchased_at, "%Y-%m-%d")
                days_held = max(1, (now - p_date).days)
            except ValueError:
                pass
                
        position_stats.append({
            "ticker": ticker,
            "value": current_value_base,
            "cost": cost_basis_base,
            "days_held": days_held
        })

    if total_cost == 0:
        total_cost = 1.0 # prevent div by zero
        
    portfolio_return_pct = ((total_value - total_cost) / total_cost) * 100.0
    
    # Calculate weights and concentration
    if total_value > 0:
        for stat in position_stats:
            stat["weight"] = stat["value"] / total_value
            weighted_holding_days += stat["days_held"] * stat["weight"]
    else:
        for stat in position_stats:
            stat["weight"] = 0
            
    # Sort by weight descending
    position_stats.sort(key=lambda x: x["weight"], reverse=True)
    
    top_position_pct = (position_stats[0]["weight"] * 100.0) if position_stats else 0.0
    top_ticker = position_stats[0]["ticker"] if position_stats else ""
    top_3_positions_pct = sum(s["weight"] for s in position_stats[:3]) * 100.0 if position_stats else 0.0
    
    flag = "low"
    if top_position_pct > 50:
        flag = "high"
    elif top_position_pct > 30:
        flag = "moderate"
        
    # Annualized return
    avg_years_held = weighted_holding_days / 365.0
    if avg_years_held > 0 and total_cost > 0:
        try:
            annualized_return_pct = (((total_value / total_cost) ** (1 / avg_years_held)) - 1) * 100.0
        except Exception:
            annualized_return_pct = portfolio_return_pct
    else:
        annualized_return_pct = portfolio_return_pct

    # 4. Benchmark Comparison
    bench_return_pct = _get_1yr_benchmark_return(benchmark_name)
    alpha_pct = portfolio_return_pct - bench_return_pct

    # 5. Observations
    observations = []
    
    # Concentration observation
    if flag == "high":
        observations.append({
            "severity": "warning", 
            "text": f"{top_position_pct:.1f}% of your portfolio is concentrated in {top_ticker}. This high concentration exposes you to significant downside risk if that specific asset drops."
        })
    elif flag == "moderate":
        observations.append({
            "severity": "info", 
            "text": f"Your largest holding is {top_ticker} at {top_position_pct:.1f}% of your portfolio. Consider diversifying to reduce concentration risk."
        })
    else:
        observations.append({
            "severity": "success", 
            "text": "Your portfolio is well diversified across multiple holdings, which helps balance risk."
        })
        
    # Performance observation
    if alpha_pct > 2.0:
        observations.append({
            "severity": "success",
            "text": f"Your portfolio is outperforming the {benchmark_name} by {alpha_pct:.1f}%, suggesting strong performance."
        })
    elif alpha_pct < -2.0:
        observations.append({
            "severity": "warning",
            "text": f"Your portfolio is underperforming the {benchmark_name} by {abs(alpha_pct):.1f}%, suggesting potential room for improvement."
        })
    else:
        observations.append({
            "severity": "info",
            "text": f"Your portfolio's performance is closely tracking the {benchmark_name}."
        })

    import math
    
    def safe_float(val, default=0.0):
        if val is None:
            return default
        try:
            f = float(val)
            if math.isnan(f) or math.isinf(f):
                return default
            return f
        except Exception:
            return default

    return {
        "concentration_risk": {
            "top_position_pct": round(safe_float(top_position_pct), 1),
            "top_3_positions_pct": round(safe_float(top_3_positions_pct), 1),
            "flag": flag
        },
        "performance": {
            "total_return_pct": round(safe_float(portfolio_return_pct), 1),
            "annualized_return_pct": round(safe_float(annualized_return_pct), 1)
        },
        "benchmark_comparison": {
            "benchmark": benchmark_name,
            "portfolio_return_pct": round(safe_float(portfolio_return_pct), 1),
            "benchmark_return_pct": round(safe_float(bench_return_pct), 1),
            "alpha_pct": round(safe_float(alpha_pct), 1)
        },
        "observations": observations,
        "disclaimer": "This is not investment advice. Please consult a financial advisor or conduct your own research before making investment decisions."
    }
