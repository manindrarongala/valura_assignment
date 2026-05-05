import asyncio
import json
from pathlib import Path
from fastapi import FastAPI, Request
from pydantic import BaseModel
from sse_starlette.sse import EventSourceResponse

from src.safety import check_safety
from src.memory import get_history, add_message
from src.classifier import classify
from src.portfolio_health import analyze_portfolio

from fastapi.responses import FileResponse

app = FastAPI(title="Valura AI", description="AI agent ecosystem microservice")

@app.get("/")
async def root():
    index_path = Path(__file__).parent / "static" / "index.html"
    return FileResponse(index_path)

class QueryRequest(BaseModel):
    session_id: str
    query: str
    user_id: str

def load_user_profile(user_id: str) -> dict:
    fixtures_dir = Path(__file__).parent.parent / "fixtures" / "users"
    if fixtures_dir.exists():
        for file_path in fixtures_dir.glob("*.json"):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    if data.get("user_id") == user_id:
                        return data
            except Exception:
                continue
                
    # Fallback to empty if not found
    return {
        "user_id": user_id,
        "base_currency": "USD",
        "positions": [],
        "preferences": {"preferred_benchmark": "S&P 500"}
    }

async def process_pipeline(req: QueryRequest):
    user_profile = load_user_profile(req.user_id)
    history = get_history(req.session_id)
    
    # Run classifier
    classification = await classify(req.query, history)
    
    # Memory: add user query
    add_message(req.session_id, "user", req.query)
    
    # Route
    agent = classification.get("agent")
    if agent == "portfolio_health":
        result = analyze_portfolio(user_profile)
        final_data = {
            "agent": "portfolio_health",
            "data": result
        }
    else:
        # Stub
        final_data = {
            "status": "not_implemented",
            "agent": agent,
            "intent": classification.get("intent", "unknown"),
            "entities": classification.get("entities", {}),
            "message": "This agent is not implemented yet."
        }
        
    # Memory: add assistant response summary
    add_message(req.session_id, "assistant", json.dumps(final_data))
    
    return final_data

@app.post("/query")
async def query_endpoint(req: QueryRequest):
    async def event_generator():
        try:
            # 1. Safety check (synchronous)
            safety_result = check_safety(req.query)
            if safety_result.blocked:
                yield {
                    "event": "error",
                    "data": "This request is not allowed because it violates safety policies."
                }
                return
                
            # Optional processing chunk
            yield {
                "event": "status",
                "data": "Analyzing your request..."
            }
            
            # 2. Run pipeline with timeout
            result = await asyncio.wait_for(process_pipeline(req), timeout=5.5)
            
            # 3. Yield final chunk
            yield {
                "event": "message",
                "data": json.dumps(result)
            }
            
        except asyncio.TimeoutError:
            yield {
                "event": "error",
                "data": "Request timed out"
            }
        except Exception as e:
            yield {
                "event": "error",
                "data": "Something went wrong"
            }
            
    return EventSourceResponse(event_generator())
