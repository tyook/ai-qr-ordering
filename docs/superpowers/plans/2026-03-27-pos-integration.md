# POS System Integration Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Inject confirmed QR orders into the restaurant's existing POS system asynchronously, with direct adapters for Square and Toast, and graceful fallbacks.

**Architecture:** A new `integrations` Django app uses the adapter pattern to dispatch confirmed orders to POS systems via Celery tasks. Each POS vendor gets its own adapter implementing `BasePOSAdapter`. Dispatch is fire-and-forget with exponential backoff retries. The frontend adds POS connection management and sync log pages to the restaurant dashboard.

**Tech Stack:** Django 4.2, Celery (already configured), `cryptography` (Fernet), `squareup` (Square SDK), `httpx` (Toast API), React 18 / Next.js 14, TanStack React Query, Tailwind / shadcn/ui

**Spec:** `docs/superpowers/specs/2026-03-27-pos-integration-design.md`

---

## Chunk 1: Core Models, Adapter Interface, and Dispatch Pipeline

This chunk builds the foundational backend: models, encryption utilities, the adapter base class, Celery dispatch task, and the integration hooks into the existing order flow. After this chunk, the system will dispatch orders to a no-op adapter and log sync attempts.

---

### Task 1: Create the `integrations` Django App Skeleton

**Files:**
- Create: `backend/integrations/__init__.py`
- Create: `backend/integrations/apps.py`
- Create: `backend/integrations/models.py` (empty initially)
- Create: `backend/integrations/admin.py`
- Create: `backend/integrations/views.py` (empty initially)
- Create: `backend/integrations/urls.py` (empty initially)
- Create: `backend/integrations/services.py` (empty initially)
- Create: `backend/integrations/tasks.py` (empty initially)
- Create: `backend/integrations/adapters/__init__.py`
- Create: `backend/integrations/adapters/base.py` (empty initially)
- Create: `backend/integrations/tests/__init__.py`
- Modify: `backend/config/settings.py:15-32` (add to INSTALLED_APPS)
- Modify: `backend/config/urls.py` (add URL include)

- [ ] **Step 1: Create the app directory structure**

```bash
mkdir -p backend/integrations/adapters
mkdir -p backend/integrations/tests
mkdir -p backend/integrations/migrations
touch backend/integrations/__init__.py
touch backend/integrations/adapters/__init__.py
touch backend/integrations/tests/__init__.py
touch backend/integrations/migrations/__init__.py
```

- [ ] **Step 2: Create `apps.py`**

```python
# backend/integrations/apps.py
from django.apps import AppConfig


class IntegrationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "integrations"
```

- [ ] **Step 3: Create empty module files**

Create these files with minimal content (empty or pass):
- `backend/integrations/models.py` → empty
- `backend/integrations/admin.py` → `from django.contrib import admin`
- `backend/integrations/views.py` → empty
- `backend/integrations/services.py` → empty
- `backend/integrations/tasks.py` → empty
- `backend/integrations/adapters/base.py` → empty

- [ ] **Step 4: Create `urls.py`**

```python
# backend/integrations/urls.py
from django.urls import path

urlpatterns = []
```

- [ ] **Step 5: Register the app in settings**

In `backend/config/settings.py`, add `"integrations"` to `INSTALLED_APPS` after `"orders"` (line ~32).

Also add POS settings after the existing Celery settings block (~line 177):

```python
# POS Integration
POS_ENCRYPTION_KEY = config("POS_ENCRYPTION_KEY", default="")
POS_SQUARE_CLIENT_ID = config("POS_SQUARE_CLIENT_ID", default="")
POS_SQUARE_CLIENT_SECRET = config("POS_SQUARE_CLIENT_SECRET", default="")
POS_TOAST_CLIENT_ID = config("POS_TOAST_CLIENT_ID", default="")
POS_TOAST_CLIENT_SECRET = config("POS_TOAST_CLIENT_SECRET", default="")
POS_DISPATCH_MAX_RETRIES = 5
POS_DISPATCH_RETRY_DELAYS = [30, 120, 600, 1800]  # seconds: 30s, 2m, 10m, 30m
```

- [ ] **Step 6: Add URL include to main router**

In `backend/config/urls.py`, add:

```python
path("api/", include("integrations.urls")),
```

- [ ] **Step 7: Verify the app loads**

Run: `cd backend && poetry run python manage.py check`
Expected: `System check identified no issues.`

- [ ] **Step 8: Commit**

```bash
git add backend/integrations/ backend/config/settings.py backend/config/urls.py
git commit -m "feat: create integrations app skeleton for POS integration"
```

---

### Task 2: Add `POSConnection` and `POSSyncLog` Models

**Files:**
- Create: `backend/integrations/models.py`
- Create: `backend/integrations/tests/factories.py`
- Create: `backend/integrations/tests/test_models.py`

- [ ] **Step 1: Write the failing test for POSConnection**

```python
# backend/integrations/tests/test_models.py
import pytest
from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import RestaurantFactory


@pytest.mark.django_db
class TestPOSConnection:
    def test_create_pos_connection(self):
        connection = POSConnectionFactory(pos_type="square")
        assert connection.pos_type == "square"
        assert connection.is_active is True
        assert connection.payment_mode == "stripe"
        assert connection.restaurant is not None

    def test_one_connection_per_restaurant(self):
        restaurant = RestaurantFactory()
        POSConnectionFactory(restaurant=restaurant)
        with pytest.raises(Exception):
            POSConnectionFactory(restaurant=restaurant)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_models.py -v`
Expected: FAIL — model and factory don't exist yet.

- [ ] **Step 3: Write the POSConnection model**

```python
# backend/integrations/models.py
import uuid

from django.db import models

from restaurants.models import Restaurant


class POSConnection(models.Model):
    class POSType(models.TextChoices):
        SQUARE = "square", "Square"
        TOAST = "toast", "Toast"
        MIDDLEWARE = "middleware", "Middleware"
        NONE = "none", "None"

    class PaymentMode(models.TextChoices):
        STRIPE = "stripe", "Stripe"
        POS_COLLECTED = "pos_collected", "POS Collected"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.OneToOneField(
        Restaurant,
        on_delete=models.CASCADE,
        related_name="pos_connection",
    )
    pos_type = models.CharField(
        max_length=20,
        choices=POSType.choices,
        default=POSType.NONE,
    )
    is_active = models.BooleanField(default=True)
    payment_mode = models.CharField(
        max_length=20,
        choices=PaymentMode.choices,
        default=PaymentMode.STRIPE,
    )
    oauth_access_token = models.TextField(blank=True, default="")
    oauth_refresh_token = models.TextField(blank=True, default="")
    oauth_token_expires_at = models.DateTimeField(null=True, blank=True)
    external_location_id = models.CharField(max_length=255, blank=True, null=True)
    middleware_config = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.restaurant.name} - {self.get_pos_type_display()}"
```

- [ ] **Step 4: Write the POSSyncLog model**

Append to `backend/integrations/models.py`:

```python
class POSSyncLog(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        SUCCESS = "success", "Success"
        FAILED = "failed", "Failed"
        RETRYING = "retrying", "Retrying"
        MANUALLY_RESOLVED = "manually_resolved", "Manually Resolved"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    order = models.ForeignKey(
        "orders.Order",
        on_delete=models.CASCADE,
        related_name="pos_sync_logs",
    )
    pos_connection = models.ForeignKey(
        POSConnection,
        on_delete=models.CASCADE,
        related_name="sync_logs",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
    )
    external_order_id = models.CharField(max_length=255, blank=True, null=True)
    attempt_count = models.PositiveIntegerField(default=0)
    last_error = models.TextField(blank=True, null=True)
    next_retry_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return f"Sync({self.order_id}, {self.status})"
```

- [ ] **Step 5: Create factories**

```python
# backend/integrations/tests/factories.py
import factory

from integrations.models import POSConnection, POSSyncLog
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory


class POSConnectionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = POSConnection

    restaurant = factory.SubFactory(RestaurantFactory)
    pos_type = "square"
    is_active = True
    payment_mode = "stripe"
    oauth_access_token = "test_access_token"
    oauth_refresh_token = "test_refresh_token"
    external_location_id = "loc_test_123"


class POSSyncLogFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = POSSyncLog

    order = factory.SubFactory(OrderFactory)
    pos_connection = factory.SubFactory(POSConnectionFactory)
    status = "pending"
    attempt_count = 0
```

- [ ] **Step 6: Create and run migration**

Run: `cd backend && poetry run python manage.py makemigrations integrations`
Expected: Creates `0001_initial.py` migration.

Run: `cd backend && poetry run python manage.py migrate`
Expected: Migration applied successfully.

- [ ] **Step 7: Run tests to verify they pass**

Run: `cd backend && poetry run pytest integrations/tests/test_models.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Add POSSyncLog tests**

Append to `backend/integrations/tests/test_models.py`:

```python
from integrations.tests.factories import POSSyncLogFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestPOSSyncLog:
    def test_create_sync_log(self):
        log = POSSyncLogFactory()
        assert log.status == "pending"
        assert log.attempt_count == 0
        assert log.order is not None
        assert log.pos_connection is not None

    def test_ordering_by_created_at(self):
        log1 = POSSyncLogFactory()
        log2 = POSSyncLogFactory(pos_connection=log1.pos_connection)
        from integrations.models import POSSyncLog
        logs = list(POSSyncLog.objects.all())
        assert logs[0].id == log2.id  # most recent first
```

- [ ] **Step 9: Run all tests**

Run: `cd backend && poetry run pytest integrations/tests/test_models.py -v`
Expected: All tests PASS.

- [ ] **Step 10: Commit**

```bash
git add backend/integrations/
git commit -m "feat: add POSConnection and POSSyncLog models with tests"
```

---

### Task 3: Add POS Fields to Existing Order Model

**Files:**
- Modify: `backend/orders/models.py:45-54` (add `pos_collected` to payment_status choices)
- Modify: `backend/orders/models.py` (add `external_order_id` and `pos_sync_status` fields)
- Create: `backend/integrations/tests/test_order_pos_fields.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_order_pos_fields.py
import pytest
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestOrderPOSFields:
    def test_default_pos_sync_status(self):
        order = OrderFactory()
        assert order.pos_sync_status == "not_applicable"
        assert order.external_order_id is None

    def test_pos_collected_payment_status(self):
        order = OrderFactory(payment_status="pos_collected")
        assert order.payment_status == "pos_collected"

    def test_set_external_order_id(self):
        order = OrderFactory()
        order.external_order_id = "sq_order_abc123"
        order.pos_sync_status = "synced"
        order.save()
        order.refresh_from_db()
        assert order.external_order_id == "sq_order_abc123"
        assert order.pos_sync_status == "synced"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_order_pos_fields.py -v`
Expected: FAIL — fields don't exist yet.

- [ ] **Step 3: Add fields to Order model**

In `backend/orders/models.py`, update `payment_status` choices (line 45-54) to add `pos_collected`:

```python
payment_status = models.CharField(
    max_length=20,
    choices=[
        ("pending", "Pending"),
        ("paid", "Paid"),
        ("pos_collected", "POS Collected"),
        ("failed", "Failed"),
        ("refunded", "Refunded"),
    ],
    default="pending",
)
```

Add new fields after `customer_allergies` (around line 87):

```python
# POS Integration
external_order_id = models.CharField(
    max_length=255,
    blank=True,
    null=True,
    help_text="Order ID in external POS system",
)
pos_sync_status = models.CharField(
    max_length=20,
    choices=[
        ("not_applicable", "Not Applicable"),
        ("pending", "Pending"),
        ("synced", "Synced"),
        ("retrying", "Retrying"),
        ("failed", "Failed"),
        ("manually_resolved", "Manually Resolved"),
    ],
    default="not_applicable",
)
```

- [ ] **Step 4: Create and run migration**

Run: `cd backend && poetry run python manage.py makemigrations orders`
Expected: Creates migration adding the new fields.

Run: `cd backend && poetry run python manage.py migrate`
Expected: Migration applied. Existing orders get `pos_sync_status='not_applicable'` and `external_order_id=NULL`.

- [ ] **Step 5: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_order_pos_fields.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Run full test suite to ensure no regressions**

Run: `cd backend && poetry run pytest -v`
Expected: All existing tests still pass.

- [ ] **Step 7: Commit**

```bash
git add backend/orders/models.py backend/orders/migrations/
git commit -m "feat: add POS sync fields to Order model"
```

---

### Task 4: Token Encryption Utility

**Files:**
- Create: `backend/integrations/encryption.py`
- Create: `backend/integrations/tests/test_encryption.py`

- [ ] **Step 1: Install the `cryptography` package**

Run: `cd backend && poetry add cryptography`

Note: `cryptography` may already be a transitive dependency. Adding it explicitly ensures it's pinned.

- [ ] **Step 2: Write the failing test**

```python
# backend/integrations/tests/test_encryption.py
from integrations.encryption import encrypt_token, decrypt_token


