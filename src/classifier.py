import os
import json
import logging
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field, ValidationError
from openai import AsyncOpenAI
import dotenv

dotenv.load_dotenv()

# We configure the OpenAI client to point to Groq if a GROQ_API_KEY is present,
# otherwise fallback to standard OpenAI.
api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
base_url = "https://api.groq.com/openai/v1" if os.getenv("GROQ_API_KEY") else None

client = AsyncOpenAI(api_key=api_key, base_url=base_url)

LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant" if os.getenv("GROQ_API_KEY") else "gpt-4o-mini")

logger = logging.getLogger(__name__)

class SafetyInfo(BaseModel):
    is_risky: bool = Field(default=False)
    reason: Optional[str] = Field(default=None)

class ClassifierOutput(BaseModel):
    agent: str
    intent: str
    entities: Dict[str, Any] = Field(default_factory=dict)
    safety: SafetyInfo = Field(default_factory=SafetyInfo)

SYSTEM_PROMPT = """
You are an expert financial intent classifier and router for the Valura AI wealth management platform.
Your job is to analyze the user's latest query, considering the conversation history if necessary, and output a structured JSON response.

You must map the query to exactly ONE of the following agents:
1. "portfolio_health": structured assessment of the user's portfolio (concentration, performance, benchmarking, observations).
2. "market_research": factual/recent info about an instrument, sector, or market event.
3. "investment_strategy": advice/strategy questions: should I buy/sell/rebalance, allocation guidance.
4. "financial_planning": long-term planning: retirement, goals, savings rate.
5. "financial_calculator": deterministic numerical computation: DCA returns, mortgage, tax, future value, FX conversion.
6. "risk_assessment": risk metrics, exposure analysis, what-if scenarios.
7. "product_recommendation": recommend specific products/funds matching user profile.
8. "predictive_analysis": forward-looking analysis: forecasts, trend extrapolation.
9. "customer_support": platform issues, account questions, how-to-use-app.
10. "general_query": educational, conversational, definitions, greetings, or anything else.

Entity Extraction:
Extract entities from the query into the `entities` object. Only include relevant fields from this vocabulary:
- "tickers": array of strings (e.g. ["AAPL", "NVDA", "ASML.AS"])
- "amount": number
- "currency": ISO 4217 string (e.g. "USD", "EUR")
- "rate": decimal (e.g. 0.08 for 8%)
- "period_years": integer
- "frequency": "daily", "weekly", "monthly", "yearly"
- "horizon": "6_months", "1_year", "5_years"
- "time_period": "today", "this_week", "this_month", "this_year"
- "topics": array of strings
- "sectors": array of strings
- "index": string (e.g. "S&P 500", "FTSE 100")
- "action": "buy", "sell", "hold", "hedge", "rebalance"
- "goal": "retirement", "education", "house", "FIRE", "emergency_fund"

Informational Safety:
Set `safety.is_risky` to true only if the query suggests dangerous financial behavior, otherwise false.

Instructions:
1. You MUST return ONLY valid JSON matching this schema:
{
  "agent": "...",
  "intent": "...",
  "entities": {...},
  "safety": {
    "is_risky": false,
    "reason": null
  }
}
2. Use the conversation history to resolve pronouns and context (e.g., if history talks about NVDA and new query is "How much do I own?", ticker is NVDA and agent is portfolio_health).
3. Do NOT include markdown blocks like ```json ... ```, just output the raw JSON.
"""

async def classify(query: str, history: List[Dict[str, str]] = None) -> Dict[str, Any]:
    if history is None:
        history = []
        
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    
    # Append limited history (e.g., last 3-5 messages)
    for msg in history[-5:]:
        # Ensure only 'user' or 'assistant' roles are passed to the model
        if msg.get("role") in ["user", "assistant"]:
            messages.append({"role": msg["role"], "content": msg.get("content", "")})
            
    # Append current query
    messages.append({"role": "user", "content": query})

    fallback_response = {
        "agent": "general_support",
        "intent": "unknown",
        "entities": {},
        "safety": {"is_risky": False, "reason": None}
    }

    try:
        response = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            response_format={"type": "json_object"},
            temperature=0.0,
            max_tokens=500
        )
        
        raw_json = response.choices[0].message.content
        data = json.loads(raw_json)
        
        # Validate against schema
        validated_data = ClassifierOutput(**data).model_dump()
        return validated_data
        
    except (json.JSONDecodeError, ValidationError) as e:
        logger.error(f"Failed to parse LLM response: {e}")
        return fallback_response
    except Exception as e:
        logger.error(f"LLM API error: {e}")
        return fallback_response
