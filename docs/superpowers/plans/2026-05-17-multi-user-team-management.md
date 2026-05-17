# Multi-User Team Management Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add role-based multi-user support with email invitation flow to restaurants.

**Architecture:** Django backend with new `Invitation` model, `TeamService` service layer, DRF permission classes (`IsRestaurantAdmin`, `HasPermission`), and Celery async email. Next.js frontend with team management page, invite acceptance page, and role-aware navigation gating via `useMyRole` hook.

**Tech Stack:** Django 5 / DRF / Celery / PostgreSQL (backend), Next.js 14 / React / Zustand / TanStack Query / shadcn/ui (frontend)

**Spec:** `docs/superpowers/specs/2026-05-17-multi-user-team-management-design.md`

---

## Chunk 1: Data Model & Migrations

### Task 1: Update RestaurantStaff model — rename roles and add permissions field

**Files:**
- Modify: `backend/restaurants/models.py:96-111`
- Modify: `backend/restaurants/tests/factories.py:36-42` (RestaurantStaffFactory)
- Test: `backend/restaurants/tests/test_team_models.py` (create)

- [ ] **Step 1: Write tests for updated RestaurantStaff model**

Create `backend/restaurants/tests/test_team_models.py`:

```python
import pytest

from restaurants.models import RestaurantStaff
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


@pytest.mark.django_db
class TestRestaurantStaffRoles:
    def test_role_choices(self):
        assert RestaurantStaff.StaffRole.OWNER == "owner"
        assert RestaurantStaff.StaffRole.ADMIN == "admin"
        assert RestaurantStaff.StaffRole.MEMBER == "member"

    def test_default_permissions_is_empty_dict(self):
        staff = RestaurantStaffFactory(role="member")
        assert staff.permissions == {}

    def test_permissions_stores_overrides(self):
        staff = RestaurantStaffFactory(role="member", permissions={"menu_edit": True})
        staff.refresh_from_db()
        assert staff.permissions == {"menu_edit": True}
```