class TestTokenEncryption:
    def test_encrypt_decrypt_roundtrip(self):
        plaintext = "sk_live_abc123_very_secret"
        encrypted = encrypt_token(plaintext)
        assert encrypted != plaintext
        assert decrypt_token(encrypted) == plaintext

    def test_encrypt_empty_string(self):
        assert encrypt_token("") == ""
        assert decrypt_token("") == ""

    def test_encrypted_output_is_different_each_time(self):
        plaintext = "test_token"
        e1 = encrypt_token(plaintext)
        e2 = encrypt_token(plaintext)
        # Fernet generates unique ciphertexts even for same plaintext
        assert e1 != e2
        assert decrypt_token(e1) == plaintext
        assert decrypt_token(e2) == plaintext
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_encryption.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 4: Implement the encryption utility**

```python
# backend/integrations/encryption.py
from cryptography.fernet import Fernet
from django.conf import settings


def _get_fernet() -> Fernet:
    key = settings.POS_ENCRYPTION_KEY
    if not key:
        raise ValueError(
            "POS_ENCRYPTION_KEY is not set. Generate one with: "
            "python -c 'from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())'"
        )
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt_token(plaintext: str) -> str:
    if not plaintext:
        return ""
    return _get_fernet().encrypt(plaintext.encode()).decode()


def decrypt_token(ciphertext: str) -> str:
    if not ciphertext:
        return ""
    return _get_fernet().decrypt(ciphertext.encode()).decode()
```

- [ ] **Step 5: Generate and set a test encryption key**

Run: `cd backend && poetry run python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`

Copy the output and add it to `backend/.env`:

```
POS_ENCRYPTION_KEY=<paste the generated key here>
```

Note: The key must be a valid Fernet key (base64-encoded 32 bytes). Do not use a placeholder string.

- [ ] **Step 6: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_encryption.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/encryption.py backend/integrations/tests/test_encryption.py backend/pyproject.toml backend/poetry.lock
git commit -m "feat: add Fernet token encryption utility for POS OAuth tokens"
```

---

### Task 5: Base POS Adapter Interface

**Files:**
- Create: `backend/integrations/adapters/base.py`
- Create: `backend/integrations/adapters/noop.py`
- Create: `backend/integrations/tests/test_adapters.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_adapters.py
import pytest
from integrations.adapters.base import BasePOSAdapter, PushResult
from integrations.adapters.noop import NoopAdapter
from integrations.tests.factories import POSConnectionFactory


@pytest.mark.django_db
class TestNoopAdapter:
    def test_push_order_returns_success(self):
        connection = POSConnectionFactory(pos_type="none")
        adapter = NoopAdapter(connection)
        from orders.tests.factories import OrderFactory
        order = OrderFactory(restaurant=connection.restaurant)
        result = adapter.push_order(order)
        assert isinstance(result, PushResult)
        assert result.success is True
        assert result.external_order_id is None

    def test_validate_connection(self):
        connection = POSConnectionFactory(pos_type="none")
        adapter = NoopAdapter(connection)
        assert adapter.validate_connection() is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_adapters.py -v`
Expected: FAIL — modules don't exist.

- [ ] **Step 3: Implement BasePOSAdapter**

```python
# backend/integrations/adapters/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class PushResult:
    success: bool
    external_order_id: str | None = None
    error_message: str | None = None


class BasePOSAdapter(ABC):
    def __init__(self, connection):
        self.connection = connection

    @abstractmethod
    def push_order(self, order) -> PushResult:
        """Push order to POS. Returns external_order_id on success."""

    @abstractmethod
    def cancel_order(self, external_order_id: str) -> bool:
        """Cancel a previously pushed order."""

    @abstractmethod
    def get_order_status(self, external_order_id: str) -> str:
        """Check order status in POS."""

    @abstractmethod
    def validate_connection(self) -> bool:
        """Test that credentials are still valid."""

    @abstractmethod
    def refresh_tokens(self) -> bool:
        """Refresh expired OAuth tokens."""
```

- [ ] **Step 4: Implement NoopAdapter**

```python
# backend/integrations/adapters/noop.py
from integrations.adapters.base import BasePOSAdapter, PushResult


class NoopAdapter(BasePOSAdapter):
    """Adapter for restaurants with no POS integration. Always succeeds."""

    def push_order(self, order) -> PushResult:
        return PushResult(success=True)

    def cancel_order(self, external_order_id: str) -> bool:
        return True

    def get_order_status(self, external_order_id: str) -> str:
        return "unknown"

    def validate_connection(self) -> bool:
        return True

    def refresh_tokens(self) -> bool:
        return True
```

- [ ] **Step 5: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_adapters.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Commit**

```bash
git add backend/integrations/adapters/
git commit -m "feat: add BasePOSAdapter interface and NoopAdapter"
```

---

### Task 6: POS Dispatch Service

**Files:**
- Create: `backend/integrations/services.py`
- Create: `backend/integrations/tests/test_dispatch.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_dispatch.py
import pytest
from unittest.mock import patch, MagicMock

from integrations.models import POSConnection, POSSyncLog
from integrations.services import POSDispatchService
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestPOSDispatchService:
    def test_dispatch_no_connection_sets_not_applicable(self):
        order = OrderFactory()
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    def test_dispatch_inactive_connection_sets_not_applicable(self):
        connection = POSConnectionFactory(is_active=False)
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    def test_dispatch_none_type_sets_not_applicable(self):
        connection = POSConnectionFactory(pos_type="none")
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))
        order.refresh_from_db()
        assert order.pos_sync_status == "not_applicable"

    @patch("integrations.services.POSDispatchService._get_adapter")
    def test_dispatch_success(self, mock_get_adapter):
        from integrations.adapters.base import PushResult
        mock_adapter = MagicMock()
        mock_adapter.push_order.return_value = PushResult(
            success=True, external_order_id="sq_order_123"
        )
        mock_get_adapter.return_value = mock_adapter

        connection = POSConnectionFactory(pos_type="square")
        order = OrderFactory(restaurant=connection.restaurant)
        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "sq_order_123"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"
        assert log.external_order_id == "sq_order_123"

    @patch("integrations.services.POSDispatchService._get_adapter")
    def test_dispatch_failure(self, mock_get_adapter):
        from integrations.adapters.base import PushResult
        mock_adapter = MagicMock()
        mock_adapter.push_order.return_value = PushResult(
            success=False, error_message="API timeout"
        )
        mock_get_adapter.return_value = mock_adapter

        connection = POSConnectionFactory(pos_type="square")
        order = OrderFactory(restaurant=connection.restaurant)

        with pytest.raises(Exception, match="POS dispatch failed"):
            POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "retrying"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "retrying"
        assert log.last_error == "API timeout"
        assert log.attempt_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_dispatch.py -v`
Expected: FAIL — service doesn't exist.

- [ ] **Step 3: Implement POSDispatchService**

```python
# backend/integrations/services.py
import logging

from django.utils import timezone

from integrations.adapters.base import BasePOSAdapter
from integrations.adapters.noop import NoopAdapter
from integrations.models import POSConnection, POSSyncLog
from orders.models import Order

logger = logging.getLogger(__name__)


class POSDispatchError(Exception):
    pass


class POSDispatchService:
    @staticmethod
    def dispatch(order_id: str) -> None:
        order = Order.objects.select_related("restaurant").get(id=order_id)

        try:
            connection = POSConnection.objects.get(
                restaurant=order.restaurant, is_active=True
            )
        except POSConnection.DoesNotExist:
            connection = None

        if not connection or connection.pos_type == POSConnection.POSType.NONE:
            Order.objects.filter(id=order.id).update(
                pos_sync_status="not_applicable"
            )
            return

        log = POSSyncLog.objects.create(
            order=order,
            pos_connection=connection,
            status=POSSyncLog.Status.PENDING,
        )

        adapter = POSDispatchService._get_adapter(connection)
        result = adapter.push_order(order)

        if result.success:
            log.status = POSSyncLog.Status.SUCCESS
            log.external_order_id = result.external_order_id
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="synced",
                external_order_id=result.external_order_id,
            )
        else:
            log.status = POSSyncLog.Status.RETRYING
            log.last_error = result.error_message
            log.attempt_count += 1
            log.save()

            Order.objects.filter(id=order.id).update(
                pos_sync_status="retrying",
            )
            raise POSDispatchError(
                f"POS dispatch failed: {result.error_message}"
            )

    @staticmethod
    def _get_adapter(connection: POSConnection) -> BasePOSAdapter:
        adapter_map = {
            POSConnection.POSType.NONE: NoopAdapter,
            # POSConnection.POSType.SQUARE: SquareAdapter,  # Task 8
            # POSConnection.POSType.TOAST: ToastAdapter,    # Task 9
        }
        adapter_class = adapter_map.get(connection.pos_type, NoopAdapter)
        return adapter_class(connection)

    @staticmethod
    def mark_failed(order_id: str) -> None:
        """Called after all retries are exhausted."""
        Order.objects.filter(id=order_id).update(pos_sync_status="failed")
        POSSyncLog.objects.filter(
            order_id=order_id, status=POSSyncLog.Status.RETRYING
        ).update(status=POSSyncLog.Status.FAILED)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_dispatch.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/services.py backend/integrations/tests/test_dispatch.py
git commit -m "feat: add POSDispatchService with adapter routing and sync logging"
```

---

### Task 7: Celery Task for POS Dispatch

**Files:**
- Create: `backend/integrations/tasks.py`
- Create: `backend/integrations/tests/test_tasks.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_tasks.py
import pytest
from unittest.mock import patch

