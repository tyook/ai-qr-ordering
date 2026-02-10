# AI QR Ordering - Backend

Django REST API for the AI-powered QR code ordering system. Handles authentication, restaurant/menu management, LLM-based order parsing, and real-time kitchen updates via WebSocket.

## Tech Stack

- **Python** 3.12 / **Django** 4.2
- **Django REST Framework** + **SimpleJWT** (authentication)
- **Django Channels** + **Daphne** (WebSocket / ASGI)
- **PostgreSQL** 16 (database)
- **Redis** 7 (Channels layer)
- **OpenAI SDK** (LLM order parsing)
- **Poetry** (dependency management)

## Prerequisites

- Python 3.11+
- PostgreSQL 16
- Redis 7
- [Poetry](https://python-poetry.org/docs/#installation)

The easiest way to get PostgreSQL and Redis running is via the root `docker-compose.yml`:

```bash
# From the project root (ai-qr-ordering/)
docker compose up -d db redis
```

This starts PostgreSQL on **port 5433** and Redis on **port 6380** (non-default ports to avoid conflicts with other projects).

## Quick Start

```bash
# 1. Install dependencies
cd backend
poetry install

# 2. Copy env file (if not done already) and edit as needed
cp ../.env.example ../.env

# 3. Run migrations
POSTGRES_HOST=localhost python manage.py migrate

# 4. Create a superuser (optional)
POSTGRES_HOST=localhost python manage.py createsuperuser

# 5. Start the dev server
POSTGRES_HOST=localhost python manage.py runserver
```

The API will be available at `http://localhost:5005`.

> **Note:** `POSTGRES_HOST=localhost` is needed when running outside Docker since the `.env` file may have `POSTGRES_HOST=db` for the Docker network. Alternatively, ensure your `.env` has `POSTGRES_HOST=localhost`.

## Environment Variables

Configured via `.env` in the project root (read by `python-decouple`):

| Variable | Default | Description |
|---|---|---|
| `DJANGO_SECRET_KEY` | `insecure-dev-key-change-me` | Django secret key |
| `DJANGO_DEBUG` | `True` | Debug mode |
| `DJANGO_ALLOWED_HOSTS` | `localhost,127.0.0.1` | Comma-separated allowed hosts |
| `POSTGRES_DB` | `aiqr` | Database name |
| `POSTGRES_USER` | `aiqr` | Database user |
| `POSTGRES_PASSWORD` | `aiqr_dev_password` | Database password |
| `POSTGRES_HOST` | `localhost` | Database host (`db` in Docker) |
| `POSTGRES_PORT` | `5432` | Database port (mapped to `5433` externally) |
| `REDIS_URL` | `redis://localhost:6379/0` | Redis URL (mapped to `6380` externally) |
| `OPENAI_API_KEY` | _(empty)_ | OpenAI API key for order parsing |

## Project Structure

```
backend/
├── config/              # Django project settings, URLs, ASGI/WSGI
│   ├── settings.py
│   ├── urls.py
│   └── asgi.py          # HTTP + WebSocket routing
├── restaurants/         # Auth, restaurant & menu management
│   ├── models.py        # User, Restaurant, MenuCategory, MenuItem, etc.
│   ├── views.py         # Register, Login, CRUD endpoints
│   ├── serializers.py
│   ├── permissions.py   # IsRestaurantOwner, IsRestaurantStaff
│   ├── managers.py      # Custom user manager (email-based auth)
│   └── tests/
├── orders/              # Order processing & real-time updates
│   ├── models.py        # Order, OrderItem
│   ├── views.py         # Public menu, parse/confirm order, kitchen updates
│   ├── services.py      # Order creation logic
│   ├── consumers.py     # WebSocket consumer for kitchen dashboard
│   ├── broadcast.py     # Channel layer broadcast helpers
│   ├── llm/             # LLM provider abstraction
│   │   ├── base.py      # Abstract base class
│   │   ├── openai_provider.py
│   │   └── menu_context.py
│   └── tests/
├── conftest.py          # Shared pytest fixtures
├── pytest.ini           # Pytest configuration
├── pyproject.toml       # Poetry dependencies
├── poetry.lock
├── manage.py
└── Dockerfile
```

## API Endpoints

### Authentication

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/auth/register/` | Register a new restaurant owner |
| POST | `/api/auth/login/` | Login, returns JWT tokens |
| POST | `/api/auth/refresh/` | Refresh access token |

### Restaurants (authenticated)

| Method | Endpoint | Description |
|---|---|---|
| POST | `/api/restaurants/` | Create a restaurant |
| GET | `/api/restaurants/` | List own restaurants |
| GET/PUT/PATCH/DELETE | `/api/restaurants/<id>/` | Restaurant detail |
| POST | `/api/restaurants/<id>/staff/` | Invite staff member |

### Menu Management (authenticated)

| Method | Endpoint | Description |
|---|---|---|
| GET/POST | `/api/restaurants/<id>/categories/` | List/create categories |
| GET/PUT/PATCH/DELETE | `/api/categories/<id>/` | Category detail |
| GET/POST | `/api/categories/<id>/items/` | List/create menu items |
| GET/PUT/PATCH/DELETE | `/api/items/<id>/` | Menu item detail |

### Public Ordering (no auth required)

| Method | Endpoint | Description |
|---|---|---|
| GET | `/api/public/menu/<slug>/` | Get restaurant menu by slug |
| POST | `/api/public/orders/parse/` | Send natural language text, get parsed order |
| POST | `/api/public/orders/confirm/` | Confirm a parsed order |
| GET | `/api/public/orders/<id>/status/` | Check order status |

### Kitchen (authenticated)

| Method | Endpoint | Description |
|---|---|---|
| PATCH | `/api/kitchen/orders/<id>/` | Update order status |

### WebSocket

| Protocol | Endpoint | Description |
|---|---|---|
| WS | `/ws/kitchen/<slug>/` | Real-time order updates for kitchen |

## Running Tests

```bash
# Run all tests
poetry run pytest

# Run with verbose output
poetry run pytest -v

# Run a specific test file
poetry run pytest restaurants/tests/test_auth.py

# Run a specific test class
poetry run pytest restaurants/tests/test_auth.py::TestLogin

# Run with coverage (install pytest-cov first)
poetry run pytest --cov=. --cov-report=term-missing
```

There are currently **56 tests** covering models, authentication, permissions, API endpoints, LLM integration, and WebSocket consumers.

## Running with Docker

From the project root:

```bash
# Start all services
docker compose up

# Start in background
docker compose up -d

# Run migrations inside container
docker compose exec backend python manage.py migrate

# Run tests inside container
docker compose exec backend pytest
```

## Adding Dependencies

```bash
# Production dependency
poetry add <package>

# Dev dependency
poetry add --group dev <package>
```