- [ ] **Step 2: Run tests — expect failure (StaffRole.ADMIN and permissions don't exist yet)**

Run: `cd backend && python -m pytest restaurants/tests/test_team_models.py -v`

- [ ] **Step 3: Update RestaurantStaff model**

In `backend/restaurants/models.py`, replace the `RestaurantStaff` class (lines 96-111):

```python
class RestaurantStaff(models.Model):
    class StaffRole(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="staff_roles")
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="staff")
    role = models.CharField(max_length=10, choices=StaffRole.choices)
    permissions = models.JSONField(default=dict, blank=True)
    invited_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "restaurant")

    def __str__(self):
        return f"{self.user.email} @ {self.restaurant.name} ({self.role})"
```

- [ ] **Step 4: Update RestaurantStaffFactory default role**

In `backend/restaurants/tests/factories.py`, change `role = "manager"` to `role = "member"` in `RestaurantStaffFactory`.

- [ ] **Step 5: Generate and run migration**

Run: `cd backend && python manage.py makemigrations restaurants && python manage.py migrate`

- [ ] **Step 6: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_models.py -v`

- [ ] **Step 7: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/tests/test_team_models.py backend/restaurants/tests/factories.py backend/restaurants/migrations/
git commit -m "feat: update RestaurantStaff roles to owner/admin/member and add permissions JSON field"
```

### Task 2: Data migration for existing role values

**Files:**
- Create: a new data migration in `backend/restaurants/migrations/`

- [ ] **Step 1: Create data migration**

Run: `cd backend && python manage.py makemigrations restaurants --empty -n rename_staff_roles`

Edit the generated migration — keep the auto-generated `dependencies` list unchanged, and replace the empty `operations` list with:

```python
from django.db import migrations


def rename_roles(apps, schema_editor):
    RestaurantStaff = apps.get_model("restaurants", "RestaurantStaff")
    RestaurantStaff.objects.filter(role="manager").update(role="admin")
    RestaurantStaff.objects.filter(role="kitchen").update(role="member")


def reverse_rename(apps, schema_editor):
    RestaurantStaff = apps.get_model("restaurants", "RestaurantStaff")
    RestaurantStaff.objects.filter(role="admin").update(role="manager")
    RestaurantStaff.objects.filter(role="member").update(role="kitchen")


# In the Migration class, replace `operations = []` with:
    operations = [
        migrations.RunPython(rename_roles, reverse_rename),
    ]
```

- [ ] **Step 2: Run migration**

Run: `cd backend && python manage.py migrate`

- [ ] **Step 3: Commit**

```bash
git add backend/restaurants/migrations/
git commit -m "feat: data migration to rename staff roles manager->admin, kitchen->member"
```

### Task 3: Add Invitation model

**Files:**
- Modify: `backend/restaurants/models.py` (add Invitation class after RestaurantStaff)
- Test: `backend/restaurants/tests/test_team_models.py` (add Invitation tests)

- [ ] **Step 1: Write tests for Invitation model**

Append to `backend/restaurants/tests/test_team_models.py`:

```python
from datetime import timedelta
from django.utils import timezone
from restaurants.models import Invitation


@pytest.mark.django_db
class TestInvitationModel:
    def test_create_invitation(self):
        restaurant = RestaurantFactory()
        user = restaurant.owner
        invitation = Invitation.objects.create(
            restaurant=restaurant,
            email="new@example.com",
            role="member",
            invited_by=user,
        )
        assert invitation.token  # auto-generated
        assert len(invitation.token) > 20
        assert invitation.status == "pending"
        assert invitation.expires_at > timezone.now()

    def test_duplicate_pending_invite_blocked(self):
        restaurant = RestaurantFactory()
        Invitation.objects.create(
            restaurant=restaurant,
            email="dup@example.com",
            role="member",
            invited_by=restaurant.owner,
        )
        from django.db import IntegrityError
        with pytest.raises(IntegrityError):
            Invitation.objects.create(
                restaurant=restaurant,
                email="dup@example.com",
                role="admin",
                invited_by=restaurant.owner,
            )

    def test_accepted_invite_allows_new_pending(self):
        restaurant = RestaurantFactory()
        inv = Invitation.objects.create(
            restaurant=restaurant,
            email="reuse@example.com",
            role="member",
            invited_by=restaurant.owner,
        )
        inv.status = "accepted"
        inv.save()
        # Should not raise — old one is accepted, not pending
        new_inv = Invitation.objects.create(
            restaurant=restaurant,
            email="reuse@example.com",
            role="admin",
            invited_by=restaurant.owner,
        )
        assert new_inv.status == "pending"
```

- [ ] **Step 2: Run tests — expect failure (Invitation model doesn't exist yet)**

Run: `cd backend && python -m pytest restaurants/tests/test_team_models.py::TestInvitationModel -v`

- [ ] **Step 3: Add Invitation model to models.py**

Add after `RestaurantStaff` in `backend/restaurants/models.py`:

```python
class Invitation(models.Model):
    class InviteStatus(models.TextChoices):
        PENDING = "pending", "Pending"
        ACCEPTED = "accepted", "Accepted"
        EXPIRED = "expired", "Expired"
        REVOKED = "revoked", "Revoked"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    restaurant = models.ForeignKey(Restaurant, on_delete=models.CASCADE, related_name="invitations")
    email = models.EmailField()
    role = models.CharField(max_length=10, choices=[("admin", "Admin"), ("member", "Member")])
    permissions = models.JSONField(default=dict, blank=True)
    token = models.CharField(max_length=64, unique=True, editable=False)
    invited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="sent_invitations"
    )
    status = models.CharField(
        max_length=10, choices=InviteStatus.choices, default=InviteStatus.PENDING
    )
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["restaurant", "email"],
                condition=models.Q(status="pending"),
                name="unique_pending_invitation",
            )
        ]

    def save(self, *args, **kwargs):
        if not self.token:
            self.token = secrets.token_urlsafe(32)
        if not self.expires_at:
            from datetime import timedelta
            self.expires_at = timezone.now() + timedelta(days=7)
        super().save(*args, **kwargs)

    @property
    def is_expired(self):
        return self.status == "pending" and timezone.now() > self.expires_at

    def __str__(self):
        return f"Invite {self.email} to {self.restaurant.name} ({self.status})"
```

Add these imports to the top of `models.py` (alongside existing imports — they are not currently present):
```python
import secrets
from django.utils import timezone
```

- [ ] **Step 4: Generate and run migration**

Run: `cd backend && python manage.py makemigrations restaurants && python manage.py migrate`

- [ ] **Step 5: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_models.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/models.py backend/restaurants/tests/test_team_models.py backend/restaurants/migrations/
git commit -m "feat: add Invitation model with conditional unique constraint"
```

---

## Chunk 2: Permission Classes & Service Layer

### Task 4: Create new DRF permission classes

**Files:**
- Modify: `backend/restaurants/permissions.py`
- Test: `backend/restaurants/tests/test_team_permissions.py` (create)

- [ ] **Step 1: Write tests for permission classes**

Create `backend/restaurants/tests/test_team_permissions.py`:

```python
import pytest
from unittest.mock import MagicMock

from restaurants.models import RestaurantStaff
from restaurants.permissions import IsRestaurantAdmin, HasPermission
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


def _make_request(user):
    request = MagicMock()
    request.user = user
    request.method = "POST"
    return request


def _make_view(slug):
    view = MagicMock()
    view.kwargs = {"slug": slug}
    return view


@pytest.mark.django_db
class TestIsRestaurantAdmin:
    def test_owner_allowed(self):
        restaurant = RestaurantFactory()
        request = _make_request(restaurant.owner)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is True

    def test_admin_allowed(self):
        restaurant = RestaurantFactory()
        admin_user = UserFactory()
        RestaurantStaffFactory(user=admin_user, restaurant=restaurant, role="admin")
        request = _make_request(admin_user)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is True

    def test_member_denied(self):
        restaurant = RestaurantFactory()
        member_user = UserFactory()
        RestaurantStaffFactory(user=member_user, restaurant=restaurant, role="member")
        request = _make_request(member_user)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is False

    def test_stranger_denied(self):
        restaurant = RestaurantFactory()
        stranger = UserFactory()
        request = _make_request(stranger)
        view = _make_view(restaurant.slug)
        assert IsRestaurantAdmin().has_permission(request, view) is False


@pytest.mark.django_db
class TestHasPermission:
    def test_owner_auto_passes(self):
        restaurant = RestaurantFactory()
        request = _make_request(restaurant.owner)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_admin_auto_passes(self):
        restaurant = RestaurantFactory()
        admin_user = UserFactory()
        RestaurantStaffFactory(user=admin_user, restaurant=restaurant, role="admin")
        request = _make_request(admin_user)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_member_with_permission_allowed(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        request = _make_request(member)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is True

    def test_member_without_permission_denied(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        request = _make_request(member)
        view = _make_view(restaurant.slug)
        assert HasPermission("menu_edit").has_permission(request, view) is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `cd backend && python -m pytest restaurants/tests/test_team_permissions.py -v`

- [ ] **Step 3: Implement permission classes**

Add to `backend/restaurants/permissions.py`:

```python
class IsRestaurantAdmin(BasePermission):
    """Allow access only to restaurant Owner or Admin."""
    message = "You need admin access to perform this action."

    def has_permission(self, request, view):
        slug = view.kwargs.get("slug")
        if slug is None:
            return False
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return False
        if restaurant.owner == request.user:
            return True
        return RestaurantStaff.objects.filter(
            user=request.user, restaurant=restaurant, role="admin"
        ).exists()


class HasPermission(BasePermission):
    """Check a specific permission key. Owner/Admin auto-pass."""

    def __init__(self, permission_key):
        self.permission_key = permission_key

    def has_permission(self, request, view):
        slug = view.kwargs.get("slug")
        if slug is None:
            return False
        try:
            restaurant = Restaurant.objects.get(slug=slug)
        except Restaurant.DoesNotExist:
            return False
        if restaurant.owner == request.user:
            return True
        try:
            staff = RestaurantStaff.objects.get(user=request.user, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            return False
        if staff.role == "admin":
            return True
        return staff.permissions.get(self.permission_key, False)
```

- [ ] **Step 4: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_permissions.py -v`

- [ ] **Step 5: Commit**

```bash
git add backend/restaurants/permissions.py backend/restaurants/tests/test_team_permissions.py
git commit -m "feat: add IsRestaurantAdmin and HasPermission DRF permission classes"
```

### Task 5: Create TeamService

**Files:**
- Create: `backend/restaurants/services/team_service.py`
- Modify: `backend/restaurants/services/__init__.py`
- Test: `backend/restaurants/tests/test_team_service.py` (create)

- [ ] **Step 1: Write tests for TeamService**

Create `backend/restaurants/tests/test_team_service.py`:

```python
import pytest
from django.contrib.auth import get_user_model
from rest_framework.exceptions import ValidationError

from restaurants.models import Invitation, RestaurantStaff
from restaurants.services.team_service import TeamService
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory

User = get_user_model()


@pytest.mark.django_db
class TestInviteMember:
    def test_creates_invitation(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="new@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        assert invitation.status == "pending"
        assert invitation.email == "new@example.com"
        assert invitation.role == "member"
        assert len(invitation.token) > 20

    def test_rejects_existing_staff(self):
        restaurant = RestaurantFactory()
        staff_user = UserFactory(email="exists@example.com")
        RestaurantStaffFactory(user=staff_user, restaurant=restaurant, role="member")
        with pytest.raises(ValidationError, match="already on your team"):
            TeamService.invite_member(
                restaurant=restaurant,
                email="exists@example.com",
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )

    def test_rejects_owner_email(self):
        restaurant = RestaurantFactory()
        with pytest.raises(ValidationError, match="owner"):
            TeamService.invite_member(
                restaurant=restaurant,
                email=restaurant.owner.email,
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )

    def test_rejects_duplicate_pending(self):
        restaurant = RestaurantFactory()
        TeamService.invite_member(
            restaurant=restaurant,
            email="dup@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        with pytest.raises(ValidationError, match="already pending"):
            TeamService.invite_member(
                restaurant=restaurant,
                email="dup@example.com",
                role="admin",
                permissions={},
                invited_by=restaurant.owner,
            )


@pytest.mark.django_db
class TestAcceptInvitation:
    def test_existing_user_accepts(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="joiner@example.com",
            role="member",
            permissions={"menu_edit": True},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="joiner@example.com")
        staff = TeamService.accept_invitation(invitation.token, user=user)
        assert staff.user == user
        assert staff.role == "member"
        assert staff.permissions == {"menu_edit": True}
        invitation.refresh_from_db()
        assert invitation.status == "accepted"

    def test_new_user_registers_and_accepts(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="brand-new@example.com",
            role="admin",
            permissions={},
            invited_by=restaurant.owner,
        )
        staff = TeamService.accept_invitation(
            invitation.token,
            registration_data={
                "first_name": "New",
                "last_name": "Person",
                "password": "securepass123",
            },
        )
        assert staff.user.email == "brand-new@example.com"
        assert staff.role == "admin"
        assert User.objects.filter(email="brand-new@example.com").exists()

    def test_expired_token_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="late@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        from datetime import timedelta
        from django.utils import timezone
        invitation.expires_at = timezone.now() - timedelta(days=1)
        invitation.save()
        with pytest.raises(ValidationError, match="expired"):
            TeamService.accept_invitation(invitation.token)

    def test_no_user_no_registration_data_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="nobody@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        with pytest.raises(ValidationError, match="registration details"):
            TeamService.accept_invitation(invitation.token)

    def test_already_accepted_token_rejected(self):
        restaurant = RestaurantFactory()
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="used@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="used@example.com")
        TeamService.accept_invitation(invitation.token, user=user)
        with pytest.raises(ValidationError, match="Invalid or already used"):
            TeamService.accept_invitation(invitation.token)


@pytest.mark.django_db
class TestUpdateMember:
    def test_change_role(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        updated = TeamService.update_member(
            restaurant=restaurant,
            staff_id=staff.id,
            role="admin",
            acting_user=restaurant.owner,
        )
        assert updated.role == "admin"

    def test_cannot_demote_owner(self):
        restaurant = RestaurantFactory()
        owner_staff = RestaurantStaffFactory(
            user=restaurant.owner, restaurant=restaurant, role="owner"
        )
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="cannot"):
            TeamService.update_member(
                restaurant=restaurant,
                staff_id=owner_staff.id,
                role="member",
                acting_user=admin,
            )


@pytest.mark.django_db
class TestRemoveMember:
    def test_remove_member(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        TeamService.remove_member(
            restaurant=restaurant,
            staff_id=staff.id,
            acting_user=restaurant.owner,
        )
        assert not RestaurantStaff.objects.filter(id=staff.id).exists()

    def test_cannot_remove_owner(self):
        restaurant = RestaurantFactory()
        owner_staff = RestaurantStaffFactory(
            user=restaurant.owner, restaurant=restaurant, role="owner"
        )
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="cannot remove the owner"):
            TeamService.remove_member(
                restaurant=restaurant,
                staff_id=owner_staff.id,
                acting_user=admin,
            )


@pytest.mark.django_db
class TestTransferOwnership:
    def test_transfer_to_admin(self):
        restaurant = RestaurantFactory()
        old_owner = restaurant.owner
        RestaurantStaffFactory(user=old_owner, restaurant=restaurant, role="owner")
        new_owner = UserFactory()
        RestaurantStaffFactory(user=new_owner, restaurant=restaurant, role="admin")
        TeamService.transfer_ownership(
            restaurant=restaurant,
            new_owner_id=str(new_owner.id),
            acting_user=old_owner,
        )
        restaurant.refresh_from_db()
        assert restaurant.owner == new_owner
        new_owner_staff = RestaurantStaff.objects.get(user=new_owner, restaurant=restaurant)
        assert new_owner_staff.role == "owner"
        old_owner_staff = RestaurantStaff.objects.get(user=old_owner, restaurant=restaurant)
        assert old_owner_staff.role == "admin"

    def test_non_owner_cannot_transfer(self):
        restaurant = RestaurantFactory()
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        target = UserFactory()
        RestaurantStaffFactory(user=target, restaurant=restaurant, role="admin")
        with pytest.raises(ValidationError, match="Only the owner"):
            TeamService.transfer_ownership(
                restaurant=restaurant,
                new_owner_id=str(target.id),
                acting_user=admin,
            )


@pytest.mark.django_db
class TestGetEffectivePermissions:
    def test_owner_gets_all(self):
        restaurant = RestaurantFactory()
        perms = TeamService.get_effective_permissions(restaurant.owner, restaurant)
        assert perms["role"] == "owner"
        assert perms["menu_edit"] is True
        assert perms["order_manage"] is True
        assert perms["is_admin"] is True

    def test_member_with_override(self):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        perms = TeamService.get_effective_permissions(member, restaurant)
        assert perms["role"] == "member"
        assert perms["menu_edit"] is True
        assert perms["order_manage"] is False
        assert perms["is_admin"] is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `cd backend && python -m pytest restaurants/tests/test_team_service.py -v`

- [ ] **Step 3: Implement TeamService**

Create `backend/restaurants/services/team_service.py`:

```python
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from rest_framework.exceptions import ValidationError

from restaurants.models import Invitation, Restaurant, RestaurantStaff

User = get_user_model()


class TeamService:

    @staticmethod
    def invite_member(restaurant, email, role, permissions, invited_by):
        if restaurant.owner.email == email:
            raise ValidationError("This person is the owner.")
        if RestaurantStaff.objects.filter(
            restaurant=restaurant, user__email=email
        ).exists():
            raise ValidationError("This person is already on your team.")
        if Invitation.objects.filter(
            restaurant=restaurant, email=email, status="pending"
        ).exists():
            raise ValidationError("Invitation already pending — resend or revoke it first.")

        invitation = Invitation.objects.create(
            restaurant=restaurant,
            email=email,
            role=role,
            permissions=permissions or {},
            invited_by=invited_by,
        )
        return invitation

    @staticmethod
    @transaction.atomic
    def accept_invitation(token, user=None, registration_data=None):
        try:
            invitation = Invitation.objects.select_related("restaurant").get(
                token=token, status="pending"
            )
        except Invitation.DoesNotExist:
            raise ValidationError("Invalid or already used invitation.")

        if invitation.is_expired:
            invitation.status = "expired"
            invitation.save(update_fields=["status"])
            raise ValidationError("This invitation has expired.")

        if user is None and registration_data:
            user = User.objects.create_user(
                email=invitation.email,
                first_name=registration_data.get("first_name", ""),
                last_name=registration_data.get("last_name", ""),
                password=registration_data["password"],
            )
        elif user is None:
            existing = User.objects.filter(email=invitation.email).first()
            if existing:
                user = existing
            else:
                raise ValidationError("Please provide registration details or log in.")

        staff = RestaurantStaff.objects.create(
            user=user,
            restaurant=invitation.restaurant,
            role=invitation.role,
            permissions=invitation.permissions,
        )
        invitation.status = "accepted"
        invitation.save(update_fields=["status"])
        return staff

    @staticmethod
    def update_member(restaurant, staff_id, role=None, permissions=None, acting_user=None):
        try:
            staff = RestaurantStaff.objects.get(id=staff_id, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            raise ValidationError("Team member not found.")

        if staff.role == "owner":
            raise ValidationError("You cannot change the owner's role.")

        if role is not None:
            staff.role = role
        if permissions is not None:
            staff.permissions = permissions
        staff.save()
        return staff

    @staticmethod
    def remove_member(restaurant, staff_id, acting_user):
        try:
            staff = RestaurantStaff.objects.get(id=staff_id, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            raise ValidationError("Team member not found.")

        if staff.role == "owner":
            raise ValidationError("You cannot remove the owner.")

        staff.delete()

    @staticmethod
    @transaction.atomic
    def transfer_ownership(restaurant, new_owner_id, acting_user):
        if restaurant.owner != acting_user:
            raise ValidationError("Only the owner can transfer ownership.")

        try:
            new_owner = User.objects.get(id=new_owner_id)
        except User.DoesNotExist:
            raise ValidationError("User not found.")

        if not RestaurantStaff.objects.filter(
            user=new_owner, restaurant=restaurant, role__in=["admin", "owner"]
        ).exists():
            raise ValidationError("Can only transfer ownership to an existing admin.")

        old_owner = restaurant.owner
        restaurant.owner = new_owner
        restaurant.save(update_fields=["owner"])

        RestaurantStaff.objects.filter(
            user=new_owner, restaurant=restaurant
        ).update(role="owner")
        RestaurantStaff.objects.filter(
            user=old_owner, restaurant=restaurant
        ).update(role="admin")

    @staticmethod
    def get_effective_permissions(user, restaurant):
        is_owner = restaurant.owner == user
        if is_owner:
            return {
                "role": "owner",
                "is_admin": True,
                "menu_edit": True,
                "order_manage": True,
            }
        try:
            staff = RestaurantStaff.objects.get(user=user, restaurant=restaurant)
        except RestaurantStaff.DoesNotExist:
            return None

        if staff.role == "admin":
            return {
                "role": "admin",
                "is_admin": True,
                "menu_edit": True,
                "order_manage": True,
            }

        return {
            "role": "member",
            "is_admin": False,
            "menu_edit": staff.permissions.get("menu_edit", False),
            "order_manage": staff.permissions.get("order_manage", False),
        }
```

- [ ] **Step 4: Register in services __init__.py**

Add to `backend/restaurants/services/__init__.py`:

```python
from .team_service import TeamService
```

And add `"TeamService"` to the `__all__` list.

- [ ] **Step 5: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_service.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/services/team_service.py backend/restaurants/services/__init__.py backend/restaurants/tests/test_team_service.py
git commit -m "feat: add TeamService with invite, accept, update, remove, transfer, permissions"
```

---

## Chunk 3: API Endpoints & Email

### Task 6: Team management serializers

**Files:**
- Create: `backend/restaurants/serializers/team_serializers.py`
- Modify: `backend/restaurants/serializers/__init__.py`

- [ ] **Step 1: Create serializers**

Create `backend/restaurants/serializers/team_serializers.py`:

```python
from rest_framework import serializers

from restaurants.models import Invitation, RestaurantStaff


class StaffMemberSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(source="user.email", read_only=True)
    first_name = serializers.CharField(source="user.first_name", read_only=True)
    last_name = serializers.CharField(source="user.last_name", read_only=True)
    user_id = serializers.UUIDField(source="user.id", read_only=True)

    class Meta:
        model = RestaurantStaff
        fields = ["id", "user_id", "email", "first_name", "last_name", "role", "permissions", "invited_at"]


class InvitationSerializer(serializers.ModelSerializer):
    invited_by_name = serializers.CharField(source="invited_by.name", read_only=True)

    class Meta:
        model = Invitation
        fields = ["id", "email", "role", "permissions", "status", "invited_by_name", "created_at", "expires_at"]


class InviteMemberSerializer(serializers.Serializer):
    email = serializers.EmailField()
    role = serializers.ChoiceField(choices=["admin", "member"])
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False, default=dict)


class UpdateMemberSerializer(serializers.Serializer):
    role = serializers.ChoiceField(choices=["admin", "member"], required=False)
    permissions = serializers.DictField(child=serializers.BooleanField(), required=False)


class TransferOwnershipSerializer(serializers.Serializer):
    new_owner_id = serializers.UUIDField()


class AcceptInvitationSerializer(serializers.Serializer):
    first_name = serializers.CharField(required=False)
    last_name = serializers.CharField(required=False)
    password = serializers.CharField(required=False, min_length=8)
    auth_provider = serializers.ChoiceField(choices=["google", "apple"], required=False)
    auth_token = serializers.CharField(required=False)


class InvitationDetailSerializer(serializers.ModelSerializer):
    restaurant_name = serializers.CharField(source="restaurant.name", read_only=True)
    restaurant_slug = serializers.CharField(source="restaurant.slug", read_only=True)
    invited_by_name = serializers.CharField(source="invited_by.name", read_only=True)
    is_expired = serializers.BooleanField(read_only=True)

    class Meta:
        model = Invitation
        fields = [
            "id", "restaurant_name", "restaurant_slug", "email", "role",
            "permissions", "status", "invited_by_name", "is_expired", "expires_at",
        ]
```

- [ ] **Step 2: Update serializers __init__.py**

Add to `backend/restaurants/serializers/__init__.py`:

```python
from .team_serializers import (
    StaffMemberSerializer,
    InvitationSerializer,
    InviteMemberSerializer,
    UpdateMemberSerializer,
    TransferOwnershipSerializer,
    AcceptInvitationSerializer,
    InvitationDetailSerializer,
)
```

- [ ] **Step 3: Commit**

```bash
git add backend/restaurants/serializers/team_serializers.py backend/restaurants/serializers/__init__.py
git commit -m "feat: add team management serializers"
```

### Task 7: Team management views and URL routes

**Files:**
- Create: `backend/restaurants/views_team.py`
- Modify: `backend/restaurants/urls.py`
- Test: `backend/restaurants/tests/test_team_api.py` (create)

- [ ] **Step 1: Write API tests**

Create `backend/restaurants/tests/test_team_api.py`:

```python
import pytest
from rest_framework import status

from restaurants.models import Invitation, RestaurantStaff
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory


@pytest.mark.django_db
class TestTeamListView:
    def test_owner_can_list_team(self, api_client):
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        api_client.force_authenticate(user=restaurant.owner)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/team/")
        assert response.status_code == status.HTTP_200_OK
        assert "members" in response.data
        assert "invitations" in response.data

    def test_member_cannot_list_team(self, api_client):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/team/")
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestInviteView:
    def test_owner_can_invite(self, api_client):
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        api_client.force_authenticate(user=restaurant.owner)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/team/invite/",
            {"email": "new@example.com", "role": "member"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert Invitation.objects.filter(email="new@example.com").exists()


@pytest.mark.django_db
class TestRemoveMemberView:
    def test_owner_can_remove_member(self, api_client):
        restaurant = RestaurantFactory()
        RestaurantStaffFactory(user=restaurant.owner, restaurant=restaurant, role="owner")
        member = UserFactory()
        staff = RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=restaurant.owner)
        response = api_client.delete(f"/api/restaurants/{restaurant.slug}/team/{staff.id}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not RestaurantStaff.objects.filter(id=staff.id).exists()


@pytest.mark.django_db
class TestInvitationAcceptView:
    def test_existing_user_can_accept(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="joiner@example.com",
            role="member",
            permissions={"menu_edit": True},
            invited_by=restaurant.owner,
        )
        user = UserFactory(email="joiner@example.com")
        api_client.force_authenticate(user=user)
        response = api_client.post(f"/api/invitations/{invitation.token}/accept/")
        assert response.status_code == status.HTTP_200_OK
        assert RestaurantStaff.objects.filter(user=user, restaurant=restaurant).exists()

    def test_new_user_registers_and_accepts(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="brand-new@example.com",
            role="admin",
            permissions={},
            invited_by=restaurant.owner,
        )
        response = api_client.post(
            f"/api/invitations/{invitation.token}/accept/",
            {"first_name": "New", "last_name": "User", "password": "securepass123"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert RestaurantStaff.objects.filter(
            user__email="brand-new@example.com", restaurant=restaurant
        ).exists()

    def test_validate_invitation(self, api_client):
        restaurant = RestaurantFactory()
        from restaurants.services.team_service import TeamService
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email="check@example.com",
            role="member",
            permissions={},
            invited_by=restaurant.owner,
        )
        response = api_client.get(f"/api/invitations/{invitation.token}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["restaurant_name"] == restaurant.name
        assert response.data["role"] == "member"


@pytest.mark.django_db
class TestMyRoleView:
    def test_returns_role_and_permissions(self, api_client):
        restaurant = RestaurantFactory()
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/my-role/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["role"] == "member"
        assert response.data["menu_edit"] is True
        assert response.data["order_manage"] is False
```

- [ ] **Step 2: Run tests — expect failure**

Run: `cd backend && python -m pytest restaurants/tests/test_team_api.py -v`

- [ ] **Step 3: Create views**

Create `backend/restaurants/views_team.py`:

```python
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from restaurants.models import Invitation, RestaurantStaff
from restaurants.permissions import IsRestaurantAdmin
from restaurants.serializers import (
    AcceptInvitationSerializer,
    InvitationDetailSerializer,
    InvitationSerializer,
    InviteMemberSerializer,
    StaffMemberSerializer,
    TransferOwnershipSerializer,
    UpdateMemberSerializer,
)
from restaurants.services import TeamService
from restaurants.views import RestaurantMixin


class TeamListView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/team/"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        members = RestaurantStaff.objects.filter(restaurant=restaurant).select_related("user")
        invitations = Invitation.objects.filter(restaurant=restaurant, status="pending")
        return Response({
            "members": StaffMemberSerializer(members, many=True).data,
            "invitations": InvitationSerializer(invitations, many=True).data,
        })


class InviteMemberView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/team/invite/"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = InviteMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        invitation = TeamService.invite_member(
            restaurant=restaurant,
            email=serializer.validated_data["email"],
            role=serializer.validated_data["role"],
            permissions=serializer.validated_data.get("permissions", {}),
            invited_by=request.user,
        )
        from restaurants.tasks import send_invitation_email_task
        send_invitation_email_task.delay(str(invitation.id))
        return Response(InvitationSerializer(invitation).data, status=status.HTTP_201_CREATED)


class MemberDetailView(RestaurantMixin, APIView):
    """PATCH + DELETE /api/restaurants/:slug/team/:staff_id/"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def patch(self, request, slug, staff_id):
        restaurant = self.get_restaurant()
        serializer = UpdateMemberSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        staff = TeamService.update_member(
            restaurant=restaurant,
            staff_id=staff_id,
            role=serializer.validated_data.get("role"),
            permissions=serializer.validated_data.get("permissions"),
            acting_user=request.user,
        )
        return Response(StaffMemberSerializer(staff).data)

    def delete(self, request, slug, staff_id):
        restaurant = self.get_restaurant()
        TeamService.remove_member(
            restaurant=restaurant,
            staff_id=staff_id,
            acting_user=request.user,
        )
        return Response(status=status.HTTP_204_NO_CONTENT)


class TransferOwnershipView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/team/transfer-ownership/"""

    def get_permissions(self):
        return [IsAuthenticated()]

    def post(self, request, slug):
        restaurant = self.get_restaurant()
        serializer = TransferOwnershipSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        TeamService.transfer_ownership(
            restaurant=restaurant,
            new_owner_id=str(serializer.validated_data["new_owner_id"]),
            acting_user=request.user,
        )
        return Response({"detail": "Ownership transferred."})


class ResendInvitationView(RestaurantMixin, APIView):
    """POST /api/restaurants/:slug/team/invitations/:id/resend/"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def post(self, request, slug, invitation_id):
        restaurant = self.get_restaurant()
        from datetime import timedelta
        from django.utils import timezone
        try:
            invitation = Invitation.objects.get(
                id=invitation_id, restaurant=restaurant, status="pending"
            )
        except Invitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
        invitation.expires_at = timezone.now() + timedelta(days=7)
        invitation.save(update_fields=["expires_at"])
        from restaurants.tasks import send_invitation_email_task
        send_invitation_email_task.delay(str(invitation.id))
        return Response(InvitationSerializer(invitation).data)


class RevokeInvitationView(RestaurantMixin, APIView):
    """DELETE /api/restaurants/:slug/team/invitations/:id/"""

    def get_permissions(self):
        return [IsAuthenticated(), IsRestaurantAdmin()]

    def delete(self, request, slug, invitation_id):
        restaurant = self.get_restaurant()
        try:
            invitation = Invitation.objects.get(
                id=invitation_id, restaurant=restaurant, status="pending"
            )
        except Invitation.DoesNotExist:
            return Response({"detail": "Invitation not found."}, status=status.HTTP_404_NOT_FOUND)
        invitation.status = "revoked"
        invitation.save(update_fields=["status"])
        return Response(status=status.HTTP_204_NO_CONTENT)


class InvitationValidateView(APIView):
    """GET /api/invitations/:token/ — public"""
    permission_classes = [AllowAny]

    def get(self, request, token):
        try:
            invitation = Invitation.objects.select_related(
                "restaurant", "invited_by"
            ).get(token=token)
        except Invitation.DoesNotExist:
            return Response({"detail": "Invalid invitation."}, status=status.HTTP_404_NOT_FOUND)
        return Response(InvitationDetailSerializer(invitation).data)


class InvitationAcceptView(APIView):
    """POST /api/invitations/:token/accept/"""
    permission_classes = [AllowAny]

    def post(self, request, token):
        serializer = AcceptInvitationSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        user = request.user if request.user.is_authenticated else None
        registration_data = None
        if not user and data.get("password"):
            registration_data = {
                "first_name": data.get("first_name", ""),
                "last_name": data.get("last_name", ""),
                "password": data["password"],
            }

        staff = TeamService.accept_invitation(
            token=token,
            user=user,
            registration_data=registration_data,
        )
        return Response({
            "detail": "Invitation accepted.",
            "restaurant_slug": staff.restaurant.slug,
            "role": staff.role,
        })


class MyRoleView(RestaurantMixin, APIView):
    """GET /api/restaurants/:slug/my-role/"""

    def get_permissions(self):
        return [IsAuthenticated()]

    def get(self, request, slug):
        restaurant = self.get_restaurant()
        perms = TeamService.get_effective_permissions(request.user, restaurant)
        if perms is None:
            return Response({"detail": "Not a team member."}, status=status.HTTP_403_FORBIDDEN)
        return Response(perms)
```

- [ ] **Step 4: Add URL routes**

Add to `backend/restaurants/urls.py` — import the new views and add URL patterns:

Add imports:
```python
from restaurants.views_team import (
    InvitationAcceptView,
    InvitationValidateView,
    InviteMemberView,
    MemberDetailView,
    MyRoleView,
    ResendInvitationView,
    RevokeInvitationView,
    TeamListView,
    TransferOwnershipView,
)
```

Add URL patterns inside `urlpatterns`:
```python
    # Team Management
    path("restaurants/<slug:slug>/team/", TeamListView.as_view(), name="team-list"),
    path("restaurants/<slug:slug>/team/invite/", InviteMemberView.as_view(), name="team-invite"),
    path("restaurants/<slug:slug>/team/<int:staff_id>/", MemberDetailView.as_view(), name="team-member-detail"),
    path("restaurants/<slug:slug>/team/transfer-ownership/", TransferOwnershipView.as_view(), name="team-transfer-ownership"),
    path("restaurants/<slug:slug>/team/invitations/<uuid:invitation_id>/resend/", ResendInvitationView.as_view(), name="team-resend-invitation"),
    path("restaurants/<slug:slug>/team/invitations/<uuid:invitation_id>/", RevokeInvitationView.as_view(), name="team-revoke-invitation"),
    path("restaurants/<slug:slug>/my-role/", MyRoleView.as_view(), name="my-role"),
    # Invitations (public)
    path("invitations/<str:token>/", InvitationValidateView.as_view(), name="invitation-validate"),
    path("invitations/<str:token>/accept/", InvitationAcceptView.as_view(), name="invitation-accept"),
```

- [ ] **Step 5: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_api.py -v`

- [ ] **Step 6: Commit**

```bash
git add backend/restaurants/views_team.py backend/restaurants/urls.py backend/restaurants/tests/test_team_api.py
git commit -m "feat: add team management API endpoints and invitation views"
```

### Task 8: Invitation email template and Celery task

**Files:**
- Create: `backend/orders/templates/emails/team_invitation.html`
- Modify: `backend/restaurants/notifications.py`
- Modify: `backend/restaurants/tasks.py`

- [ ] **Step 1: Create email template**

Create `backend/orders/templates/emails/team_invitation.html` following the existing `merchant_welcome.html` pattern:

```html
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>You're invited to join {{ restaurant_name }}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4f4f5;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,Helvetica,Arial,sans-serif;">
<table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color:#f4f4f5;padding:24px 0;">
<tr><td align="center">
<table role="presentation" width="600" cellpadding="0" cellspacing="0" style="background-color:#ffffff;border-radius:8px;overflow:hidden;max-width:100%;">

<tr><td style="background-color:#18181b;padding:24px 32px;">
  <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:600;">Join {{ restaurant_name }} on MenuChat</h1>
</td></tr>

<tr><td style="padding:32px;">
  <p style="margin:0 0 16px;color:#18181b;font-size:16px;">Hi there,</p>
  <p style="margin:0 0 24px;color:#52525b;font-size:14px;line-height:1.6;">
    <strong>{{ invited_by_name }}</strong> has invited you to join
    <strong>{{ restaurant_name }}</strong> as {{ role_display }}.
  </p>

  <p style="margin:0;text-align:center;">
    <a href="{{ invite_url }}" style="display:inline-block;padding:12px 32px;background-color:#18181b;color:#ffffff;text-decoration:none;border-radius:6px;font-size:14px;font-weight:500;">Accept Invitation</a>
  </p>

  <p style="margin:24px 0 0;color:#a1a1aa;font-size:12px;text-align:center;line-height:1.6;">
    This invitation expires on {{ expires_date }}.<br>
    If you didn't expect this email, you can safely ignore it.
  </p>
</td></tr>

<tr><td style="padding:16px 32px;background-color:#fafafa;border-top:1px solid #e4e4e7;">
  <p style="margin:0;color:#a1a1aa;font-size:12px;text-align:center;">
    {{ restaurant_name }} &mdash; Powered by MenuChat
  </p>
</td></tr>

</table>
</td></tr>
</table>
</body>
</html>
```

- [ ] **Step 2: Add notification function**

Add to `backend/restaurants/notifications.py`:

```python
def send_team_invitation_email(invitation) -> None:
    """Send invitation email to a prospective team member."""
    context = {
        "restaurant_name": invitation.restaurant.name,
        "invited_by_name": invitation.invited_by.name or invitation.invited_by.email,
        "role_display": "an Admin" if invitation.role == "admin" else "a Member",
        "invite_url": f"{settings.FRONTEND_URL}/invite/{invitation.token}",
        "expires_date": invitation.expires_at.strftime("%B %d, %Y"),
    }
    html_message = render_to_string("emails/team_invitation.html", context)
    plain_message = strip_tags(html_message)

    try:
        send_mail(
            subject=f"You're invited to join {invitation.restaurant.name} on MenuChat",
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[invitation.email],
            html_message=html_message,
            fail_silently=False,
        )
    except Exception:
        logger.exception("Failed to send invitation email to %s", invitation.email)
```

- [ ] **Step 3: Add Celery task**

Add to `backend/restaurants/tasks.py`:

```python
@shared_task
def send_invitation_email_task(invitation_id: str):
    """Send team invitation email (async)."""
    from restaurants.models import Invitation
    try:
        invitation = Invitation.objects.select_related(
            "restaurant", "invited_by"
        ).get(id=invitation_id)
    except Invitation.DoesNotExist:
        logger.warning("send_invitation_email_task: invitation %s not found", invitation_id)
        return

    from restaurants.notifications import send_team_invitation_email
    send_team_invitation_email(invitation)
```

- [ ] **Step 4: Commit**

```bash
git add backend/orders/templates/emails/team_invitation.html backend/restaurants/notifications.py backend/restaurants/tasks.py
git commit -m "feat: add team invitation email template and async Celery task"
```

### Task 9: Apply permission classes to existing views

**Files:**
- Modify: `backend/restaurants/views.py`
- Modify: `backend/restaurants/views_menu_upload.py`
- Modify: `backend/orders/views.py`
- Modify: `backend/orders/tab_views.py`
- Test: `backend/restaurants/tests/test_team_permissions_integration.py` (create)

- [ ] **Step 1: Write integration tests for permission gating**

Create `backend/restaurants/tests/test_team_permissions_integration.py`:

```python
import pytest
from rest_framework import status

from restaurants.models import Subscription
from restaurants.tests.factories import RestaurantFactory, RestaurantStaffFactory, UserFactory
from datetime import timedelta
from django.utils import timezone


def _setup_restaurant_with_subscription():
    """Helper to create a restaurant with an active subscription."""
    restaurant = RestaurantFactory()
    Subscription.objects.create(
        restaurant=restaurant,
        plan="starter",
        status="active",
        current_period_start=timezone.now(),
        current_period_end=timezone.now() + timedelta(days=30),
    )
    return restaurant


@pytest.mark.django_db
class TestAdminOnlyViews:
    """Verify that admin-only views reject members."""

    def test_member_cannot_access_analytics(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/analytics/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_access_analytics(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        admin = UserFactory()
        RestaurantStaffFactory(user=admin, restaurant=restaurant, role="admin")
        api_client.force_authenticate(user=admin)
        response = api_client.get(f"/api/restaurants/{restaurant.slug}/analytics/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestMenuEditPermission:
    """Verify menu edit permission gating for members."""

    def test_member_without_permission_cannot_create_category(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        member = UserFactory()
        RestaurantStaffFactory(user=member, restaurant=restaurant, role="member")
        api_client.force_authenticate(user=member)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "New Category"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_member_with_permission_can_create_category(self, api_client):
        restaurant = _setup_restaurant_with_subscription()
        from restaurants.models import MenuVersion
        MenuVersion.objects.create(restaurant=restaurant, name="Main", is_active=True)
        member = UserFactory()
        RestaurantStaffFactory(
            user=member, restaurant=restaurant, role="member",
            permissions={"menu_edit": True},
        )
        api_client.force_authenticate(user=member)
        response = api_client.post(
            f"/api/restaurants/{restaurant.slug}/categories/",
            {"name": "New Category"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
```

- [ ] **Step 2: Run tests — expect failure (permissions not applied yet)**

Run: `cd backend && python -m pytest restaurants/tests/test_team_permissions_integration.py -v`

- [ ] **Step 3: Update views in restaurants/views.py**

Add the import at the top of `views.py`:
```python
from restaurants.permissions import HasActiveSubscription, IsRestaurantAdmin, HasPermission
```

Three patterns to apply. For each view listed, add the matching `get_permissions` override.

**Pattern A: Admin-only (all methods).** Add to each:
```python
def get_permissions(self):
    return [IsAuthenticated(), IsRestaurantAdmin()]
```
Views: `RestaurantAnalyticsView`, `SubscriptionDetailView`, `CreateCheckoutSessionView`, `CancelSubscriptionView`, `ReactivateSubscriptionView`, `BillingHistoryView`, `CreateBillingPortalView`, `ConnectOnboardView`, `ConnectStatusView`, `ConnectDashboardView`, `PayoutListView`, `PayoutDetailView`.

**Pattern B: Admin-only on write methods, any staff on GET.** Add to each:
```python
def get_permissions(self):
    if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
        return [IsAuthenticated(), IsRestaurantAdmin()]
    return [IsAuthenticated(), HasActiveSubscription()]
```
Views: `RestaurantDetailView` (note: this uses `generics.RetrieveUpdateAPIView` without `RestaurantMixin` — the pattern still works because `IsRestaurantAdmin` reads `slug` from `view.kwargs`), `AcceptingOrdersToggleView`, `OperatingHoursBulkView`, `TableListCreateView`, `TableDetailView`, `HolidayOverrideListCreateView`, `HolidayOverrideDetailView`.

**Pattern C: `menu_edit` permission on write methods.** Add to each:
```python
def get_permissions(self):
    if self.request.method in ("POST", "PUT", "PATCH", "DELETE"):
        return [IsAuthenticated(), HasPermission("menu_edit")]
    return [IsAuthenticated(), HasActiveSubscription()]
```
Views: `MenuCategoryListCreateView`, `MenuCategoryDetailView`, `MenuItemListCreateView`, `MenuItemDetailView`.

- [ ] **Step 4: Update views_menu_upload.py**

Add import and override `get_permissions` for all upload views:
```python
from restaurants.permissions import HasPermission
```

For `MenuUploadParseView`, `MenuUploadSaveView`, `MenuItemImageUploadView`, `MenuVersionActivateView`:
```python
def get_permissions(self):
    return [IsAuthenticated(), HasPermission("menu_edit")]
```

For `MenuVersionDetailView` (has GET, PATCH, DELETE):
```python
def get_permissions(self):
    if self.request.method in ("PATCH", "DELETE"):
        from restaurants.permissions import HasPermission
        return [IsAuthenticated(), HasPermission("menu_edit")]
    return super().get_permissions()
```

- [ ] **Step 5: Update orders/views.py — KitchenOrderUpdateView**

Add permission check to `KitchenOrderUpdateView.patch` method. Since this view doesn't use `RestaurantMixin` (it resolves the order by `order_id`, not `slug`), add an inline check:

```python
class KitchenOrderUpdateView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request, order_id):
        try:
            order = Order.objects.select_related("restaurant").get(id=order_id)
        except Order.DoesNotExist:
            return Response({"detail": "Order not found."}, status=status.HTTP_404_NOT_FOUND)

        # Permission check: owner/admin can always update, member needs order_manage
        from restaurants.services import TeamService
        perms = TeamService.get_effective_permissions(request.user, order.restaurant)
        if perms is None or (not perms["is_admin"] and not perms.get("order_manage")):
            return Response({"detail": "Permission denied."}, status=status.HTTP_403_FORBIDDEN)

        new_status = request.data.get("status")
        order = OrderService.update_order_status(order, new_status, request.user)
        return Response(OrderResponseSerializer(order).data)
```

- [ ] **Step 6: Update orders/tab_views.py — KitchenTabCloseView**

Apply the same inline permission check pattern:

```python
class KitchenTabCloseView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, tab_id):
        try:
            tab = Tab.objects.select_related("restaurant").get(id=tab_id)
        except Tab.DoesNotExist:
            return Response(status=status.HTTP_404_NOT_FOUND)

        from restaurants.services import TeamService
        perms = TeamService.get_effective_permissions(request.user, tab.restaurant)
        if perms is None or (not perms["is_admin"] and not perms.get("order_manage")):
            return Response(status=status.HTTP_403_FORBIDDEN)

        TabService.close_tab(tab)
        return Response(TabResponseSerializer(tab).data)
```

- [ ] **Step 7: Run tests — expect pass**

Run: `cd backend && python -m pytest restaurants/tests/test_team_permissions_integration.py -v`

Also run the full test suite to check for regressions:

Run: `cd backend && python -m pytest --tb=short`

- [ ] **Step 8: Commit**

```bash
git add backend/restaurants/views.py backend/restaurants/views_menu_upload.py backend/orders/views.py backend/orders/tab_views.py backend/restaurants/tests/test_team_permissions_integration.py
git commit -m "feat: apply role-based permission gating to all existing views"
```

---

## Chunk 4: Frontend — API Layer, Hooks, and Types

### Task 10: Add frontend types

**Files:**
- Modify: `frontend/src/types/index.ts`

- [ ] **Step 1: Add team-related types**

Append to `frontend/src/types/index.ts`:

```typescript
// Team types
export interface StaffMember {
  id: number;
  user_id: string;
  email: string;
  first_name: string;
  last_name: string;
  role: "owner" | "admin" | "member";
  permissions: Record<string, boolean>;
  invited_at: string;
}

export interface TeamInvitation {
  id: string;
  email: string;
  role: "admin" | "member";
  permissions: Record<string, boolean>;
  status: "pending" | "accepted" | "expired" | "revoked";
  invited_by_name: string;
  created_at: string;
  expires_at: string;
}

export interface TeamResponse {
  members: StaffMember[];
  invitations: TeamInvitation[];
}

export interface MyRoleResponse {
  role: "owner" | "admin" | "member";
  is_admin: boolean;
  menu_edit: boolean;
  order_manage: boolean;
}

export interface InvitationDetail {
  id: string;
  restaurant_name: string;
  restaurant_slug: string;
  email: string;
  role: "admin" | "member";
  permissions: Record<string, boolean>;
  status: string;
  invited_by_name: string;
  is_expired: boolean;
  expires_at: string;
}
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/types/index.ts
git commit -m "feat: add team management TypeScript types"
```

### Task 11: Add API functions

**Files:**
- Modify: `frontend/src/lib/api.ts`

- [ ] **Step 1: Add team API functions**

Append to `frontend/src/lib/api.ts`:

```typescript
// Team Management
export async function fetchTeam(slug: string): Promise<TeamResponse> {
  return apiFetch<TeamResponse>(`/api/restaurants/${slug}/team/`);
}

export async function inviteTeamMember(
  slug: string,
  data: { email: string; role: string; permissions?: Record<string, boolean> }
): Promise<TeamInvitation> {
  return apiFetch<TeamInvitation>(`/api/restaurants/${slug}/team/invite/`, {
    method: "POST",
    body: JSON.stringify(data),
  });
}

export async function updateTeamMember(
  slug: string,
  staffId: number,
  data: { role?: string; permissions?: Record<string, boolean> }
): Promise<StaffMember> {
  return apiFetch<StaffMember>(`/api/restaurants/${slug}/team/${staffId}/`, {
    method: "PATCH",
    body: JSON.stringify(data),
  });
}

export async function removeTeamMember(slug: string, staffId: number): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/${staffId}/`, {
    method: "DELETE",
  });
}

export async function transferOwnership(slug: string, newOwnerId: string): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/transfer-ownership/`, {
    method: "POST",
    body: JSON.stringify({ new_owner_id: newOwnerId }),
  });
}

export async function resendInvitation(slug: string, invitationId: string): Promise<TeamInvitation> {
  return apiFetch<TeamInvitation>(`/api/restaurants/${slug}/team/invitations/${invitationId}/resend/`, {
    method: "POST",
  });
}

export async function revokeInvitation(slug: string, invitationId: string): Promise<void> {
  return apiFetch<void>(`/api/restaurants/${slug}/team/invitations/${invitationId}/`, {
    method: "DELETE",
  });
}

export async function fetchMyRole(slug: string): Promise<MyRoleResponse> {
  return apiFetch<MyRoleResponse>(`/api/restaurants/${slug}/my-role/`);
}

export async function fetchInvitationDetail(token: string): Promise<InvitationDetail> {
  return apiFetch<InvitationDetail>(`/api/invitations/${token}/`);
}

export async function acceptInvitation(
  token: string,
  data?: { first_name?: string; last_name?: string; password?: string }
): Promise<{ detail: string; restaurant_slug: string; role: string }> {
  return apiFetch(`/api/invitations/${token}/accept/`, {
    method: "POST",
    body: JSON.stringify(data || {}),
  });
}
```

Add the type imports at the top of the file (where other types are imported):
```typescript
import type { TeamResponse, TeamInvitation, StaffMember, MyRoleResponse, InvitationDetail } from "@/types";
```

- [ ] **Step 2: Commit**

```bash
git add frontend/src/lib/api.ts
git commit -m "feat: add team management API functions"
```

### Task 12: Create frontend hooks

**Files:**
- Create: `frontend/src/hooks/use-team.ts`
- Create: `frontend/src/hooks/use-my-role.ts`
- Create: `frontend/src/hooks/use-invitation.ts`

- [ ] **Step 1: Create use-team.ts**

```typescript
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  fetchTeam,
  inviteTeamMember,
  updateTeamMember,
  removeTeamMember,
  transferOwnership,
  resendInvitation,
  revokeInvitation,
} from "@/lib/api";

export function useTeam(slug: string) {
  return useQuery({
    queryKey: ["team", slug],
    queryFn: () => fetchTeam(slug),
    enabled: !!slug,
  });
}

export function useInviteTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (data: { email: string; role: string; permissions?: Record<string, boolean> }) =>
      inviteTeamMember(slug, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useUpdateTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ staffId, data }: { staffId: number; data: { role?: string; permissions?: Record<string, boolean> } }) =>
      updateTeamMember(slug, staffId, data),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useRemoveTeamMember(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (staffId: number) => removeTeamMember(slug, staffId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useTransferOwnership(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (newOwnerId: string) => transferOwnership(slug, newOwnerId),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["team", slug] });
      queryClient.invalidateQueries({ queryKey: ["my-role", slug] });
    },
  });
}

export function useResendInvitation(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => resendInvitation(slug, invitationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}

export function useRevokeInvitation(slug: string) {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (invitationId: string) => revokeInvitation(slug, invitationId),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["team", slug] }),
  });
}
```

- [ ] **Step 2: Create use-my-role.ts**

```typescript
import { useQuery } from "@tanstack/react-query";
import { fetchMyRole } from "@/lib/api";
import type { MyRoleResponse } from "@/types";

export function useMyRole(slug: string) {
  return useQuery({
    queryKey: ["my-role", slug],
    queryFn: () => fetchMyRole(slug),
    enabled: !!slug,
  });
}

export function useCan(slug: string) {
  const { data: role } = useMyRole(slug);
  return (permission: string): boolean => {
    if (!role) return false;
    if (role.is_admin) return true;
    return (role as Record<string, unknown>)[permission] === true;
  };
}
```

- [ ] **Step 3: Create use-invitation.ts**

```typescript
import { useQuery, useMutation } from "@tanstack/react-query";
import { fetchInvitationDetail, acceptInvitation } from "@/lib/api";

export function useInvitationDetail(token: string) {
  return useQuery({
    queryKey: ["invitation", token],
    queryFn: () => fetchInvitationDetail(token),
    enabled: !!token,
  });
}

export function useAcceptInvitation(token: string) {
  return useMutation({
    mutationFn: (data?: { first_name?: string; last_name?: string; password?: string }) =>
      acceptInvitation(token, data),
  });
}
```

- [ ] **Step 4: Commit**

```bash
git add frontend/src/hooks/use-team.ts frontend/src/hooks/use-my-role.ts frontend/src/hooks/use-invitation.ts
git commit -m "feat: add team management React hooks"
```

---

## Chunk 5: Frontend — Pages and Navigation

### Task 13: Team Management page

**Files:**
- Create: `frontend/src/app/account/restaurants/[slug]/team/page.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/team/components/invite-modal.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/team/components/member-row.tsx`
- Create: `frontend/src/app/account/restaurants/[slug]/team/components/pending-invite-row.tsx`

This is a large UI task. Implement the team management page matching the mockups in `.superpowers/brainstorm/team-management-v2.html`. Key elements:

- Team members table with role badges (Owner=amber, Admin=blue, Member=gray)
- Extra permissions shown as green tags on Member rows
- ⋮ dropdown menu per row (using shadcn `DropdownMenu`)
- Pending invitations section with Resend/Revoke buttons
- "+ Invite Member" button opening a modal dialog
- Invite modal: email input, role selector (Admin/Member toggle), permission checkboxes shown when Member is selected

Use shadcn/ui components: `Card`, `Button`, `Dialog`, `DropdownMenu`, `Input`, `Badge`, `Checkbox`, `Label`.

Use hooks: `useTeam`, `useMyRole`, `useInviteTeamMember`, `useUpdateTeamMember`, `useRemoveTeamMember`, `useTransferOwnership`, `useResendInvitation`, `useRevokeInvitation`.

- [ ] **Step 1: Create page.tsx** — Main page component that fetches team data and renders the table layout
- [ ] **Step 2: Create invite-modal.tsx** — Dialog with email, role selector, permission toggles
- [ ] **Step 3: Create member-row.tsx** — Row component with role badge, permissions tags, ⋮ dropdown. Key rules for the dropdown menu: "Transfer Ownership" option only appears when the acting user is the Owner (not Admin) and only on the Owner's own row. "Remove from team" and role change options require a confirmation `AlertDialog` before executing. Pass `slug` to mutation hooks via props from page.tsx.
- [ ] **Step 4: Create pending-invite-row.tsx** — Row for pending invitations with Resend/Revoke
- [ ] **Step 5: Test in browser** — Start dev server, navigate to `/account/restaurants/{slug}/team`, verify all CRUD operations
- [ ] **Step 6: Commit**

```bash
git add frontend/src/app/account/restaurants/\[slug\]/team/
git commit -m "feat: add team management page with invite modal and member actions"
```

### Task 14: Invite acceptance page

**Files:**
- Create: `frontend/src/app/invite/[token]/page.tsx`

Implement the invite acceptance page matching the mockups in `.superpowers/brainstorm/invite-acceptance.html`. Four states:

- **Valid + logged in**: Show restaurant name, inviter, role, permissions list, "Accept Invitation" button. Use `useAuthStore` to check `user` is not null.
- **Valid + not logged in, has account**: Show "Log in" link that redirects to `/login?next=/invite/{token}`. After login, user returns to this page and sees the logged-in state.
- **Valid + no account**: Inline registration form (email locked from invitation, name, password fields, Google/Apple social login buttons). Social auth is an optional enhancement — password-based registration is the minimum.
- **Error states**: Expired (clock icon + "Ask the restaurant to send a new one"), Already accepted (checkmark + "Go to Dashboard" link), Invalid/revoked (generic error)

Use hooks: `useInvitationDetail`, `useAcceptInvitation`. Use `useAuthStore` from `@/stores/auth-store` to determine login state (`user !== null` = logged in).

After successful acceptance, redirect to `/kitchen/{restaurant_slug}` (for members) or `/account/restaurants/{restaurant_slug}` (for admins).

- [ ] **Step 1: Create page.tsx** — Fetches invitation detail, shows appropriate state
- [ ] **Step 2: Test in browser** — Create a test invitation via the team page, open the link, verify all three scenarios
- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/invite/
git commit -m "feat: add invite acceptance page with registration flow"
```

### Task 15: Navigation gating — add Team link and guard existing routes

**Files:**
- Modify: `frontend/src/app/account/restaurants/page.tsx`

- [ ] **Step 1: Add Team button and guard navigation by role**

Update the button bar in `frontend/src/app/account/restaurants/page.tsx`. The `useCan` hook (from `use-my-role.ts`) needs to be called per restaurant. Extract the restaurant card into a `RestaurantCard` component that calls `useCan(slug)` internally and conditionally renders buttons.

Key changes:
- Add "Team" button (links to `/account/restaurants/${slug}/team`) — visible only when `useCan(slug)("is_admin")` returns true (Owner/Admin)
- Hide Analytics, Billing, Settings buttons unless `useCan(slug)("is_admin")`
- Hide Menu button unless `can("menu_edit")`
- Keep Orders and Kitchen buttons visible to all roles

- [ ] **Step 2: Test in browser** — Log in as different roles and verify navigation buttons appear/hide correctly
- [ ] **Step 3: Commit**

```bash
git add frontend/src/app/account/restaurants/page.tsx
git commit -m "feat: add role-based navigation gating and Team button"
```

### Task 16: Final integration test and cleanup

- [ ] **Step 1: Run full backend test suite**

Run: `cd backend && python -m pytest --tb=short`

Fix any failures.

- [ ] **Step 2: Run frontend type check**

Run: `cd frontend && npx tsc --noEmit`

Fix any type errors.

- [ ] **Step 3: End-to-end manual test**

Test the complete flow:
1. Log in as restaurant owner
2. Navigate to Team page
3. Invite a new member with `menu_edit` permission
4. Open the invitation link in an incognito window
5. Register as the new user and accept
6. Verify the new user appears on the team list
7. Verify the new user can edit menu but not access analytics
8. Resend and revoke invitations
9. Change a member's role
10. Remove a member
11. Transfer ownership

- [ ] **Step 4: Final commit (only if fixes were made in steps 1-3)**

```bash
git add -u
git commit -m "fix: resolve integration test issues from team management feature"
```