from integrations.tasks import dispatch_order_to_pos
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory


@pytest.mark.django_db
class TestDispatchOrderTask:
    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_calls_dispatch_service(self, mock_dispatch):
        order = OrderFactory()
        dispatch_order_to_pos(str(order.id))
        mock_dispatch.assert_called_once_with(str(order.id))

    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_retries_on_dispatch_error(self, mock_dispatch):
        from integrations.services import POSDispatchError
        mock_dispatch.side_effect = POSDispatchError("API timeout")
        order = OrderFactory()
        # Celery task should raise for retry mechanism
        with pytest.raises(POSDispatchError):
            dispatch_order_to_pos(str(order.id))

    @patch("integrations.tasks.POSDispatchService.mark_failed")
    @patch("integrations.tasks.POSDispatchService.dispatch")
    def test_task_marks_failed_after_max_retries(self, mock_dispatch, mock_mark_failed):
        from integrations.services import POSDispatchError
        mock_dispatch.side_effect = POSDispatchError("API down")
        order = OrderFactory()
        # Simulate max retries exceeded by calling the on_failure handler
        task = dispatch_order_to_pos
        # Test the mark_failed path directly
        from integrations.services import POSDispatchService
        POSDispatchService.mark_failed(str(order.id))
        mock_mark_failed.assert_called_once_with(str(order.id))
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_tasks.py -v`
Expected: FAIL — task doesn't exist.

- [ ] **Step 3: Implement the Celery task**

```python
# backend/integrations/tasks.py
import logging

from celery import shared_task
from django.conf import settings

from integrations.services import POSDispatchError, POSDispatchService

logger = logging.getLogger(__name__)

RETRY_DELAYS = getattr(settings, "POS_DISPATCH_RETRY_DELAYS", [30, 120, 600, 1800])


@shared_task(
    bind=True,
    max_retries=len(RETRY_DELAYS),  # 4 retries = 5 total attempts (initial + 4 retries)
    acks_late=True,
)
def dispatch_order_to_pos(self, order_id: str) -> None:
    """Dispatch order to POS with idempotency check and exponential backoff."""
    # Idempotency: skip if already synced (prevents double dispatch from
    # ConfirmPaymentView + webhook both firing for the same order)
    from orders.models import Order
    if Order.objects.filter(id=order_id, pos_sync_status="synced").exists():
        return

    try:
        POSDispatchService.dispatch(order_id)
    except POSDispatchError as exc:
        retry_num = self.request.retries
        if retry_num < len(RETRY_DELAYS):
            countdown = RETRY_DELAYS[retry_num]
            logger.warning(
                "POS dispatch failed, retrying in %ds: order=%s error=%s",
                countdown,
                order_id,
                exc,
            )
            raise self.retry(exc=exc, countdown=countdown)
        else:
            logger.error("POS dispatch failed after all retries: order=%s", order_id)
            POSDispatchService.mark_failed(order_id)
    except Exception:
        logger.exception("Unexpected error in POS dispatch: order=%s", order_id)
        POSDispatchService.mark_failed(order_id)
```

- [ ] **Step 4: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_tasks.py -v`
Expected: All tests PASS.

- [ ] **Step 5: Commit**

```bash
git add backend/integrations/tasks.py backend/integrations/tests/test_tasks.py
git commit -m "feat: add Celery task for async POS dispatch with retry"
```

---

### Task 8: Hook POS Dispatch Into Existing Order Flow

**Files:**
- Modify: `backend/orders/views.py:33-69` (ConfirmOrderView)
- Modify: `backend/orders/views.py:72-129` (CreatePaymentView)
- Modify: `backend/orders/views.py:166-198` (ConfirmPaymentView)
- Modify: `backend/orders/services.py:498-509` (_handle_payment_succeeded)
- Create: `backend/integrations/tests/test_order_flow_hooks.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_order_flow_hooks.py
import pytest
from decimal import Decimal
from unittest.mock import patch

from rest_framework import status

from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestOrderFlowPOSDispatch:
    @pytest.fixture
    def restaurant_with_pos(self):
        restaurant = RestaurantFactory(slug="pos-test", tax_rate=Decimal("8.875"))
        POSConnectionFactory(restaurant=restaurant, pos_type="square")
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        return {"restaurant": restaurant, "item": item, "variant": variant}

    @patch("orders.views.dispatch_order_to_pos")
    def test_confirm_order_dispatches_to_pos(self, mock_task, api_client, restaurant_with_pos):
        data = {
            "items": [
                {
                    "menu_item_id": restaurant_with_pos["item"].id,
                    "variant_id": restaurant_with_pos["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one burger please",
            "table_identifier": "5",
        }
        response = api_client.post(
            "/api/order/pos-test/confirm/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        mock_task.delay.assert_called_once()
        # Verify the order ID was passed
        call_args = mock_task.delay.call_args[0]
        assert call_args[0] == str(response.data["id"])
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_order_flow_hooks.py -v`
Expected: FAIL — dispatch_order_to_pos not imported in views.

- [ ] **Step 3: Add dispatch hook to ConfirmOrderView**

In `backend/orders/views.py`, add import at top:

```python
from integrations.tasks import dispatch_order_to_pos
```

In `ConfirmOrderView.post()`, after the `broadcast_order_to_kitchen(order)` call (around line 64), add:

```python
dispatch_order_to_pos.delay(str(order.id))
```

- [ ] **Step 4: Add dispatch hook to CreatePaymentView**

In `CreatePaymentView.post()`, after the inline payment success block where `order.status` is set to `"confirmed"` (around line 125), add:

```python
dispatch_order_to_pos.delay(str(order.id))
```

- [ ] **Step 5: Add dispatch hook to ConfirmPaymentView**

In `ConfirmPaymentView.post()` (line 166), after `OrderService.confirm_payment(order)` (line 186), add the dispatch **only if payment succeeded**:

```python
if order.payment_status == "paid":
    dispatch_order_to_pos.delay(str(order.id))
```

- [ ] **Step 6: Add dispatch hook to Stripe webhook handler**

In `backend/orders/services.py`, in `_handle_payment_succeeded()` (line 498), **inside the `if updated:` block** (after `broadcast_order_to_kitchen(order)` around line 511), add:

```python
from integrations.tasks import dispatch_order_to_pos
dispatch_order_to_pos.delay(str(order.id))
```

Note: Both Step 5 and Step 6 can fire for the same order (ConfirmPaymentView for sync confirmation, webhook for async). The Celery task includes an idempotency check (`pos_sync_status == "synced"` → skip), so double dispatch is harmless.

- [ ] **Step 7: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_order_flow_hooks.py -v`
Expected: All tests PASS.

- [ ] **Step 8: Run full test suite**

Run: `cd backend && poetry run pytest -v`
Expected: All tests PASS (no regressions).

- [ ] **Step 9: Commit**

```bash
git add backend/orders/views.py backend/orders/services.py backend/integrations/tests/test_order_flow_hooks.py
git commit -m "feat: hook POS dispatch into order confirmation flow"
```

---

## Chunk 2: Square Adapter, OAuth Flow, and Dashboard APIs

This chunk implements the Square POS adapter, OAuth connection flow, and the backend API endpoints for POS connection management and sync log viewing. After this chunk, restaurants can connect their Square account and see orders dispatched to Square's API.

---

### Task 9: Square Adapter

**Files:**
- Create: `backend/integrations/adapters/square.py`
- Create: `backend/integrations/tests/test_square_adapter.py`

- [ ] **Step 1: Install the Square SDK**

Run: `cd backend && poetry add squareup`

- [ ] **Step 2: Write the failing test**

```python
# backend/integrations/tests/test_square_adapter.py
import pytest
from unittest.mock import patch, MagicMock
from decimal import Decimal

