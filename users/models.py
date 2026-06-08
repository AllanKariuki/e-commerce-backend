from django.db import models
from django.contrib.auth.models import (
    AbstractBaseUser,
    BaseUserManager,
    PermissionsMixin,
)


class UserManager(BaseUserManager):
    """
    Custom manager so `email` is the natural login identifier instead of
    `username`. SimpleJWT calls into `create_user` / `create_superuser`
    via management commands and tests, so both must exist.
    """

    use_in_migrations = True

    def _create_user(self, email, password, **extra_fields):
        if not email:
            raise ValueError("Users must have an email address")
        email = self.normalize_email(email)
        # `username` is REQUIRED on this model so SimpleJWT and the admin
        # still have a non-email handle to show in lists. Default it from
        # the email local-part if the caller didn't supply one.
        extra_fields.setdefault("username", email.split("@", 1)[0])
        user = self.model(email=email, **extra_fields)
        if password:
            user.set_password(password)
        else:
            # Keycloak-imported / OAuth users never had a Django password.
            # Mark them unusable so password-login can't accidentally succeed.
            user.set_unusable_password()
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", False)
        extra_fields.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra_fields)

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        if extra_fields.get("is_staff") is not True:
            raise ValueError("Superuser must have is_staff=True.")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Superuser must have is_superuser=True.")
        return self._create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):
    """
    Custom user model for TryOn.ke.

    Pre-2026-05-21 this was a plain `models.Model` populated from Keycloak
    JWTs (see legacy `KeycloakTokenAuthentication`). We're swapping to
    `djangorestframework-simplejwt` for MVP auth, so the model now extends
    `AbstractBaseUser` + `PermissionsMixin` to plug into Django's auth
    machinery (admin, `request.user.is_authenticated`, password hashing,
    `check_password`, etc.).

    `keycloak_id` is kept (nullable) so any rows synced from Keycloak in
    earlier dev sessions don't have to be discarded — they just won't be
    able to password-login until reset.
    """

    # Legacy / forward-compat identifiers.
    keycloak_id = models.CharField(
        max_length=255, unique=True, null=True, blank=True
    )

    # Login identifier. Unique + indexed for fast lookup on every JWT verify.
    email = models.EmailField(unique=True)

    # `username` stays present but is no longer the login key — useful as a
    # display name and for admin search.
    username = models.CharField(max_length=255)

    first_name = models.CharField(max_length=255, blank=True)
    last_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)

    # Required by Django's auth framework / admin.
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    EMAIL_FIELD = "email"
    REQUIRED_FIELDS = ["username"]

    def __str__(self):
        return self.email or self.username

    def get_full_name(self):
        full = f"{self.first_name} {self.last_name}".strip()
        return full or self.username

    def get_short_name(self):
        return self.first_name or self.username


class GuestSession(models.Model):
    """
    Tracks anonymous shoppers via cookie so cart/recent-views/try-on quota
    survive without forcing an account. See `GuestCookieMiddleware`.
    """

    session_id = models.CharField(max_length=38, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "guest_sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"Guest {self.session_id[:8]}... {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"

    @property
    def is_expired(self):
        """Guest sessions expire after a year of inactivity."""
        from django.utils import timezone
        from datetime import timedelta

        return self.last_activity < timezone.now() - timedelta(days=365)
