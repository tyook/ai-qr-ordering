from datetime import timedelta
from pathlib import Path

from decouple import config

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = config("DJANGO_SECRET_KEY", default="insecure-dev-key-change-me")
DEBUG = config("DJANGO_DEBUG", default=True, cast=bool)
ALLOWED_HOSTS = config("DJANGO_ALLOWED_HOSTS", default="localhost,127.0.0.1").split(",")

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
    "django_celery_beat",
    # Local
    "accounts",
    "restaurants",
    "orders",
    "integrations",
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
AUTH_USER_MODEL = "accounts.User"

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
        "accounts.authentication.CookieJWTAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
}

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(minutes=15),
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
# Stripe
# ---------------------------------------------------------------------------
STRIPE_SECRET_KEY = config("STRIPE_SECRET_KEY", default="")
STRIPE_WEBHOOK_SECRET = config("STRIPE_WEBHOOK_SECRET", default="")

# ---------------------------------------------------------------------------
# Stripe Subscription Plans
# ---------------------------------------------------------------------------
STRIPE_PRICE_STARTER_MONTHLY = config("STRIPE_PRICE_STARTER_MONTHLY", default="")
STRIPE_PRICE_GROWTH_MONTHLY = config("STRIPE_PRICE_GROWTH_MONTHLY", default="")
STRIPE_PRICE_PRO_MONTHLY = config("STRIPE_PRICE_PRO_MONTHLY", default="")
# STRIPE_PRICE_STARTER_ANNUAL = config("STRIPE_PRICE_STARTER_ANNUAL", default="")
# STRIPE_PRICE_GROWTH_ANNUAL = config("STRIPE_PRICE_GROWTH_ANNUAL", default="")
# STRIPE_PRICE_PRO_ANNUAL = config("STRIPE_PRICE_PRO_ANNUAL", default="")

SUBSCRIPTION_PLANS = {
    "starter": {
        "name": "Starter",
        "order_limit": 200,
        "overage_rate_cents": 20,  # $0.20
        "monthly_price_id": STRIPE_PRICE_STARTER_MONTHLY,
        # "annual_price_id": STRIPE_PRICE_STARTER_ANNUAL,
    },
    "growth": {
        "name": "Growth",
        "order_limit": 600,
        "overage_rate_cents": 15,  # $0.15
        "monthly_price_id": STRIPE_PRICE_GROWTH_MONTHLY,
        # "annual_price_id": STRIPE_PRICE_GROWTH_ANNUAL,
    },
    "pro": {
        "name": "Pro",
        "order_limit": 1500,
        "overage_rate_cents": 10,  # $0.10
        "monthly_price_id": STRIPE_PRICE_PRO_MONTHLY,
        # "annual_price_id": STRIPE_PRICE_PRO_ANNUAL,
    },
}

# Free trial settings
FREE_TRIAL_DAYS = 14
FREE_TRIAL_ORDER_LIMIT = 200

FRONTEND_URL = config("FRONTEND_URL", default="http://localhost:3000")

# ---------------------------------------------------------------------------
# Celery
# ---------------------------------------------------------------------------
CELERY_BROKER_URL = config("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = CELERY_BROKER_URL
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TIMEZONE = "UTC"

# ---------------------------------------------------------------------------
# POS Integration
# ---------------------------------------------------------------------------
POS_ENCRYPTION_KEY = config("POS_ENCRYPTION_KEY", default="")
POS_SQUARE_CLIENT_ID = config("POS_SQUARE_CLIENT_ID", default="")
POS_SQUARE_CLIENT_SECRET = config("POS_SQUARE_CLIENT_SECRET", default="")
POS_TOAST_CLIENT_ID = config("POS_TOAST_CLIENT_ID", default="")
POS_TOAST_CLIENT_SECRET = config("POS_TOAST_CLIENT_SECRET", default="")
POS_DISPATCH_MAX_RETRIES = 5
POS_DISPATCH_RETRY_DELAYS = [30, 120, 600, 1800]  # seconds: 30s, 2m, 10m, 30m

# ---------------------------------------------------------------------------
# Payout Configuration
# ---------------------------------------------------------------------------
PAYOUT_CONFIG = {
    "settlement_days": 2,
    "job_run_hour_utc": 2,
    "default_fee_rate": 0,
    "default_fee_fixed_cents": 0,
}

STRIPE_CONNECT_WEBHOOK_SECRET = config("STRIPE_CONNECT_WEBHOOK_SECRET", default="")

# ---------------------------------------------------------------------------
# CORS
# ---------------------------------------------------------------------------
if DEBUG:
    CORS_ALLOW_ALL_ORIGINS = True
else:
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:3000",
        "http://localhost:3001",
    ]
CORS_ALLOW_CREDENTIALS = True

# ---------------------------------------------------------------------------
# Cookie Auth
# ---------------------------------------------------------------------------
AUTH_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_HTTPONLY = False  # Frontend reads csrftoken cookie
CSRF_COOKIE_SAMESITE = "Lax"
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_TRUSTED_ORIGINS = [
    "http://localhost:3000",
    "http://localhost:3001",
]

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
ANTHROPIC_API_KEY = config("ANTHROPIC_API_KEY", default="")
LLM_MODEL = config("LLM_MODEL", default="")

# ---------------------------------------------------------------------------
# Social Auth
# ---------------------------------------------------------------------------
GOOGLE_CLIENT_ID = config("GOOGLE_CLIENT_ID", default="")
APPLE_CLIENT_ID = config("APPLE_CLIENT_ID", default="")  # e.g. "com.yourapp.service"
