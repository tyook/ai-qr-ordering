# CI/CD Pipeline Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Set up CI pipeline (GitHub Actions) and CD pipeline (Vercel for frontend, Render for backend) with staging + production environments.

**Architecture:** GitHub Actions runs lint + tests on every PR. Merges to `main` auto-deploy to staging via Vercel/Render native Git integrations. Production deploys are triggered manually via `workflow_dispatch` or Git tag push (`v*`), using Vercel CLI and Render deploy hooks.

**Tech Stack:** GitHub Actions, Vercel CLI, Render Deploy Hooks, ruff (Python linter), pytest, Yarn, Next.js

---

### Task 1: Add ruff configuration to backend

**Files:**
- Create: `backend/ruff.toml`
- Modify: `backend/pyproject.toml` (add ruff to dev dependencies)

**Step 1: Create ruff config**

Create `backend/ruff.toml`:

```toml
target-version = "py312"
line-length = 120

[lint]
select = [
    "E",    # pycodestyle errors
    "W",    # pycodestyle warnings
    "F",    # pyflakes
    "I",    # isort
    "B",    # flake8-bugbear
    "UP",   # pyupgrade
]
ignore = [
    "E501",  # line too long (handled by formatter)
]

[format]
quote-style = "double"
indent-style = "space"
```

**Step 2: Add ruff to dev dependencies**

In `backend/pyproject.toml`, add `ruff` to the `[tool.poetry.group.dev.dependencies]` section:

```toml
[tool.poetry.group.dev.dependencies]
pytest = "8.3.4"
pytest-django = "4.9.0"
factory-boy = "3.3.1"
pytest-asyncio = "0.25.3"
ruff = ">=0.9.0"
```

**Step 3: Install ruff and verify it works**

Run:
```bash
cd backend && poetry install
```

Then verify:
```bash
cd backend && poetry run ruff check .
cd backend && poetry run ruff format --check .
```

Expected: Runs without crashing. May report existing lint/format issues — that's OK for now. We want CI to run it, but we won't block on fixing all existing issues in this task.

**Step 4: Commit**

```bash
git add backend/ruff.toml backend/pyproject.toml backend/poetry.lock
git commit -m "chore: add ruff linter configuration to backend"
```

---

### Task 2: Create CI workflow for PRs

**Files:**
- Create: `.github/workflows/ci.yml`

**Step 1: Create the CI workflow file**

Create `.github/workflows/ci.yml`:

```yaml
name: CI

on:
  pull_request:
    branches: [main]

concurrency:
  group: ci-${{ github.ref }}
  cancel-in-progress: true

jobs:
  backend:
    name: Backend (lint + test)
    runs-on: ubuntu-latest

    services:
      postgres:
        image: postgres:16-alpine
        env:
          POSTGRES_DB: test_aiqr
          POSTGRES_USER: aiqr
          POSTGRES_PASSWORD: test_password
        ports:
          - 5432:5432
        options: >-
          --health-cmd "pg_isready -U aiqr"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

      redis:
        image: redis:7-alpine
        ports:
          - 6379:6379
        options: >-
          --health-cmd "redis-cli ping"
          --health-interval 5s
          --health-timeout 3s
          --health-retries 5

    defaults:
      run:
        working-directory: backend

    steps:
      - uses: actions/checkout@v4

      - name: Set up Python 3.12
        uses: actions/setup-python@v5
        with:
          python-version: "3.12"

      - name: Install Poetry
        run: pip install poetry

      - name: Cache Poetry virtualenv
        uses: actions/cache@v4
        with:
          path: ~/.cache/pypoetry
          key: poetry-${{ runner.os }}-${{ hashFiles('backend/poetry.lock') }}
          restore-keys: poetry-${{ runner.os }}-

      - name: Install dependencies
        run: poetry install --no-interaction --no-ansi

      - name: Lint (ruff check)
        run: poetry run ruff check .

      - name: Format check (ruff format)
        run: poetry run ruff format --check .

      - name: Run tests
        env:
          DJANGO_SETTINGS_MODULE: config.settings
          POSTGRES_DB: test_aiqr
          POSTGRES_USER: aiqr
          POSTGRES_PASSWORD: test_password
          POSTGRES_HOST: localhost
          POSTGRES_PORT: "5432"
          REDIS_URL: redis://localhost:6379/0
          DJANGO_SECRET_KEY: ci-test-secret-key
          DJANGO_DEBUG: "False"
        run: poetry run pytest

  frontend:
    name: Frontend (lint + build)
    runs-on: ubuntu-latest

    defaults:
      run:
        working-directory: frontend

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node 20
        uses: actions/setup-node@v4
        with:
          node-version: "20"
          cache: "yarn"
          cache-dependency-path: frontend/yarn.lock

      - name: Install dependencies
        run: yarn install --frozen-lockfile

      - name: Lint
        run: yarn lint

      - name: Build
        env:
          NEXT_PUBLIC_API_URL: http://localhost:5005
          NEXT_PUBLIC_WS_URL: ws://localhost:5005
        run: yarn build
```

