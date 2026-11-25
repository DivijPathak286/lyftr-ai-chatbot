# Lyftr AI — LLM Chatbot with Key Failover and Response Caching

A full-stack conversational AI application built using React, FastAPI, LiteLLM, and SQLite. The application demonstrates multi-turn conversational memory, automatic provider API-key failover, response caching, per-request token metadata, and configurable failure simulation.

## 1. Live URLs

- Frontend: `ADD_DEPLOYED_FRONTEND_URL`
- Backend: `ADD_DEPLOYED_BACKEND_URL`
- Health: `ADD_DEPLOYED_BACKEND_URL/health`

Replace these placeholders with the public deployment URLs before submission.

## 2. Run locally

### Requirements

- Docker Desktop / Docker Engine and Docker Compose
- API keys for a supported LLM provider
- Node.js 22+ and Python 3.12+ for running without Docker

### Using Docker

1. Copy `.env.example` to `.env`.
2. Configure your provider API keys and model.
3. Start the application:

   ```bash
   docker compose up -d --build
   ```

4. Open the frontend at `http://localhost:3000`.
5. Access the backend at `http://localhost:8000`.
6. Access API documentation at `http://localhost:8000/docs`.

Stop the application:

```bash
docker compose down
```

The named Docker volume `app_data` stores SQLite database files under `/data`, allowing conversation history to persist across container restarts.

### Without Docker

**Backend**

```bash
cd backend
python -m venv .venv
```

Activate the virtual environment:

```bash
# Windows
.venv\Scripts\activate

# macOS/Linux
source .venv/bin/activate
```

Install dependencies:

```bash
pip install -r requirements.txt
```

Configure the required environment variables and start the backend:

```bash
uvicorn app.main:app --reload --port 8000
```

**Frontend**

Open another terminal:

```bash
cd frontend
npm install
npm run dev
```

The Vite development server normally runs at `http://localhost:5173`.

## 3. Design decisions

### API-key failover

The backend supports multiple configured provider API keys and attempts them in sequence. Provider failures, including rate limits and server errors, can trigger fallback attempts.

The response metadata identifies the successful key without exposing its secret value.

### Response caching

LiteLLM caching is used to reuse eligible previous model responses and reduce unnecessary inference requests.

The cache distinguishes requests based on their model and message inputs. Cache responses are identified using `LLM_CACHE`, while new model requests are identified using `LIVE_INFERENCE`.

The current local cache is in-memory and is reset when the backend process restarts.

### SQLite session storage

SQLite stores conversations using session IDs. User and assistant messages are associated with their respective sessions, and conversation history is reconstructed for subsequent requests.

A fresh session starts whenever the frontend page is loaded. Previous conversations remain accessible through the conversation history sidebar.

The Docker named volume ensures database persistence across container restarts.

### Token and latency metadata

Each assistant response includes metadata such as:

- Resolution source
- Model name
- Latency in milliseconds
- Input tokens
- Output tokens
- Provider key identifier
- Number of fallback attempts

## 4. Verification

### Backend health

```bash
curl http://localhost:8000/health
```

### Backend automated tests

Run from the project root:

```bash
python -m pytest backend/tests -v
```

### Manual verification

The following scenarios have been tested:

- Backend health endpoint and API-key configuration.
- Automatic failover when the first API key returns a simulated HTTP 429.
- HTTP 503 response when all configured keys fail.
- Failed requests are not stored in conversation history.
- Cache hit for an identical request in a new session.
- Live inference for a different request.
- Per-request token and latency metadata.
- Multi-turn conversational memory.
- SQLite conversation history retrieval.
- Frontend metadata display and required test identifiers.
- System prompt functionality.
- Frontend error handling for HTTP 503.
- New session creation on page refresh.
- Previous conversation restoration through the sidebar.
- Database persistence across Docker container restarts.

Failure simulation can be enabled using `ENABLE_FAILURE_SIMULATION=true` and tested through the `X-Simulate-Failure` request header.

## 5. Setup Used

- Editor: Visual Studio Code
- AI assistance: ChatGPT
- Backend: Python 3.12, FastAPI
- Frontend: React, Vite, Node.js 22
- LLM integration: LiteLLM and Google Gemini
- Database: SQLite
- Containerization: Docker and Docker Compose
- Testing: Pytest and HTTPX

## 6. Bonus features (if any)

- Session-level system prompt configuration.
- Conversation history sidebar.
- New conversation functionality.
- Configurable provider failure simulation.
- Responsive dark-themed interface.
- SQLite-based conversation persistence.
- Backend health monitoring.
- Per-message response metadata.
- Multi-stage Docker builds.