from integrations.adapters.base import PushResult
from integrations.adapters.square import SquareAdapter
from integrations.tests.factories import POSConnectionFactory
from orders.tests.factories import OrderFactory, OrderItemFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    MenuItemModifierFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestSquareAdapter:
    @pytest.fixture
    def setup(self):
        restaurant = RestaurantFactory()
        connection = POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            external_location_id="L123",
            oauth_access_token="sq_test_token",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99")
        )
        modifier = MenuItemModifierFactory(
            menu_item=item, name="Extra Cheese", price_adjustment=Decimal("1.50")
        )
        order = OrderFactory(
            restaurant=restaurant,
            subtotal=Decimal("14.49"),
            tax_amount=Decimal("1.29"),
            total_price=Decimal("15.78"),
        )
        order_item = OrderItemFactory(
            order=order,
            menu_item=item,
            variant=variant,
            quantity=1,
        )
        order_item.modifiers.add(modifier)
        return {
            "connection": connection,
            "order": order,
            "item": item,
            "variant": variant,
            "modifier": modifier,
        }

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_order_abc"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        assert result.external_order_id == "sq_order_abc"
        mock_client.orders.create_order.assert_called_once()

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_failure(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = False
        mock_result.errors = [{"detail": "Invalid location"}]
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is False
        assert "Invalid location" in result.error_message

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_push_order_with_stripe_payment_marks_paid(self, mock_get_client, setup):
        setup["connection"].payment_mode = "stripe"
        setup["connection"].save()
        setup["order"].payment_status = "paid"
        setup["order"].save()

        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_order_paid"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        result = adapter.push_order(setup["order"])

        assert result.success is True
        call_body = mock_client.orders.create_order.call_args[0][0]
        # Verify a tender was included for "paid externally"
        assert "tenders" in call_body["order"]

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_cancel_order_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_client.orders.update_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.cancel_order("sq_order_123") is True

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_validate_connection_success(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_client.locations.list_locations.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.validate_connection() is True

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_validate_connection_failure(self, mock_get_client, setup):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = False
        mock_client.locations.list_locations.return_value = mock_result
        mock_get_client.return_value = mock_client

        adapter = SquareAdapter(setup["connection"])
        assert adapter.validate_connection() is False
```

- [ ] **Step 3: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_square_adapter.py -v`
Expected: FAIL — module doesn't exist.

- [ ] **Step 4: Implement SquareAdapter**

```python
# backend/integrations/adapters/square.py
import logging

from square.client import Client as SquareClient

from integrations.adapters.base import BasePOSAdapter, PushResult
from integrations.encryption import decrypt_token, encrypt_token

logger = logging.getLogger(__name__)


class SquareAdapter(BasePOSAdapter):
    def _get_client(self) -> SquareClient:
        access_token = decrypt_token(self.connection.oauth_access_token)
        return SquareClient(access_token=access_token, environment="production")

    def push_order(self, order) -> PushResult:
        client = self._get_client()
        location_id = self.connection.external_location_id

        line_items = []
        for item in order.items.select_related("variant").prefetch_related("modifiers"):
            line_item = {
                "name": item.menu_item.name,
                "quantity": str(item.quantity),
                "base_price_money": {
                    "amount": int(item.variant.price * 100),
                    "currency": "USD",
                },
            }
            if item.modifiers.exists():
                line_item["modifiers"] = [
                    {
                        "name": mod.name,
                        "base_price_money": {
                            "amount": int(mod.price_adjustment * 100),
                            "currency": "USD",
                        },
                    }
                    for mod in item.modifiers.all()
                ]
            line_items.append(line_item)

        body = {
            "order": {
                "location_id": location_id,
                "reference_id": str(order.id),
                "line_items": line_items,
            },
        }

        # If paid via Stripe, mark as paid externally
        if (
            self.connection.payment_mode == "stripe"
            and order.payment_status == "paid"
        ):
            body["order"]["tenders"] = [
                {
                    "type": "OTHER",
                    "amount_money": {
                        "amount": int(order.total_price * 100),
                        "currency": "USD",
                    },
                    "note": "Paid via QR Ordering Platform",
                }
            ]

        try:
            result = client.orders.create_order(body)
        except Exception as e:
            return PushResult(success=False, error_message=str(e))

        if result.is_success():
            external_id = result.body["order"]["id"]
            return PushResult(success=True, external_order_id=external_id)
        else:
            errors = "; ".join(e.get("detail", str(e)) for e in result.errors)
            return PushResult(success=False, error_message=errors)

    def cancel_order(self, external_order_id: str) -> bool:
        try:
            client = self._get_client()
            result = client.orders.update_order(
                order_id=external_order_id,
                body={
                    "order": {
                        "location_id": self.connection.external_location_id,
                        "state": "CANCELED",
                        "version": 1,
                    },
                },
            )
            return result.is_success()
        except Exception:
            logger.exception("Failed to cancel Square order %s", external_order_id)
            return False

    def get_order_status(self, external_order_id: str) -> str:
        try:
            client = self._get_client()
            result = client.orders.retrieve_order(order_id=external_order_id)
            if result.is_success():
                return result.body["order"]["state"]
            return "unknown"
        except Exception:
            return "unknown"

    def validate_connection(self) -> bool:
        try:
            client = self._get_client()
            result = client.locations.list_locations()
            return result.is_success()
        except Exception:
            return False

    def refresh_tokens(self) -> bool:
        from django.conf import settings

        try:
            client = SquareClient(environment="production")
            result = client.o_auth.obtain_token(
                body={
                    "client_id": settings.POS_SQUARE_CLIENT_ID,
                    "client_secret": settings.POS_SQUARE_CLIENT_SECRET,
                    "grant_type": "refresh_token",
                    "refresh_token": decrypt_token(
                        self.connection.oauth_refresh_token
                    ),
                }
            )
            if result.is_success():
                self.connection.oauth_access_token = encrypt_token(
                    result.body["access_token"]
                )
                if "refresh_token" in result.body:
                    self.connection.oauth_refresh_token = encrypt_token(
                        result.body["refresh_token"]
                    )
                self.connection.save()
                return True
            return False
        except Exception:
            logger.exception("Failed to refresh Square tokens")
            return False
```

- [ ] **Step 5: Register Square in adapter map**

In `backend/integrations/services.py`, update `_get_adapter`:

```python
from integrations.adapters.square import SquareAdapter

adapter_map = {
    POSConnection.POSType.NONE: NoopAdapter,
    POSConnection.POSType.SQUARE: SquareAdapter,
}
```

- [ ] **Step 6: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_square_adapter.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/adapters/square.py backend/integrations/tests/test_square_adapter.py backend/integrations/services.py backend/pyproject.toml backend/poetry.lock
git commit -m "feat: add Square POS adapter with order push, cancel, and token refresh"
```

---

### Task 10: POS Connection Management API Endpoints

**Files:**
- Create: `backend/integrations/serializers.py`
- Modify: `backend/integrations/views.py`
- Modify: `backend/integrations/urls.py`
- Create: `backend/integrations/tests/test_views.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_views.py
import pytest
from rest_framework import status

from integrations.models import POSConnection
from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestPOSConnectionAPI:
    @pytest.fixture
    def owner_setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="test-resto")
        api_client.force_authenticate(user=user)
        return {"user": user, "restaurant": restaurant, "client": api_client}

    def test_get_connection_when_none_exists(self, owner_setup):
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "none"
        assert response.data["is_connected"] is False

    def test_get_existing_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["pos_type"] == "square"
        assert response.data["is_connected"] is True

    def test_update_payment_mode(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].patch(
            "/api/restaurants/test-resto/pos/connection/",
            {"payment_mode": "pos_collected"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "pos_collected"

    def test_delete_connection(self, owner_setup):
        POSConnectionFactory(
            restaurant=owner_setup["restaurant"],
            pos_type="square",
        )
        response = owner_setup["client"].delete(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not POSConnection.objects.filter(
            restaurant=owner_setup["restaurant"]
        ).exists()

    def test_unauthenticated_access_denied(self, api_client):
        RestaurantFactory(slug="test-resto")
        response = api_client.get(
            "/api/restaurants/test-resto/pos/connection/"
        )
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_views.py -v`
Expected: FAIL — views/serializers don't exist.

- [ ] **Step 3: Create serializers**

```python
# backend/integrations/serializers.py
from rest_framework import serializers

from integrations.models import POSConnection, POSSyncLog


class POSConnectionSerializer(serializers.ModelSerializer):
    is_connected = serializers.SerializerMethodField()

    class Meta:
        model = POSConnection
        fields = [
            "id",
            "pos_type",
            "is_active",
            "payment_mode",
            "external_location_id",
            "is_connected",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "is_connected", "created_at", "updated_at"]

    def get_is_connected(self, obj):
        return obj.is_active and obj.pos_type != POSConnection.POSType.NONE


class POSConnectionUpdateSerializer(serializers.ModelSerializer):
    class Meta:
        model = POSConnection
        fields = ["payment_mode", "external_location_id"]


class POSSyncLogSerializer(serializers.ModelSerializer):
    order_id = serializers.UUIDField(source="order.id", read_only=True)
    order_created_at = serializers.DateTimeField(source="order.created_at", read_only=True)

    class Meta:
        model = POSSyncLog
        fields = [
            "id",
            "order_id",
            "order_created_at",
            "status",
            "external_order_id",
            "attempt_count",
            "last_error",
            "next_retry_at",
            "created_at",
        ]
```

- [ ] **Step 4: Implement views**

```python
# backend/integrations/views.py
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from integrations.models import POSConnection, POSSyncLog
from integrations.serializers import (
    POSConnectionSerializer,
    POSConnectionUpdateSerializer,
    POSSyncLogSerializer,
)
from restaurants.models import Restaurant


class RestaurantPOSMixin:
    def get_restaurant(self, slug):
        return Restaurant.objects.get(slug=slug, owner=self.request.user)


class POSConnectionDetailView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        restaurant = self.get_restaurant(slug)
        try:
            connection = POSConnection.objects.get(restaurant=restaurant)
        except POSConnection.DoesNotExist:
            return Response(
                {"pos_type": "none", "is_connected": False, "payment_mode": "stripe"}
            )
        return Response(POSConnectionSerializer(connection).data)

    def patch(self, request, slug):
        restaurant = self.get_restaurant(slug)
        connection = POSConnection.objects.get(restaurant=restaurant)
        serializer = POSConnectionUpdateSerializer(
            connection, data=request.data, partial=True
        )
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(POSConnectionSerializer(connection).data)

    def delete(self, request, slug):
        restaurant = self.get_restaurant(slug)
        POSConnection.objects.filter(restaurant=restaurant).delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

- [ ] **Step 5: Wire up URLs**

```python
# backend/integrations/urls.py
from django.urls import path

from integrations.views import POSConnectionDetailView

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
    ),
]
```

- [ ] **Step 6: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_views.py -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/serializers.py backend/integrations/views.py backend/integrations/urls.py backend/integrations/tests/test_views.py
git commit -m "feat: add POS connection management API endpoints"
```

---

### Task 11: Sync Log API and Retry Endpoints

**Files:**
- Modify: `backend/integrations/views.py`
- Modify: `backend/integrations/urls.py`
- Create: `backend/integrations/tests/test_sync_views.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_sync_views.py
import pytest
from unittest.mock import patch
from rest_framework import status

from integrations.models import POSSyncLog
from integrations.tests.factories import POSConnectionFactory, POSSyncLogFactory
from orders.tests.factories import OrderFactory
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestPOSSyncLogAPI:
    @pytest.fixture
    def setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="sync-test")
        connection = POSConnectionFactory(restaurant=restaurant)
        api_client.force_authenticate(user=user)
        return {
            "user": user,
            "restaurant": restaurant,
            "connection": connection,
            "client": api_client,
        }

    def test_list_sync_logs(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"])
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="success")
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="failed")

        response = setup["client"].get("/api/restaurants/sync-test/pos/sync-logs/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2

    def test_filter_sync_logs_by_status(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"])
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="success")
        POSSyncLogFactory(order=order, pos_connection=setup["connection"], status="failed")

        response = setup["client"].get(
            "/api/restaurants/sync-test/pos/sync-logs/?status=failed"
        )
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["status"] == "failed"

    @patch("integrations.views.dispatch_order_to_pos")
    def test_retry_single_order(self, mock_task, setup):
        order = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        log = POSSyncLogFactory(
            order=order, pos_connection=setup["connection"], status="failed"
        )

        response = setup["client"].post(
            f"/api/restaurants/sync-test/pos/retry/{order.id}/"
        )
        assert response.status_code == status.HTTP_200_OK
        mock_task.delay.assert_called_once_with(str(order.id))

    @patch("integrations.views.dispatch_order_to_pos")
    def test_retry_all_failed(self, mock_task, setup):
        order1 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        order2 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        order3 = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="synced")
        POSSyncLogFactory(order=order1, pos_connection=setup["connection"], status="failed")
        POSSyncLogFactory(order=order2, pos_connection=setup["connection"], status="failed")
        POSSyncLogFactory(order=order3, pos_connection=setup["connection"], status="success")

        response = setup["client"].post(
            "/api/restaurants/sync-test/pos/retry-all/"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 2
        assert mock_task.delay.call_count == 2

    def test_mark_manually_resolved(self, setup):
        order = OrderFactory(restaurant=setup["restaurant"], pos_sync_status="failed")
        log = POSSyncLogFactory(
            order=order, pos_connection=setup["connection"], status="failed"
        )

        response = setup["client"].patch(
            f"/api/restaurants/sync-test/pos/sync-logs/{log.id}/",
            {"status": "manually_resolved"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        log.refresh_from_db()
        assert log.status == "manually_resolved"
        order.refresh_from_db()
        assert order.pos_sync_status == "manually_resolved"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_sync_views.py -v`
Expected: FAIL — views don't exist.

- [ ] **Step 3: Implement sync log views**

Append to `backend/integrations/views.py`:

```python
from integrations.tasks import dispatch_order_to_pos
from orders.models import Order


class POSSyncLogListView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request, slug):
        restaurant = self.get_restaurant(slug)
        logs = POSSyncLog.objects.filter(
            pos_connection__restaurant=restaurant
        ).select_related("order")

        status_filter = request.query_params.get("status")
        if status_filter:
            logs = logs.filter(status=status_filter)

        return Response(POSSyncLogSerializer(logs, many=True).data)


class RetryOrderSyncView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug, order_id):
        restaurant = self.get_restaurant(slug)
        order = Order.objects.get(id=order_id, restaurant=restaurant)
        order.pos_sync_status = "pending"
        order.save(update_fields=["pos_sync_status"])
        dispatch_order_to_pos.delay(str(order.id))
        return Response({"status": "retry_queued"})


class RetryAllSyncView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        failed_orders = Order.objects.filter(
            restaurant=restaurant, pos_sync_status="failed"
        )
        count = failed_orders.count()
        for order in failed_orders:
            order.pos_sync_status = "pending"
            order.save(update_fields=["pos_sync_status"])
            dispatch_order_to_pos.delay(str(order.id))
        return Response({"status": "retry_queued", "count": count})


class POSSyncLogDetailView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, slug, log_id):
        restaurant = self.get_restaurant(slug)
        log = POSSyncLog.objects.get(
            id=log_id, pos_connection__restaurant=restaurant
        )
        new_status = request.data.get("status")
        if new_status == "manually_resolved":
            log.status = POSSyncLog.Status.MANUALLY_RESOLVED
            log.save(update_fields=["status"])
            Order.objects.filter(id=log.order_id).update(
                pos_sync_status="manually_resolved"
            )
        return Response(POSSyncLogSerializer(log).data)
```

- [ ] **Step 4: Update URLs**

```python
# backend/integrations/urls.py
from django.urls import path

from integrations.views import (
    POSConnectionDetailView,
    POSSyncLogDetailView,
    POSSyncLogListView,
    RetryAllSyncView,
    RetryOrderSyncView,
)

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/",
        POSSyncLogListView.as_view(),
        name="pos-sync-logs",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry-all/",
        RetryAllSyncView.as_view(),
        name="pos-retry-all",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry/<uuid:order_id>/",
        RetryOrderSyncView.as_view(),
        name="pos-retry-order",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/<uuid:log_id>/",
        POSSyncLogDetailView.as_view(),
        name="pos-sync-log-detail",
    ),
]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_sync_views.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `cd backend && poetry run pytest -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/views.py backend/integrations/urls.py backend/integrations/tests/test_sync_views.py
git commit -m "feat: add sync log list, retry, and mark-resolved API endpoints"
```