**Step 2: Validate the YAML syntax**

Run:
```bash
python3 -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))" 2>&1 || echo "YAML syntax error"
```

Expected: No output (valid YAML). If Python yaml module is not available, skip this step.

**Step 3: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: add GitHub Actions CI pipeline for backend and frontend"
```

---

### Task 3: Create production deploy workflow

**Files:**
- Create: `.github/workflows/deploy-production.yml`

**Step 1: Create the production deploy workflow**

Create `.github/workflows/deploy-production.yml`:

```yaml
name: Deploy Production

on:
  push:
    tags:
      - "v*"
  workflow_dispatch:

concurrency:
  group: deploy-production
  cancel-in-progress: false

jobs:
  deploy-frontend:
    name: Deploy Frontend to Vercel (Production)
    runs-on: ubuntu-latest

    steps:
      - uses: actions/checkout@v4

      - name: Set up Node 20
        uses: actions/setup-node@v4
        with:
          node-version: "20"

      - name: Install Vercel CLI
        run: npm install -g vercel

      - name: Pull Vercel environment
        run: vercel pull --yes --environment=production --token=${{ secrets.VERCEL_TOKEN }}
        working-directory: frontend

      - name: Build
        run: vercel build --prod --token=${{ secrets.VERCEL_TOKEN }}
        working-directory: frontend

      - name: Deploy to Production
        run: vercel deploy --prebuilt --prod --token=${{ secrets.VERCEL_TOKEN }}
        working-directory: frontend
        env:
          VERCEL_ORG_ID: ${{ secrets.VERCEL_ORG_ID }}
          VERCEL_PROJECT_ID: ${{ secrets.VERCEL_PROJECT_ID }}

  deploy-backend:
    name: Deploy Backend to Render (Production)
    runs-on: ubuntu-latest

    steps:
      - name: Trigger Render Deploy
        run: |
          curl -s -o /dev/null -w "%{http_code}" \
            "${{ secrets.RENDER_DEPLOY_HOOK_PRODUCTION }}" | grep -q "200" \
            && echo "Deploy triggered successfully" \
            || (echo "Failed to trigger deploy" && exit 1)
```

**Step 2: Commit**

```bash
git add .github/workflows/deploy-production.yml
git commit -m "ci: add production deploy workflow (Vercel + Render)"
```

---

### Task 4: Add Vercel project configuration

**Files:**
- Create: `frontend/vercel.json`

**Step 1: Create vercel.json**

Create `frontend/vercel.json`:

```json
{
  "$schema": "https://openapi.vercel.sh/vercel.json",
  "framework": "nextjs",
  "buildCommand": "yarn build",
  "installCommand": "yarn install --frozen-lockfile",
  "outputDirectory": ".next"
}
```

**Step 2: Commit**

```bash
git add frontend/vercel.json
git commit -m "ci: add Vercel project configuration"
```

---

### Task 5: Add Render blueprint for backend

**Files:**
- Create: `render.yaml`

**Step 1: Create render.yaml**

This Render blueprint defines the backend web service for infrastructure-as-code. Create `render.yaml` in the project root:

```yaml
services:
  - type: web
    name: menuchat-backend
    runtime: docker
    dockerfilePath: backend/Dockerfile
    dockerContext: backend
    plan: free
    healthCheckPath: /api/health/
    envVars:
      - key: DJANGO_SECRET_KEY
        generateValue: true
      - key: DJANGO_DEBUG
        value: "False"
      - key: DJANGO_ALLOWED_HOSTS
        sync: false
      - key: POSTGRES_DB
        sync: false
      - key: POSTGRES_USER
        sync: false
      - key: POSTGRES_PASSWORD
        sync: false
      - key: POSTGRES_HOST
        sync: false
      - key: POSTGRES_PORT
        sync: false
      - key: REDIS_URL
        sync: false
      - key: OPENAI_API_KEY
        sync: false
      - key: STRIPE_SECRET_KEY
        sync: false
      - key: STRIPE_WEBHOOK_SECRET
        sync: false
