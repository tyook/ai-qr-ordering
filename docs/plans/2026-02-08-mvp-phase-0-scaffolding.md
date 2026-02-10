# Phase 0: Infrastructure & Project Scaffolding

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up the monorepo structure, Docker Compose for local dev, and initialize both Django backend and Next.js frontend projects with all dependencies.

**Architecture:** Monorepo with `backend/` (Django 4.2 + DRF + Channels) and `frontend/` (Next.js 14 App Router). Docker Compose orchestrates PostgreSQL 16, Redis 7, and both app servers for local development.

**Tech Stack:** Docker, PostgreSQL 16, Redis 7, Django 4.2, Next.js 14, TypeScript

**Depends on:** Nothing (first phase)

---

## Task 1: Docker Compose & Infrastructure

**Files:**
- Create: `docker-compose.yml`
- Create: `.env.example`
- Create: `.gitignore`

**Step 1: Create `.gitignore`**

```gitignore
# Python
__pycache__/
*.py[cod]
*.egg-info/
.eggs/
dist/
build/
*.egg
.venv/
venv/

# Django
*.sqlite3
media/

# Node
node_modules/
.next/
out/

# Environment
.env
.env.local
.env.production

# IDE
.idea/
.vscode/
*.swp
*.swo

# OS
.DS_Store
Thumbs.db

# Docker
docker-compose.override.yml
```

**Step 2: Create `.env.example`**

```env
# Django
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=aiqr
POSTGRES_USER=aiqr
POSTGRES_PASSWORD=aiqr_dev_password
POSTGRES_HOST=db
POSTGRES_PORT=5432

# Redis
REDIS_URL=redis://redis:6379/0

# LLM
OPENAI_API_KEY=sk-your-key-here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

**Step 3: Create `docker-compose.yml`**

```yaml
version: "3.9"

services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: ${POSTGRES_DB:-aiqr}
      POSTGRES_USER: ${POSTGRES_USER:-aiqr}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-aiqr_dev_password}
    ports:
      - "5432:5432"
    volumes:
      - pgdata:/var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-aiqr}"]
      interval: 5s
      timeout: 3s
      retries: 5

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    healthcheck:
      test: ["CMD", "redis-cli", "ping"]
      interval: 5s
      timeout: 3s
      retries: 5

  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    command: python manage.py runserver 0.0.0.0:8000
    volumes:
      - ./backend:/app
    ports:
      - "8000:8000"
    env_file:
      - .env
    depends_on:
      db:
        condition: service_healthy
      redis:
        condition: service_healthy

  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    command: npm run dev
    volumes:
      - ./frontend:/app
      - /app/node_modules
    ports:
      - "3000:3000"
    env_file:
      - .env
    depends_on:
      - backend

volumes:
  pgdata:
```

**Step 4: Commit**

```bash
git add .gitignore .env.example docker-compose.yml
git commit -m "chore: add Docker Compose, env config, and gitignore"
```

---

## Task 2: Django Backend Scaffolding

**Files:**
- Create: `backend/Dockerfile`
- Create: `backend/requirements.txt`
- Create: `backend/manage.py` (via django-admin)
- Create: `backend/config/` (Django project package)
- Create: `backend/pytest.ini`
- Create: `backend/conftest.py`

**Step 1: Create `backend/requirements.txt`**

```txt
Django==4.2.17
djangorestframework==3.15.2
djangorestframework-simplejwt==5.4.0
django-cors-headers==4.6.0
channels==4.2.0
channels-redis==4.2.1
daphne==4.1.2
openai==1.61.0
anthropic==0.43.0
psycopg2-binary==2.9.10
Pillow==11.1.0
python-decouple==3.8
```

**Step 2: Create `backend/Dockerfile`**

```dockerfile
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
```

**Step 3: Initialize Django project**

```bash
cd backend
pip install django==4.2.17
django-admin startproject config .
```

This creates:
- `backend/manage.py`
- `backend/config/__init__.py`
- `backend/config/settings.py`
- `backend/config/urls.py`
- `backend/config/asgi.py`
- `backend/config/wsgi.py`

**Step 4: Replace `backend/config/settings.py` with production-ready config**

Replace the entire file with:

```python
import os
from pathlib import Path
from datetime import timedelta

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config(
    "DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1"
).split(",")

# ---------------------------------------------------------------------------
# Apps
# ---------------------------------------------------------------------------
INSTALLED_APPS = [
    "daphne",
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "channels",
    # Local
    "restaurants",
    "orders",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": config("POSTGRES_DB", default="aiqr"),
        "USER": config("POSTGRES_USER", default="aiqr"),
        "PASSWORD": config("POSTGRES_PASSWORD", default="aiqr_dev_password"),
        "HOST": config("POSTGRES_HOST", default="localhost"),
        "PORT": config("POSTGRES_PORT", default="5432"),
    }
}

# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------
AUTH_USER_MODEL = "restaurants.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ---------------------------------------------------------------------------
# REST Framework
# ---------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=12),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=7),
}

# ---------------------------------------------------------------------------
# Channels (WebSocket)
# ---------------------------------------------------------------------------
CHANNEL_LAYERS = {
    "default": {
        "BACKEND": "channels_redis.core.RedisChannelLayer",
        "CONFIG": {
            "hosts": [config("REDIS_URL", default="redis://localhost:6379/0")],
        },
    },
}

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# i18n
# ---------------------------------------------------------------------------
LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

