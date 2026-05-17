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

5. Set up Stripe (for subscription billing):

   a. Create a [Stripe account](https://dashboard.stripe.com/register) and switch to **Test mode**.

   b. Copy your **Secret key** from Developers > API keys and set it in `.env`:
      ```
      STRIPE_SECRET_KEY=sk_test_...
      ```

   c. Copy your **Publishable key** and set it in `frontend/.env.local`:
      ```
      NEXT_PUBLIC_STRIPE_PUBLISHABLE_KEY=pk_test_...
      ```

   d. Create three products in **Product catalog > Add product** with two prices each:

      | Product | Monthly price | Annual price |
      |---------|--------------|--------------|
      | Starter | $49/month    | $480/year    |
      | Growth  | $99/month    | $984/year    |
      | Pro     | $199/month   | $1,992/year  |

   e. Copy each price ID (starts with `price_`) and set them in `.env`:
      ```
      STRIPE_PRICE_STARTER_MONTHLY=price_...
      STRIPE_PRICE_STARTER_ANNUAL=price_...
      STRIPE_PRICE_GROWTH_MONTHLY=price_...
      STRIPE_PRICE_GROWTH_ANNUAL=price_...
      STRIPE_PRICE_PRO_MONTHLY=price_...
      STRIPE_PRICE_PRO_ANNUAL=price_...
      ```

   f. Install the [Stripe CLI](https://docs.stripe.com/stripe-cli) and forward webhooks to your local backend:
      ```
      brew install stripe/stripe-cli/stripe
      stripe login
      stripe listen --forward-to localhost:5005/api/webhooks/stripe/
      ```
      Copy the webhook signing secret it prints and set it in `.env`:
      ```
      STRIPE_WEBHOOK_SECRET=whsec_...
      ```

   > **Important:** `stripe listen` generates a new signing secret each session.
   > You must update `STRIPE_WEBHOOK_SECRET` in `.env` every time you restart it,
   > then restart the backend. When done testing, revert `STRIPE_WEBHOOK_SECRET`
   > to the value configured in the Stripe Dashboard for your deployed environment.

### Stripe Troubleshooting

| Error | Cause | Fix |
|---|---|---|
| `No such price: 'prod_...'` | Using a product ID instead of a price ID in `STRIPE_PRICE_*` env vars | Go to Stripe Dashboard > Products > click the product > copy the `price_` ID from the Pricing section. Product IDs (`prod_`) are not price IDs (`price_`). |
| Webhook returns 400 | `STRIPE_WEBHOOK_SECRET` doesn't match the `stripe listen` signing secret | Copy the `whsec_` value printed by `stripe listen` into `.env` and restart the backend |
| Subscription plan not updating after checkout | Stripe webhooks not reaching your local server | Run `stripe listen --forward-to localhost:5005/api/webhooks/stripe/` and verify events show `[200]` responses |

## Database Reset

To wipe the database and re-run all migrations from scratch:

```bash
cd backend
python manage.py reset_db
```

You will be prompted to confirm. To skip the prompt (useful in CI or scripts):

```bash
python manage.py reset_db --no-input
```

To delete all data but keep the schema (faster, skips re-running migrations):

```bash
python manage.py reset_db --flush-only
```

| Flag | Effect |
|------|--------|
| *(none)* | Drop all tables, re-run migrations (full reset) |
| `--flush-only` | Delete all rows but keep tables and schema |
| `--no-input` | Skip the "are you sure?" confirmation prompt |

## Running

Start the database and Redis:
```
docker compose up db redis -d
```

Start the backend (port 5005):
```
cd backend
./manage.py runserver 5005
```

Start the frontend (port 3001):
```
cd frontend
yarn dev -- -p 3001
```

Start Stripe webhook forwarding (in a separate terminal):
```
stripe listen --forward-to localhost:5005/api/webhooks/stripe/
```

| Service  | URL                     |
|----------|-------------------------|
| Backend  | http://localhost:5005   |
| Frontend | http://localhost:3001   |

Run BE server locally
./manage.py runserver 5005
## Mobile App (Capacitor)

The frontend is wrapped with [Capacitor](https://capacitorjs.com/) to produce native Android and iOS apps from the same codebase. Native features include push notifications, QR code scanning, and over-the-air live updates.

### Prerequisites

- Android Studio (for Android builds)
- Xcode (for iOS builds, macOS only)
- CocoaPods (`sudo gem install cocoapods`)

### Setup

1. Build the static frontend and sync with native projects:
   ```
   cd frontend
   npm run build:mobile
   ```

2. Open in your IDE:
   ```
   npm run open:android   # Opens Android Studio
   npm run open:ios       # Opens Xcode
   ```

3. For local development, set your machine's IP so the app can reach the backend:
   ```
   NEXT_PUBLIC_API_URL=http://192.168.x.x:5005 npm run build:mobile
   ```

### Build Scripts

| Script | Description |
|--------|-------------|
| `npm run build:mobile` | Static export + Capacitor sync |
| `npm run open:android` | Open project in Android Studio |
| `npm run open:ios` | Open project in Xcode |
| `npm run deploy:mobile` | Build and push OTA live update |

### Live Updates

Code changes can be pushed to users' devices without an App Store resubmission using [Capawesome Live Update](https://github.com/capawesome-team/capacitor-plugins). Run `npm run deploy:mobile` to build and upload a new bundle. Users receive the update on next app launch.

Store resubmission is only required when:
- Adding or removing Capacitor native plugins
- Changing `capacitor.config.ts`
- Updating native project files (`android/`, `ios/`)

### Architecture

See [Capacitor Mobile Design Spec](docs/superpowers/specs/2026-03-30-capacitor-mobile-design.md) for full details.