```

**Step 2: Commit**

```bash
git add render.yaml
git commit -m "ci: add Render blueprint for backend deployment"
```

---

### Task 6: Fix any ruff lint/format issues in backend

**Step 1: Run ruff and auto-fix**

```bash
cd backend && poetry run ruff check --fix .
cd backend && poetry run ruff format .
```

**Step 2: Verify clean**

```bash
cd backend && poetry run ruff check .
cd backend && poetry run ruff format --check .
```

Expected: No errors.

**Step 3: Run tests to ensure nothing broke**

```bash
cd backend && POSTGRES_HOST=localhost poetry run pytest
```

Expected: All tests pass.

**Step 4: Commit**

```bash
git add -A backend/
git commit -m "style: fix ruff lint and format issues in backend"
```

---

### Task 7: Update .env.example with staging/production notes

**Files:**
- Modify: `.env.example`

**Step 1: Add environment-awareness comments**

Update `.env.example` to document which variables are needed where:

```bash
# =============================================================================
# Local Development
# =============================================================================

# Django
DJANGO_SECRET_KEY=change-me-in-production
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1

# Database
POSTGRES_DB=aiqr
POSTGRES_USER=aiqr
POSTGRES_PASSWORD=aiqr_dev_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5433

# Redis
REDIS_URL=redis://localhost:6380/0

# LLM
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=sk-ant-your-key-here
LLM_MODEL=gpt-4o-mini

# Stripe
STRIPE_SECRET_KEY=sk_test_your-key-here
STRIPE_WEBHOOK_SECRET=whsec_your-key-here

# Frontend
NEXT_PUBLIC_API_URL=http://localhost:5005
NEXT_PUBLIC_WS_URL=ws://localhost:5005

# =============================================================================
# Staging / Production (set in Vercel & Render dashboards, not here)
# =============================================================================
# DJANGO_ALLOWED_HOSTS=menuchat-staging.onrender.com
# FRONTEND_URL=https://menuchat-staging.vercel.app
# NEXT_PUBLIC_API_URL=https://menuchat-staging.onrender.com
# NEXT_PUBLIC_WS_URL=wss://menuchat-staging.onrender.com
```

**Step 2: Commit**

```bash
git add .env.example
git commit -m "docs: update .env.example with staging/production notes"
```

---

### Task 8: Verify CI workflow locally (dry run)

**Step 1: Verify backend CI steps work locally**

```bash
cd backend && poetry run ruff check .
cd backend && poetry run ruff format --check .
cd backend && POSTGRES_HOST=localhost poetry run pytest
```

Expected: All pass.

**Step 2: Verify frontend CI steps work locally**

```bash
cd frontend && yarn lint
cd frontend && yarn build
```

Expected: Both pass.

**Step 3: No commit needed — this is a verification step.**

---

### Task 9: Final commit and summary

**Step 1: Verify all files are committed**

```bash
git status
```

Expected: Clean working tree.

**Step 2: Summarize remaining manual setup**

Print the checklist of manual steps the developer needs to do outside of code:

1. **Vercel:** Create `menuchat-staging` project linked to `main` branch. Create `menuchat-production` project with auto-deploy disabled.
2. **Render:** Create `menuchat-staging` web service linked to `main` with auto-deploy. Create `menuchat-production` web service with auto-deploy off. Create a deploy hook for production.
3. **GitHub Secrets:** Add `VERCEL_TOKEN`, `VERCEL_ORG_ID`, `VERCEL_PROJECT_ID`, `RENDER_DEPLOY_HOOK_PRODUCTION`.
4. **GitHub Branch Protection:** Require CI status checks to pass before merging PRs to `main`.