# ---------------------------------------------------------------------------
# Static & Media
# ---------------------------------------------------------------------------
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ---------------------------------------------------------------------------
# LLM
# ---------------------------------------------------------------------------
OPENAI_API_KEY = config("OPENAI_API_KEY", default="")
```

**Step 5: Update `backend/config/asgi.py`**

```python
import os
from channels.routing import ProtocolTypeRouter, URLRouter
from django.core.asgi import get_asgi_application

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
django_asgi_app = get_asgi_application()

from orders.routing import websocket_urlpatterns  # noqa: E402

application = ProtocolTypeRouter(
    {
        "http": django_asgi_app,
        "websocket": URLRouter(websocket_urlpatterns),
    }
)
```

> **Note:** This file will cause an import error until Phase 4 creates `orders/routing.py`. That is fine — during Phase 0-3 development, use `python manage.py runserver` (WSGI) instead of Daphne. The ASGI config will be verified in Phase 4.

**Step 6: Create `backend/pytest.ini`**

```ini
[pytest]
DJANGO_SETTINGS_MODULE = config.settings
python_files = tests.py test_*.py *_tests.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short
```

**Step 7: Create `backend/conftest.py`**

```python
import pytest
from rest_framework.test import APIClient


@pytest.fixture
def api_client():
    return APIClient()
```

**Step 8: Add test dependencies to `backend/requirements.txt`**

Append to the file:

```txt
# Testing
pytest==8.3.4
pytest-django==4.9.0
factory-boy==3.3.1
```

**Step 9: Commit**

```bash
git add backend/
git commit -m "chore: scaffold Django backend with config, Docker, and test setup"
```

---

## Task 3: Create Django Apps (empty shells)

We need two Django apps: `restaurants` and `orders`. This task creates the app directories with empty `__init__.py` files so imports resolve. Models come in Phase 1.

**Step 1: Create the restaurant app**

```bash
cd backend
python manage.py startapp restaurants
```

**Step 2: Create the orders app**

```bash
cd backend
python manage.py startapp orders
```

**Step 3: Create placeholder `orders/routing.py`**

```python
# WebSocket URL patterns - implemented in Phase 4
websocket_urlpatterns = []
```

This satisfies the ASGI import in `config/asgi.py`.

**Step 4: Update `backend/config/urls.py`**

```python
from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/", include("restaurants.urls")),
    path("api/", include("orders.urls")),
]
```

**Step 5: Create empty URL files**

Create `backend/restaurants/urls.py`:

```python
from django.urls import path

urlpatterns = []
```

Create `backend/orders/urls.py`:

```python
from django.urls import path

urlpatterns = []
```

**Step 6: Verify Django starts without errors**

```bash
cd backend
python manage.py check
```

Expected: `System check identified no issues.` (may warn about unapplied migrations — that's fine, models come in Phase 1)

**Step 7: Commit**

```bash
git add backend/
git commit -m "chore: create restaurants and orders Django apps"
```

---

## Task 4: Next.js Frontend Scaffolding

**Files:**
- Create: `frontend/` (via create-next-app)
- Create: `frontend/Dockerfile`
- Modify: `frontend/package.json` (add dependencies)

**Step 1: Initialize Next.js project**

```bash
npx create-next-app@14 frontend \
  --typescript \
  --tailwind \
  --eslint \
  --app \
  --src-dir \
  --import-alias "@/*" \
  --no-turbo
```

**Step 2: Create `frontend/Dockerfile`**

```dockerfile
FROM node:20-alpine

WORKDIR /app

COPY package*.json ./
RUN npm install

COPY . .
```

**Step 3: Install additional dependencies**

```bash
cd frontend
npm install zustand react-hot-toast qrcode.react
npm install -D @types/node
```

**Step 4: Initialize shadcn/ui**

```bash
cd frontend
npx shadcn-ui@latest init
```

When prompted:
- Style: Default
- Base color: Slate
- CSS variables: Yes

**Step 5: Add commonly needed shadcn components**

```bash
cd frontend
npx shadcn-ui@latest add button card input label textarea badge dialog dropdown-menu separator toast tabs
```

**Step 6: Create `frontend/src/lib/api.ts`** (API client stub)

```typescript
const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_URL}${path}`;
  const headers: HeadersInit = {
    "Content-Type": "application/json",
    ...options.headers,
  };

  const token =
    typeof window !== "undefined" ? localStorage.getItem("access_token") : null;
  if (token) {
    (headers as Record<string, string>)["Authorization"] = `Bearer ${token}`;
  }

  const response = await fetch(url, { ...options, headers });

  if (!response.ok) {
    const error = await response.json().catch(() => ({}));
    throw new Error(error.detail || `API error: ${response.status}`);
  }

  return response.json();
}
```

**Step 7: Verify frontend starts**

```bash
cd frontend
npm run build
```

Expected: Build succeeds without errors.

**Step 8: Commit**

```bash
git add frontend/
git commit -m "chore: scaffold Next.js frontend with Tailwind, shadcn/ui, and API client"
```

---

## Task 5: Verify Full Docker Compose Stack

**Step 1: Copy `.env.example` to `.env`**

```bash
cp .env.example .env
```

**Step 2: Build and start all services**

```bash
docker compose up --build -d
```

**Step 3: Verify all services are healthy**

```bash
docker compose ps
```

Expected: All 4 services (db, redis, backend, frontend) running.

**Step 4: Verify backend responds**

```bash
curl http://localhost:8000/admin/
```

Expected: HTML response (Django admin login page).

**Step 5: Verify frontend responds**

```bash
curl -s http://localhost:3000 | head -20
```

Expected: HTML response (Next.js page).

**Step 6: Stop services**

```bash
docker compose down
```

**Step 7: Commit any adjustments**

```bash
git add -A
git commit -m "chore: verify Docker Compose stack boots successfully"
```