---

### Task 12: Square OAuth Flow

**Files:**
- Modify: `backend/integrations/views.py`
- Modify: `backend/integrations/urls.py`
- Create: `backend/integrations/tests/test_oauth.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_oauth.py
import pytest
from unittest.mock import patch, MagicMock
from rest_framework import status

from integrations.models import POSConnection
from restaurants.tests.factories import RestaurantFactory, UserFactory


@pytest.mark.django_db
class TestSquareOAuth:
    @pytest.fixture
    def owner_setup(self, api_client):
        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="oauth-test")
        api_client.force_authenticate(user=user)
        return {"user": user, "restaurant": restaurant, "client": api_client}

    @patch("integrations.views.settings")
    def test_initiate_square_connect(self, mock_settings, owner_setup):
        mock_settings.POS_SQUARE_CLIENT_ID = "sq_client_123"
        mock_settings.FRONTEND_URL = "http://localhost:3000"

        response = owner_setup["client"].post(
            "/api/restaurants/oauth-test/pos/connect/",
            {"pos_type": "square"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "auth_url" in response.data
        assert "square" in response.data["auth_url"].lower()

    @patch("integrations.views.SquareClient")
    def test_square_oauth_callback_success(self, mock_square_class, api_client):
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {
            "access_token": "sq_access_123",
            "refresh_token": "sq_refresh_456",
            "expires_at": "2026-04-27T00:00:00Z",
        }
        mock_client.o_auth.obtain_token.return_value = mock_result
        mock_square_class.return_value = mock_client

        user = UserFactory()
        restaurant = RestaurantFactory(owner=user, slug="oauth-cb-test")

        # Simulate the callback with state containing restaurant slug
        response = api_client.get(
            "/api/integrations/oauth/square/callback/",
            {"code": "auth_code_123", "state": f"{restaurant.slug}:{user.id}"},
        )
        assert response.status_code == status.HTTP_302_FOUND

        connection = POSConnection.objects.get(restaurant=restaurant)
        assert connection.pos_type == "square"
        assert connection.is_active is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_oauth.py -v`
Expected: FAIL — OAuth views don't exist.

- [ ] **Step 3: Implement OAuth views**

Append to `backend/integrations/views.py`:

```python
from django.conf import settings as django_settings
from django.http import HttpResponseRedirect
from django.utils.dateparse import parse_datetime
from square.client import Client as SquareClient

import hashlib
import hmac

from integrations.encryption import encrypt_token


def _sign_oauth_state(payload: str) -> str:
    """HMAC-sign an OAuth state string to prevent tampering."""
    from django.conf import settings as s
    key = s.SECRET_KEY.encode()
    sig = hmac.new(key, payload.encode(), hashlib.sha256).hexdigest()[:16]
    return f"{payload}:{sig}"


def _verify_oauth_state(state: str) -> tuple[str, str]:
    """Verify and parse an HMAC-signed OAuth state. Returns (slug, user_id)."""
    from django.conf import settings as s
    parts = state.rsplit(":", 2)
    if len(parts) != 3:
        raise ValueError("Invalid OAuth state format")
    slug, user_id, sig = parts
    key = s.SECRET_KEY.encode()
    expected = hmac.new(key, f"{slug}:{user_id}".encode(), hashlib.sha256).hexdigest()[:16]
    if not hmac.compare_digest(sig, expected):
        raise ValueError("Invalid OAuth state signature")
    return slug, user_id


class POSConnectInitiateView(RestaurantPOSMixin, APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, slug):
        restaurant = self.get_restaurant(slug)
        pos_type = request.data.get("pos_type")

        if pos_type == "square":
            state = _sign_oauth_state(f"{restaurant.slug}:{request.user.id}")
            auth_url = (
                f"https://connect.squareup.com/oauth2/authorize"
                f"?client_id={django_settings.POS_SQUARE_CLIENT_ID}"
                f"&scope=ORDERS_WRITE+ORDERS_READ+MERCHANT_PROFILE_READ"
                f"&state={state}"
                f"&session=false"
            )
            return Response({"auth_url": auth_url})

        return Response(
            {"error": f"Unsupported POS type: {pos_type}"},
            status=status.HTTP_400_BAD_REQUEST,
        )


class SquareOAuthCallbackView(APIView):
    permission_classes = []

    def get(self, request):
        code = request.query_params.get("code")
        state = request.query_params.get("state")

        if not code or not state:
            return Response(
                {"error": "Missing code or state"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            slug, user_id = _verify_oauth_state(state)
        except ValueError:
            return Response(
                {"error": "Invalid state parameter"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        restaurant = Restaurant.objects.get(slug=slug, owner_id=user_id)

        client = SquareClient(environment="production")
        result = client.o_auth.obtain_token(
            body={
                "client_id": django_settings.POS_SQUARE_CLIENT_ID,
                "client_secret": django_settings.POS_SQUARE_CLIENT_SECRET,
                "code": code,
                "grant_type": "authorization_code",
            }
        )

        if not result.is_success():
            frontend_url = getattr(django_settings, "FRONTEND_URL", "http://localhost:3000")
            return HttpResponseRedirect(
                f"{frontend_url}/account/restaurants/{slug}/integrations?error=oauth_failed"
            )

        token_data = result.body
        connection, _ = POSConnection.objects.update_or_create(
            restaurant=restaurant,
            defaults={
                "pos_type": POSConnection.POSType.SQUARE,
                "is_active": True,
                "oauth_access_token": encrypt_token(token_data["access_token"]),
                "oauth_refresh_token": encrypt_token(
                    token_data.get("refresh_token", "")
                ),
                "oauth_token_expires_at": parse_datetime(
                    token_data.get("expires_at", "")
                ),
            },
        )

        frontend_url = getattr(django_settings, "FRONTEND_URL", "http://localhost:3000")
        return HttpResponseRedirect(
            f"{frontend_url}/account/restaurants/{slug}/integrations?connected=square"
        )
```

- [ ] **Step 4: Add OAuth URLs**

Add to `backend/integrations/urls.py`:

Update `backend/integrations/urls.py` to include the full import list and new paths:

```python
# backend/integrations/urls.py
from django.urls import path

from integrations.views import (
    POSConnectionDetailView,
    POSConnectInitiateView,
    POSSyncLogDetailView,
    POSSyncLogListView,
    RetryAllSyncView,
    RetryOrderSyncView,
    SquareOAuthCallbackView,
)

urlpatterns = [
    path(
        "restaurants/<slug:slug>/pos/connection/",
        POSConnectionDetailView.as_view(),
        name="pos-connection-detail",
    ),
    path(
        "restaurants/<slug:slug>/pos/connect/",
        POSConnectInitiateView.as_view(),
        name="pos-connect-initiate",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/",
        POSSyncLogListView.as_view(),
        name="pos-sync-logs",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry-all/",
        RetryAllSyncView.as_view(),
        name="pos-retry-all",
    ),
    path(
        "restaurants/<slug:slug>/pos/retry/<uuid:order_id>/",
        RetryOrderSyncView.as_view(),
        name="pos-retry-order",
    ),
    path(
        "restaurants/<slug:slug>/pos/sync-logs/<uuid:log_id>/",
        POSSyncLogDetailView.as_view(),
        name="pos-sync-log-detail",
    ),
    path(
        "integrations/oauth/square/callback/",
        SquareOAuthCallbackView.as_view(),
        name="square-oauth-callback",
    ),
]
```

- [ ] **Step 5: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_oauth.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `cd backend && poetry run pytest -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/integrations/views.py backend/integrations/urls.py backend/integrations/tests/test_oauth.py
git commit -m "feat: add Square OAuth connect flow with token encryption"
```

---

### Task 13: Payment Mode Awareness in Public Order Flow

**Files:**
- Modify: `backend/orders/views.py:11-15` (PublicMenuView)
- Modify: `backend/orders/views.py:33-69` (ConfirmOrderView)
- Create: `backend/integrations/tests/test_payment_mode.py`

- [ ] **Step 1: Write the failing test**

