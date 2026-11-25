# Lyftr AI Chatbot — LLM Chatbot with Key Failover and Response Caching

A full-stack AI chatbot built using React, FastAPI, LiteLLM, and SQLite. It supports multi-turn conversations, automatic API-key failover, response caching, and session history.

## 1. Live URLs

- **Frontend:** https://lyftr-ai-chatbot-frontend-4rys.onrender.com
- **Backend:** https://lyftr-ai-chatbot-lbcz.onrender.com
- **Backend Health:** https://lyftr-ai-chatbot-lbcz.onrender.com/health
- **GitHub Repository:** https://github.com/DivijPathak286/lyftr-ai-chatbot

## 2. Run locally

### Requirements

- Python 3.12+
- Node.js 22+
- Docker Desktop and Docker Compose
- Gemini API keys (at least two for failover testing)

### Using Docker

1. Clone the repository:

   ```bash
   git clone https://github.com/DivijPathak286/lyftr-ai-chatbot.git
   cd lyftr-ai-chatbot
   ```

2. Create your environment file:

   ```bash
   cp .env.example .env
   ```

3. Add your API keys and configuration to `.env`.

4. Start the application:

   ```bash
   docker compose up --build -d
   ```

5. Access the application:

   - Frontend: http://localhost:3000
   - Backend: http://localhost:8000
   - API documentation: http://localhost:8000/docs

6. Stop the application:

   ```bash
   docker compose down
   ```

### Without Docker

Backend:

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment and install dependencies:

```bash
pip install -r requirements.txt
```

Run the backend:

```bash
uvicorn app.main:app --reload
```

Frontend (in another terminal):

```bash
cd frontend
npm install
npm run dev
```

## 3. Design decisions

### API-key failover

- Supports multiple Gemini API keys.
- Automatically attempts another key when a provider request fails.
- Handles rate limits and provider failures.
- Includes a failure simulation mechanism for testing failover.

### Response caching

- Uses LiteLLM's local cache.
- Cache identity considers the model and complete message history.
- Identical requests can reuse cached responses.
- Cache hits and live inference are identified in response metadata.

### SQLite session storage

- Stores conversation sessions and message history in SQLite.
- Supports retrieving previous conversations.
- Stores assistant response metadata alongside messages.
- Docker uses a named volume for database persistence.

### Token and latency metadata

Assistant responses include:

- Resolution source
- Model name
- Response latency
- Input tokens
- Output tokens

## 4. Verification

### Backend health

Verified deployed health endpoint:

```text
GET /health
```

Expected response:

```json
{
  "status": "ok",
  "keys_configured": 2,
  "cache_enabled": true
}
```

### Backend automated tests

Run:

```bash
cd backend
python -m pytest -v
```

### Manual verification

The following functionality has been verified:

- Backend health endpoint returns HTTP 200.
- Frontend and backend are successfully connected.
- Live chatbot requests return assistant responses.
- All five required response metadata fields are displayed.
- Multi-turn conversations work.
- Optional system prompts work.
- API-key failover and failure simulation were tested locally.
- Cache behavior was verified locally.
- SQLite session history and Docker volume persistence were tested locally.

Note: Deployed cache-hit behavior is still undergoing verification.

## 5. Setup Used

### Backend

- Python 3.12
- FastAPI
- LiteLLM
- SQLite
- Pydantic
- Uvicorn

### Frontend

- React
- Vite
- JavaScript
- CSS

### Deployment and Infrastructure

- Docker
- Docker Compose
- Render
- GitHub

## 6. Bonus features (if any)

- Conversation history sidebar.
- New conversation on page refresh.
- Optional system prompt configuration.
- Failure simulation controls.
- Response metadata display.
- Multi-key automatic failover.
- Docker-based deployment.
- Interactive API documentation through Swagger UI.