# ai-qr-ordering
AI-powered QR code ordering system for restaurants. Customers scan, speak or type their order, and an LLM parses it into structured items.

## Prerequisites

- Python 3.11+
- Node.js 18+
- Docker & Docker Compose (for Postgres and Redis)

## Setup

1. Copy `.env.example` to `.env` and fill in your API keys:
   ```
   cp .env.example .env
   ```

2. Start Postgres and Redis:
   ```
   docker-compose up -d db redis
   ```

3. Install backend dependencies and run migrations:
   ```
   cd backend
   poetry install
   python manage.py migrate
   ```

4. Install frontend dependencies:
   ```
   cd frontend
   npm install
   ```

## Running

Start the backend (port 5005):
```
cd backend
./manage.py runserver 5005
```

Start the frontend (port 3001):
```
cd frontend
npm run dev -- -p 3001
```

| Service  | URL                     |
|----------|-------------------------|
| Backend  | http://localhost:5005   |
| Frontend | http://localhost:3001   |
