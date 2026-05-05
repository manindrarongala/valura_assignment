# Valura AI — Portfolio Agent Microservice

An AI-powered wealth management microservice designed to help users build, monitor, grow, and protect their investment portfolios.

## Setup and Installation

**Requirements:** Python 3.11+, an OpenAI or Groq API key.

1. **Clone the repository and enter the directory:**
   ```bash
   git clone <your-repo-url>
   cd <repo-name>
   ```

2. **Set up a virtual environment:**
   ```bash
   python -m venv venv
   # macOS/Linux:
   source venv/bin/activate
   # Windows:
   venv\Scripts\activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Configure Environment Variables:**
   Copy the `.env.example` file to create your local `.env`:
   ```bash
   cp .env.example .env
   ```
   Add your API keys to the `.env` file (see required variables below).

## Environment Variables

The application expects the following variables to be set in your `.env` file:

- `OPENAI_API_KEY`: Fallback LLM provider key for intent classification.
- `GROQ_API_KEY`: (Recommended) Primary LLM provider key for fast, low-cost intent classification using Llama 3.
- `LLM_MODEL`: The model string to use (defaults to `llama-3.1-8b-instant` if Groq is used, otherwise `gpt-4o-mini`).

*Note: `DATABASE_URL` from the example is optional for this iteration as memory is handled in-memory.*

## Running the Application

Start the FastAPI streaming server with Uvicorn:

```bash
uvicorn src.main:app --reload
```

The server will be available at `http://127.0.0.1:8000`. It serves a simple frontend at the root `/` to test the streaming endpoints.

### Running Tests

```bash
pytest tests/ -v
```

## Architecture and Design Decisions

Here are some of the key, non-obvious technical decisions made during the implementation:

1. **Hybrid Local Safety Guard:** 
   The safety guard (`src/safety.py`) evaluates inputs synchronously *before* they hit the LLM. It uses regex patterns and keyword matching to catch harmful financial requests (insider trading, market manipulation) and scores them against educational signals. This ensures zero latency and zero LLM cost for obvious safety violations.

2. **Groq for Low-Latency Classification:** 
   Intent classification (`src/classifier.py`) uses Groq (`llama-3.1-8b-instant`) by default instead of OpenAI to drastically reduce latency and cost. Fast routing is critical for user experience, and Groq's inference speeds make the classification layer virtually unnoticeable. The application falls back seamlessly to OpenAI's `gpt-4o-mini` if a Groq key is absent.

3. **In-Memory Conversation Persistence:**
   For this microservice, conversation histories and user profiles are stored in-memory (and via local mock JSON files in `fixtures/users/`). This minimizes dependencies (no Postgres/Redis required locally) while still perfectly validating the SSE logic and agent state transitions.

4. **Live Market Data via `yfinance`:**
   The Portfolio Health agent fetches live prices and benchmark comparisons using `yfinance`. It converts foreign assets to the user's base currency using live FX rates dynamically. It falls back gracefully to cost-basis data if the yfinance fetch fails or times out.

## Defence Video

[**Link to Defence Video**] (Insert URL here)
*(Please replace the placeholder with the link to your video presentation).*