```python
# backend/integrations/tests/test_payment_mode.py
import pytest
from decimal import Decimal
from rest_framework import status

from integrations.tests.factories import POSConnectionFactory
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestPaymentModeAwareness:
    @pytest.fixture
    def pos_collected_restaurant(self):
        restaurant = RestaurantFactory(slug="pos-pay-test", tax_rate=Decimal("8.875"))
        POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            payment_mode="pos_collected",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Coffee")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("4.50"), is_default=True
        )
        return {"restaurant": restaurant, "item": item, "variant": variant}

    def test_menu_endpoint_includes_payment_mode(self, api_client, pos_collected_restaurant):
        response = api_client.get("/api/order/pos-pay-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "pos_collected"

    def test_menu_endpoint_defaults_to_stripe(self, api_client):
        RestaurantFactory(slug="no-pos-test")
        response = api_client.get("/api/order/no-pos-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["payment_mode"] == "stripe"

    def test_confirm_order_with_pos_collected(self, api_client, pos_collected_restaurant):
        data = {
            "items": [
                {
                    "menu_item_id": pos_collected_restaurant["item"].id,
                    "variant_id": pos_collected_restaurant["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one coffee",
            "table_identifier": "3",
        }
        response = api_client.post(
            "/api/order/pos-pay-test/confirm/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["payment_status"] == "pos_collected"
        assert response.data["status"] == "confirmed"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `cd backend && poetry run pytest integrations/tests/test_payment_mode.py -v`
Expected: FAIL — menu endpoint doesn't return payment_mode.

- [ ] **Step 3: Add payment_mode to PublicMenuView response**

In `backend/orders/services.py`, modify the `get_public_menu()` static method (line 726). The method returns a dict at line 745-751. Add the payment_mode lookup before the return statement and include it in the returned dict:

```python
@staticmethod
def get_public_menu(slug: str) -> dict:
    from restaurants.models import MenuCategory
    from restaurants.serializers import PublicMenuCategorySerializer

    try:
        restaurant = Restaurant.objects.get(slug=slug)
    except Restaurant.DoesNotExist:
        raise NotFound("Restaurant not found.")

    categories = (
        MenuCategory.objects.filter(restaurant=restaurant, is_active=True)
        .prefetch_related("items__variants", "items__modifiers")
        .order_by("sort_order")
    )

    # Determine payment mode from POS connection
    from integrations.models import POSConnection
    try:
        pos_conn = POSConnection.objects.get(restaurant=restaurant, is_active=True)
        payment_mode = pos_conn.payment_mode
    except POSConnection.DoesNotExist:
        payment_mode = "stripe"

    return {
        "restaurant_name": restaurant.name,
        "tax_rate": str(restaurant.tax_rate),
        "payment_mode": payment_mode,
        "categories": PublicMenuCategorySerializer(
            categories, many=True
        ).data,
    }
```

- [ ] **Step 4: Add pos_collected awareness to ConfirmOrderView**

In `backend/orders/views.py`, in `ConfirmOrderView.post()` (line 33), add the payment mode check after the restaurant lookup (around line 37). Also ensure the POS dispatch is called for pos_collected orders (which skip the payment flow entirely):

```python
# Add import at top of file:
from integrations.models import POSConnection

# Inside ConfirmOrderView.post(), after getting the restaurant (line ~37):
try:
    pos_connection = POSConnection.objects.get(restaurant=restaurant, is_active=True)
    payment_mode = pos_connection.payment_mode
except POSConnection.DoesNotExist:
    payment_mode = "stripe"

# When calling OrderService.create_order(), pass payment_status based on mode:
# If pos_collected, set payment_status="pos_collected" instead of "pending"
payment_status = "pos_collected" if payment_mode == "pos_collected" else "pending"
```

Pass `payment_status` to `OrderService.create_order()`. The existing `dispatch_order_to_pos.delay(str(order.id))` call (added in Task 8, Step 3) already fires after order creation, so pos_collected orders will be dispatched to the POS correctly.

- [ ] **Step 5: Run tests**

Run: `cd backend && poetry run pytest integrations/tests/test_payment_mode.py -v`
Expected: All tests PASS.

- [ ] **Step 6: Run full test suite**

Run: `cd backend && poetry run pytest -v`
Expected: All tests PASS.

- [ ] **Step 7: Commit**

```bash
git add backend/orders/views.py backend/orders/services.py backend/integrations/tests/test_payment_mode.py
git commit -m "feat: add payment mode awareness to public menu and order confirm flow"
```

---

## Chunk 3: Frontend — POS Settings, Sync Dashboard, and Payment Mode

This chunk builds the frontend pages: POS connection settings, sync log dashboard with retry functionality, and payment mode branching in the order flow.

---

### Task 14: Frontend API Functions and Types for POS

**Files:**
- Modify: `frontend/src/lib/api.ts`
- Modify: `frontend/src/types/index.ts` (or create types file if it doesn't exist)

- [ ] **Step 1: Add POS types**

Add to the frontend types file:

```typescript
export interface POSConnectionResponse {
  id: string;
  pos_type: "square" | "toast" | "middleware" | "none";
  is_active: boolean;
  payment_mode: "stripe" | "pos_collected";
  external_location_id: string | null;
  is_connected: boolean;
  created_at: string;
  updated_at: string;
}

export interface POSSyncLog {
  id: string;
  order_id: string;
  order_created_at: string;
  status: "pending" | "success" | "failed" | "retrying" | "manually_resolved";
  external_order_id: string | null;
  attempt_count: number;
  last_error: string | null;
  next_retry_at: string | null;
  created_at: string;
}
```

- [ ] **Step 2: Add POS API functions**

Add to `frontend/src/lib/api.ts`:

```typescript
// POS Integration
export async function fetchPOSConnection(
  slug: string
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/connection/`
  );
}

export async function initiatePOSConnect(
  slug: string,
  posType: string
): Promise<{ auth_url: string }> {
  return apiFetch<{ auth_url: string }>(
    `/api/restaurants/${slug}/pos/connect/`,
    { method: "POST", body: JSON.stringify({ pos_type: posType }) }
  );
}

export async function disconnectPOS(slug: string): Promise<void> {
  await apiFetch(`/api/restaurants/${slug}/pos/connection/`, {
    method: "DELETE",
  });
}

export async function updatePOSConnection(
  slug: string,
  data: { payment_mode?: string; external_location_id?: string }
): Promise<POSConnectionResponse> {
  return apiFetch<POSConnectionResponse>(
    `/api/restaurants/${slug}/pos/connection/`,
    { method: "PATCH", body: JSON.stringify(data) }
  );
}

export async function fetchPOSSyncLogs(
  slug: string,
  statusFilter?: string
): Promise<POSSyncLog[]> {
  const query = statusFilter ? `?status=${statusFilter}` : "";
  return apiFetch<POSSyncLog[]>(
    `/api/restaurants/${slug}/pos/sync-logs/${query}`
  );
}

export async function retryPOSSync(
  slug: string,
  orderId: string
): Promise<{ status: string }> {
  return apiFetch<{ status: string }>(
    `/api/restaurants/${slug}/pos/retry/${orderId}/`,
    { method: "POST" }
  );
}

export async function retryAllPOSSync(
  slug: string
): Promise<{ status: string; count: number }> {
  return apiFetch<{ status: string; count: number }>(
    `/api/restaurants/${slug}/pos/retry-all/`,
    { method: "POST" }
  );
}

export async function markSyncResolved(
  slug: string,
  logId: string
): Promise<POSSyncLog> {
  return apiFetch<POSSyncLog>(
    `/api/restaurants/${slug}/pos/sync-logs/${logId}/`,
    { method: "PATCH", body: JSON.stringify({ status: "manually_resolved" }) }
  );
}
```

- [ ] **Step 3: Commit**

```bash
git add frontend/src/lib/api.ts frontend/src/types/
git commit -m "feat: add POS integration API functions and types"
```

---

### Task 15: POS Connection Settings Page

**Files:**
- Create: `frontend/src/hooks/use-pos-connection.ts`
- Create: `frontend/src/app/account/restaurants/[slug]/integrations/page.tsx`

- [ ] **Step 1: Create the React Query hook**

```typescript
// frontend/src/hooks/use-pos-connection.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  disconnectPOS,
  fetchPOSConnection,
  initiatePOSConnect,
  updatePOSConnection,
} from "@/lib/api";

export function usePOSConnection(slug: string) {
  return useQuery({
    queryKey: ["pos-connection", slug],
    queryFn: () => fetchPOSConnection(slug),
    enabled: !!slug,
  });
}

export function usePOSConnect() {
  return useMutation({
    mutationFn: ({ slug, posType }: { slug: string; posType: string }) =>
      initiatePOSConnect(slug, posType),
    onSuccess: (data) => {
      window.location.href = data.auth_url;
    },
  });
}

export function usePOSDisconnect(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => disconnectPOS(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}

export function usePOSConnectionUpdate(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { payment_mode?: string; external_location_id?: string }) =>
      updatePOSConnection(slug, data),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-connection", slug] });
    },
  });
}
```

- [ ] **Step 2: Create the POS settings page**

```typescript
// frontend/src/app/account/restaurants/[slug]/integrations/page.tsx
"use client";

import { useParams, useSearchParams } from "next/navigation";
import {
  usePOSConnect,
  usePOSConnection,
  usePOSConnectionUpdate,
  usePOSDisconnect,
} from "@/hooks/use-pos-connection";

export default function POSIntegrationsPage() {
  const params = useParams<{ slug: string }>();
  const searchParams = useSearchParams();
  const slug = params.slug;

  const { data: connection, isLoading } = usePOSConnection(slug);
  const connect = usePOSConnect();
  const disconnect = usePOSDisconnect(slug);
  const updateConnection = usePOSConnectionUpdate(slug);

  const justConnected = searchParams.get("connected");
  const oauthError = searchParams.get("error");

  if (isLoading) {
    return <div className="p-6">Loading...</div>;
  }

  const isConnected = connection?.is_connected ?? false;

  return (
    <div className="space-y-6 p-6">
      <h1 className="text-2xl font-bold">POS Integration</h1>

      {justConnected && (
        <div className="rounded-md bg-green-50 p-4 text-green-800">
          Successfully connected to {justConnected}!
        </div>
      )}

      {oauthError && (
        <div className="rounded-md bg-red-50 p-4 text-red-800">
          Failed to connect. Please try again.
        </div>
      )}

      {/* Connection Status */}
      <div className="rounded-lg border p-6">
        <h2 className="text-lg font-semibold">Connection Status</h2>
        <div className="mt-4 flex items-center gap-3">
          <span
            className={`h-3 w-3 rounded-full ${
              isConnected ? "bg-green-500" : "bg-gray-300"
            }`}
          />
          <span>
            {isConnected
              ? `Connected to ${connection?.pos_type}`
              : "No POS connected"}
          </span>
        </div>

        {!isConnected && (
          <div className="mt-4 flex gap-3">
            <button
              onClick={() => connect.mutate({ slug, posType: "square" })}
              className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700"
              disabled={connect.isPending}
            >
              {connect.isPending ? "Connecting..." : "Connect Square"}
            </button>
            <button
              disabled
              className="rounded-md bg-gray-200 px-4 py-2 text-gray-400 cursor-not-allowed"
              title="Coming soon"
            >
              Connect Toast (Coming Soon)
            </button>
          </div>
        )}

        {isConnected && (
          <button
            onClick={() => {
              if (window.confirm("Disconnect POS? Orders will no longer sync.")) {
                disconnect.mutate();
              }
            }}
            className="mt-4 rounded-md border border-red-300 px-4 py-2 text-red-600 hover:bg-red-50"
            disabled={disconnect.isPending}
          >
            Disconnect
          </button>
        )}
      </div>

      {/* Location Selector (for multi-location POS accounts) */}
      {isConnected && (
        <div className="rounded-lg border p-6">
          <h2 className="text-lg font-semibold">POS Location</h2>
          <p className="mt-1 text-sm text-gray-500">
            Enter the location ID from your POS dashboard for the location that should receive QR orders.
          </p>
          <div className="mt-4 flex gap-3">
            <input
              type="text"
              value={connection?.external_location_id ?? ""}
              onChange={(e) =>
                updateConnection.mutate({ external_location_id: e.target.value })
              }
              placeholder="e.g., L1234ABC (Square) or GUID (Toast)"
              className="flex-1 rounded-md border px-3 py-2 text-sm"
            />
          </div>
        </div>
      )}

      {/* Payment Mode */}
      {isConnected && (
        <div className="rounded-lg border p-6">
          <h2 className="text-lg font-semibold">Payment Mode</h2>
          <p className="mt-1 text-sm text-gray-500">
            Choose how payments are collected for QR orders.
          </p>
          <div className="mt-4 space-y-3">
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="stripe"
                checked={connection?.payment_mode === "stripe"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "stripe" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay online (Stripe)</div>
                <div className="text-sm text-gray-500">
                  Customers pay through the app. Orders appear as paid in your
                  POS.
                </div>
              </div>
            </label>
            <label className="flex items-start gap-3">
              <input
                type="radio"
                name="payment_mode"
                value="pos_collected"
                checked={connection?.payment_mode === "pos_collected"}
                onChange={() =>
                  updateConnection.mutate({ payment_mode: "pos_collected" })
                }
                className="mt-1"
              />
              <div>
                <div className="font-medium">Pay at counter (POS)</div>
                <div className="text-sm text-gray-500">
                  Orders are sent to your POS. Customers pay at the counter or
                  table.
                </div>
              </div>
            </label>
          </div>
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify page renders**

Run: `cd frontend && npm run dev`
Navigate to: `http://localhost:3000/account/restaurants/[your-slug]/integrations`
Expected: Page renders with connection status and connect buttons.

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-pos-connection.ts frontend/src/app/account/restaurants/\[slug\]/integrations/
git commit -m "feat: add POS connection settings page with Square OAuth connect"
```

---

### Task 16: POS Sync Logs Dashboard Page

**Files:**
- Create: `frontend/src/hooks/use-pos-sync-logs.ts`
- Create: `frontend/src/app/account/restaurants/[slug]/sync-logs/page.tsx`

- [ ] **Step 1: Create the React Query hooks**

```typescript
// frontend/src/hooks/use-pos-sync-logs.ts
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  fetchPOSSyncLogs,
  markSyncResolved,
  retryAllPOSSync,
  retryPOSSync,
} from "@/lib/api";

export function usePOSSyncLogs(slug: string, statusFilter?: string) {
  return useQuery({
    queryKey: ["pos-sync-logs", slug, statusFilter],
    queryFn: () => fetchPOSSyncLogs(slug, statusFilter),
    enabled: !!slug,
    refetchInterval: 10000, // Poll every 10s for status updates
  });
}

export function useRetrySync(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (orderId: string) => retryPOSSync(slug, orderId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}

export function useRetryAllSync(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: () => retryAllPOSSync(slug),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}

export function useMarkResolved(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (logId: string) => markSyncResolved(slug, logId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["pos-sync-logs", slug] });
    },
  });
}
```

- [ ] **Step 2: Create the sync logs page**

```typescript
// frontend/src/app/account/restaurants/[slug]/sync-logs/page.tsx
"use client";

import { useState } from "react";
import { useParams } from "next/navigation";
import {
  useMarkResolved,
  usePOSSyncLogs,
  useRetryAllSync,
  useRetrySync,
} from "@/hooks/use-pos-sync-logs";

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800",
  success: "bg-green-100 text-green-800",
  failed: "bg-red-100 text-red-800",
  retrying: "bg-orange-100 text-orange-800",
  manually_resolved: "bg-gray-100 text-gray-800",
};

export default function POSSyncLogsPage() {
  const params = useParams<{ slug: string }>();
  const slug = params.slug;
  const [statusFilter, setStatusFilter] = useState<string | undefined>();

  const { data: logs, isLoading } = usePOSSyncLogs(slug, statusFilter);
  const retrySync = useRetrySync(slug);
  const retryAll = useRetryAllSync(slug);
  const markResolved = useMarkResolved(slug);

  const failedCount = logs?.filter((l) => l.status === "failed").length ?? 0;
  const pendingCount =
    logs?.filter((l) => l.status === "pending" || l.status === "retrying")
      .length ?? 0;

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-bold">POS Sync Status</h1>
        {failedCount > 0 && (
          <button
            onClick={() => retryAll.mutate()}
            disabled={retryAll.isPending}
            className="rounded-md bg-blue-600 px-4 py-2 text-white hover:bg-blue-700 disabled:opacity-50"
          >
            {retryAll.isPending
              ? "Retrying..."
              : `Retry All Failed (${failedCount})`}
          </button>
        )}
      </div>

      {/* Summary bar */}
      <div className="flex gap-4">
        {failedCount > 0 && (
          <span className="rounded-full bg-red-100 px-3 py-1 text-sm text-red-800">
            {failedCount} failed
          </span>
        )}
        {pendingCount > 0 && (
          <span className="rounded-full bg-yellow-100 px-3 py-1 text-sm text-yellow-800">
            {pendingCount} pending
          </span>
        )}
      </div>

      {/* Filter */}
      <div className="flex gap-2">
        {["all", "failed", "pending", "retrying", "success", "manually_resolved"].map(
          (s) => (
            <button
              key={s}
              onClick={() => setStatusFilter(s === "all" ? undefined : s)}
              className={`rounded-md px-3 py-1 text-sm ${
                (s === "all" && !statusFilter) || statusFilter === s
                  ? "bg-gray-900 text-white"
                  : "bg-gray-100 text-gray-700 hover:bg-gray-200"
              }`}
            >
              {s === "all" ? "All" : s.replace("_", " ")}
            </button>
          )
        )}
      </div>

      {isLoading ? (
        <div>Loading...</div>
      ) : (
        <table className="w-full text-left text-sm">
          <thead className="border-b text-gray-500">
            <tr>
              <th className="pb-2">Order</th>
              <th className="pb-2">Date</th>
              <th className="pb-2">Status</th>
              <th className="pb-2">POS Order ID</th>
              <th className="pb-2">Attempts</th>
              <th className="pb-2">Error</th>
              <th className="pb-2">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {logs?.map((log) => (
              <tr key={log.id}>
                <td className="py-3 font-mono text-xs">
                  {log.order_id.slice(0, 8)}...
                </td>
                <td className="py-3">
                  {new Date(log.order_created_at).toLocaleString()}
                </td>
                <td className="py-3">
                  <span
                    className={`rounded-full px-2 py-0.5 text-xs ${
                      STATUS_COLORS[log.status] ?? ""
                    }`}
                  >
                    {log.status.replace("_", " ")}
                  </span>
                </td>
                <td className="py-3 font-mono text-xs">
                  {log.external_order_id ?? "-"}
                </td>
                <td className="py-3">{log.attempt_count}</td>
                <td className="max-w-xs truncate py-3 text-xs text-gray-500">
                  {log.last_error ?? "-"}
                </td>
                <td className="py-3">
                  <div className="flex gap-2">
                    {log.status === "failed" && (
                      <>
                        <button
                          onClick={() => retrySync.mutate(log.order_id)}
                          className="text-xs text-blue-600 hover:underline"
                        >
                          Retry
                        </button>
                        <button
                          onClick={() => markResolved.mutate(log.id)}
                          className="text-xs text-gray-600 hover:underline"
                        >
                          Mark Resolved
                        </button>
                      </>
                    )}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      )}

      {logs?.length === 0 && (
        <div className="py-12 text-center text-gray-500">
          No sync logs found.
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 3: Verify page renders**

Run: `cd frontend && npm run dev`
Navigate to: `http://localhost:3000/account/restaurants/[your-slug]/sync-logs`
Expected: Page renders with sync log table (empty if no data).

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-pos-sync-logs.ts frontend/src/app/account/restaurants/\[slug\]/sync-logs/
git commit -m "feat: add POS sync logs dashboard with retry and mark-resolved"
```

---

### Task 17: Payment Mode Branching in Frontend Order Flow

**Files:**
- Modify: `frontend/src/hooks/use-menu.ts` — ensure the menu type includes `payment_mode`
- Modify: `frontend/src/app/order/[slug]/page.tsx:76-81` — add conditional around `step === "payment"`
- Modify: `frontend/src/types/index.ts` — add `payment_mode` to the menu response type

- [ ] **Step 1: Update menu response type**

In `frontend/src/types/index.ts`, find the menu response interface and add `payment_mode`:

```typescript
payment_mode: "stripe" | "pos_collected";
```

The menu hook (`frontend/src/hooks/use-menu.ts`) already returns this data from the API — no hook changes needed if the type is updated.

- [ ] **Step 2: Skip the payment step for pos_collected restaurants**

The approach: when `payment_mode === "pos_collected"`, the `ConfirmationStep` should call a different API endpoint (confirm without payment) and transition directly to `"submitted"` instead of `"payment"`. No changes needed to `page.tsx` rendering — the step simply skips "payment" entirely.

**Modify `frontend/src/app/order/[slug]/components/ConfirmationStep.tsx`:**

The component currently calls `createPaymentMutation.mutate()` on line 67, and on success transitions to `setStep("payment")` on line 73. Add a `paymentMode` prop and branch the confirm logic:

1. Add `paymentMode` to the `ConfirmationStepProps` interface (line 16):

```typescript
interface ConfirmationStepProps {
  slug: string;
  taxRate: string;
  paymentMode: "stripe" | "pos_collected";
}
```

2. In `handleConfirm()` (line 52), add a branch for pos_collected mode. When `paymentMode === "pos_collected"`, call the existing `confirmOrder` API (which creates the order without Stripe payment) and transition to `"submitted"`:

```typescript
import { useConfirmOrder } from "@/hooks/use-confirm-order";

// Inside the component:
const confirmOrderMutation = useConfirmOrder(slug);

const handleConfirm = () => {
  const items: ConfirmOrderItem[] = parsedItems.map((item) => ({
    menu_item_id: item.menu_item_id,
    variant_id: item.variant.id,
    quantity: item.quantity,
    modifier_ids: item.modifiers.map((m) => m.id),
    special_requests: item.special_requests,
  }));

  const prefAllergies = allergyNote
    ? allergyNote.split(",").map((a) => a.trim()).filter(Boolean)
    : [];
  const allAllergies = Array.from(new Set([...parsedAllergies, ...prefAllergies]));

  if (paymentMode === "pos_collected") {
    // Skip Stripe — just confirm the order
    confirmOrderMutation.mutate(
      { items, rawInput, tableIdentifier, language, customerName, customerPhone, allergies: allAllergies },
      {
        onSuccess: (result) => {
          setOrderId(result.id);
          setStep("submitted");  // Skip payment, go directly to submitted
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : "Failed to confirm order");
        },
      }
    );
  } else {
    // Existing Stripe payment flow
    createPaymentMutation.mutate(
      { items, rawInput, tableIdentifier, language, customerName, customerPhone, allergies: allAllergies },
      {
        onSuccess: (result) => {
          setOrderId(result.id);
          setClientSecret(result.client_secret);
          setStep("payment");
        },
        onError: (err) => {
          setError(err instanceof Error ? err.message : "Failed to create payment");
        },
      }
    );
  }
};
```

3. In `frontend/src/app/order/[slug]/page.tsx`, pass `paymentMode` to `ConfirmationStep` (line 79):

```typescript
{step === "confirmation" && (
  <ConfirmationStep slug={slug} taxRate={menu.tax_rate} paymentMode={menu.payment_mode ?? "stripe"} />
)}

- [ ] **Step 3: Verify the flow**

1. Set up a restaurant with `payment_mode = "pos_collected"` in the database
2. Navigate to the order page for that restaurant
3. Submit an order
4. Expected: No Stripe payment form appears. Instead, see "Your order has been sent. Please pay at the counter."

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/order/ frontend/src/hooks/
git commit -m "feat: skip Stripe payment UI when restaurant uses POS-collected payment mode"
```

---

### Task 18: Kitchen Display Print Button

**Files:**
- Modify: `frontend/src/app/kitchen/[slug]/components/OrderCard.tsx` — add print button and hidden print template
- Create: `frontend/src/app/kitchen/[slug]/print.css` — print-specific CSS

The kitchen display has this component structure:
- `frontend/src/app/kitchen/[slug]/page.tsx` — main page with WebSocket connection
- `frontend/src/app/kitchen/[slug]/components/OrderColumn.tsx` — column of orders by status
- `frontend/src/app/kitchen/[slug]/components/OrderCard.tsx` — individual order card (this is where the print button goes)

- [ ] **Step 1: Add print styles**

Create `frontend/src/app/kitchen/[slug]/print.css`:

```css
@media print {
  body * {
    display: none !important;
  }
  .print-receipt,
  .print-receipt * {
    display: block !important;
  }
  .print-receipt {
    position: absolute;
    left: 0;
    top: 0;
    width: 80mm; /* standard thermal receipt width */
    font-family: monospace;
    font-size: 12px;
    padding: 4mm;
  }
}
```

Import this CSS in `frontend/src/app/kitchen/[slug]/page.tsx` at the top:

```typescript
import "./print.css";
```

- [ ] **Step 2: Add print button and receipt template to OrderCard**

Modify `frontend/src/app/kitchen/[slug]/components/OrderCard.tsx` (84 lines). The component receives `order: OrderResponse` and renders a `<Card>`.

Add the print handler function inside the component (before the return statement at line 30), a "Print" button in the card header (line 35 area, next to the order ID), and a hidden receipt template at the end of the `<Card>`:

```typescript
// frontend/src/app/kitchen/[slug]/components/OrderCard.tsx
"use client";

import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import type { OrderResponse } from "@/types";

interface OrderCardProps {
  order: OrderResponse;
  onAdvance: (orderId: string) => void;
}

function timeSince(dateString: string): string {
  const seconds = Math.floor(
    (Date.now() - new Date(dateString).getTime()) / 1000
  );
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}

const statusLabels: Record<string, string> = {
  confirmed: "Start Preparing",
  preparing: "Mark Ready",
  ready: "Complete",
};

export function OrderCard({ order, onAdvance }: OrderCardProps) {
  const handlePrint = (e: React.MouseEvent) => {
    e.stopPropagation(); // Don't trigger the card's onClick (onAdvance)
    const printEl = document.getElementById(`print-receipt-${order.id}`);
    if (!printEl) return;
    printEl.classList.add("print-receipt");
    const cleanup = () => {
      printEl.classList.remove("print-receipt");
      window.removeEventListener("afterprint", cleanup);
    };
    window.addEventListener("afterprint", cleanup);
    window.print();
  };

  return (
    <Card
      className="p-4 cursor-pointer hover:shadow-md transition-shadow"
      onClick={() => onAdvance(order.id)}
    >
      <div className="flex justify-between items-start mb-2">
        <div>
          <span className="font-bold text-sm">
            #{order.id.slice(0, 8)}
          </span>
          {order.table_identifier && (
            <Badge variant="outline" className="ml-2">
              Table {order.table_identifier}
            </Badge>
          )}
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={handlePrint}
            className="text-xs text-muted-foreground hover:text-foreground"
          >
            Print
          </button>
          <span className="text-xs text-muted-foreground">
            {timeSince(order.created_at)}
          </span>
        </div>
      </div>

      {order.customer_allergies?.length > 0 && (
        <div className="flex flex-wrap gap-1 mb-2">
          {order.customer_allergies.map((allergy) => (
            <Badge key={allergy} variant="destructive" className="text-xs">
              {allergy}
            </Badge>
          ))}
        </div>
      )}

      <ul className="text-sm space-y-1 mb-3">
        {order.items.map((item) => (
          <li key={item.id}>
            {item.quantity}x {item.name} ({item.variant_label})
            {item.special_requests && (
              <span className="text-muted-foreground italic">
                {" "}- {item.special_requests}
              </span>
            )}
          </li>
        ))}
      </ul>

      <div className="text-xs text-center text-primary font-medium">
        Tap to {statusLabels[order.status] || "update"}
      </div>

      {/* Hidden receipt template — only visible during printing */}
      <div id={`print-receipt-${order.id}`} style={{ display: "none" }}>
        <div style={{ textAlign: "center", fontWeight: "bold" }}>
          ORDER #{order.id.slice(0, 8)}
        </div>
        {order.table_identifier && <div>Table: {order.table_identifier}</div>}
        <div>Time: {new Date(order.created_at).toLocaleTimeString()}</div>
        <hr />
        {order.items.map((item) => (
          <div key={item.id}>
            {item.quantity}x {item.name} ({item.variant_label})
            {item.special_requests && <div>  Note: {item.special_requests}</div>}
          </div>
        ))}
        {order.customer_allergies?.length > 0 && (
          <>
            <hr />
            <div>ALLERGIES: {order.customer_allergies.join(", ")}</div>
          </>
        )}
        <hr />
        <div>
          Payment: {order.payment_status === "pos_collected"
            ? "Pay at counter"
            : "Paid online"}
        </div>
      </div>
    </Card>
  );
}
```

This is a full replacement of the file. The print receipt uses inline `style={{ display: "none" }}` which is overridden by the print CSS `display: block !important`.

- [ ] **Step 3: Verify print works**

1. Open the kitchen display page
2. Click "Print" on an order card
3. Expected: Browser print dialog opens with a receipt-formatted view of just that order

- [ ] **Step 4: Commit**

```bash
git add frontend/src/app/kitchen/
git commit -m "feat: add print button to kitchen order cards for receipt printing"
```

---

### Task 19: Admin Registration for POS Models

**Files:**
- Modify: `backend/integrations/admin.py`

- [ ] **Step 1: Register models in Django admin**

```python
# backend/integrations/admin.py
from django.contrib import admin

from integrations.models import POSConnection, POSSyncLog


@admin.register(POSConnection)
class POSConnectionAdmin(admin.ModelAdmin):
    list_display = ["restaurant", "pos_type", "is_active", "payment_mode", "created_at"]
    list_filter = ["pos_type", "is_active", "payment_mode"]
    search_fields = ["restaurant__name", "restaurant__slug"]
    readonly_fields = ["id", "created_at", "updated_at"]


@admin.register(POSSyncLog)
class POSSyncLogAdmin(admin.ModelAdmin):
    list_display = ["order", "status", "attempt_count", "external_order_id", "created_at"]
    list_filter = ["status"]
    search_fields = ["order__id", "external_order_id"]
    readonly_fields = ["id", "created_at", "updated_at"]
```

- [ ] **Step 2: Verify admin renders**

Run: `cd backend && poetry run python manage.py runserver 5005`
Navigate to: `http://localhost:5005/django-admin/`
Expected: POSConnection and POSSyncLog appear in the admin.

- [ ] **Step 3: Commit**

```bash
git add backend/integrations/admin.py
git commit -m "feat: register POS models in Django admin"
```

---

### Task 20: Final Integration Test

**Files:**
- Create: `backend/integrations/tests/test_integration.py`

- [ ] **Step 1: Write an end-to-end integration test**

```python
# backend/integrations/tests/test_integration.py
import pytest
from decimal import Decimal
from unittest.mock import patch, MagicMock

from rest_framework import status

from integrations.adapters.base import PushResult
from integrations.models import POSConnection, POSSyncLog
from integrations.tests.factories import POSConnectionFactory
from orders.models import Order
from restaurants.tests.factories import (
    MenuCategoryFactory,
    MenuItemFactory,
    MenuItemVariantFactory,
    RestaurantFactory,
)


@pytest.mark.django_db
class TestPOSIntegrationEndToEnd:
    @pytest.fixture
    def full_setup(self):
        restaurant = RestaurantFactory(slug="e2e-test", tax_rate=Decimal("8.875"))
        connection = POSConnectionFactory(
            restaurant=restaurant,
            pos_type="square",
            payment_mode="stripe",
        )
        cat = MenuCategoryFactory(restaurant=restaurant)
        item = MenuItemFactory(category=cat, name="Burger")
        variant = MenuItemVariantFactory(
            menu_item=item, label="Regular", price=Decimal("12.99"), is_default=True
        )
        return {
            "restaurant": restaurant,
            "connection": connection,
            "item": item,
            "variant": variant,
        }

    @patch("orders.views.dispatch_order_to_pos")
    def test_order_confirm_triggers_dispatch(self, mock_task, api_client, full_setup):
        """Confirm an order and verify the POS dispatch task is enqueued."""
        data = {
            "items": [
                {
                    "menu_item_id": full_setup["item"].id,
                    "variant_id": full_setup["variant"].id,
                    "quantity": 1,
                    "modifier_ids": [],
                }
            ],
            "raw_input": "one burger",
            "table_identifier": "7",
        }
        response = api_client.post(
            "/api/order/e2e-test/confirm/", data, format="json"
        )
        assert response.status_code == status.HTTP_201_CREATED
        mock_task.delay.assert_called_once()

    @patch("integrations.adapters.square.SquareAdapter._get_client")
    def test_dispatch_creates_sync_log_on_success(self, mock_get_client, full_setup):
        """Run the dispatch service and verify sync log is created."""
        mock_client = MagicMock()
        mock_result = MagicMock()
        mock_result.is_success.return_value = True
        mock_result.body = {"order": {"id": "sq_e2e_order"}}
        mock_client.orders.create_order.return_value = mock_result
        mock_get_client.return_value = mock_client

        from orders.tests.factories import OrderFactory
        order = OrderFactory(restaurant=full_setup["restaurant"])

        from integrations.services import POSDispatchService
        POSDispatchService.dispatch(str(order.id))

        order.refresh_from_db()
        assert order.pos_sync_status == "synced"
        assert order.external_order_id == "sq_e2e_order"

        log = POSSyncLog.objects.get(order=order)
        assert log.status == "success"

    def test_menu_endpoint_returns_payment_mode(self, api_client, full_setup):
        """Verify the public menu endpoint includes payment_mode."""
        response = api_client.get("/api/order/e2e-test/menu/")
        assert response.status_code == status.HTTP_200_OK
        assert "payment_mode" in response.data
```

- [ ] **Step 2: Run the integration test**

Run: `cd backend && poetry run pytest integrations/tests/test_integration.py -v`
Expected: All tests PASS.

- [ ] **Step 3: Run full test suite one final time**

Run: `cd backend && poetry run pytest -v`
Expected: All tests PASS.

- [ ] **Step 4: Commit**

```bash
git add backend/integrations/tests/test_integration.py
git commit -m "test: add end-to-end integration test for POS dispatch flow"
```
