from django.db import models

# Create your models here.
class User(models.Model):
    keycloak_id = models.CharField(max_length=255, unique=True, null=True, blank=True)
    username = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    first_name = models.CharField(max_length=255)
    last_name = models.CharField(max_length=255)
    phone = models.CharField(max_length=20)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return self.username

class GuestSession(models.Model):
    """
    Model to track guest sessions without creating full user records.
    Stores minimal information about guest identification
    """

    session_id = models.CharField(max_length=38, unique=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    last_activity = models.DateTimeField(auto_now=True)
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.TextField(null=True, blank=True)

    class Meta:
        db_table = "guest_sessions"
        ordering = ['-created_at']

    def __str__(self):
        return f"Guest {self.session_id[:8]}... {self.created_at.strftime('%Y-%m-%d %H:%M:%S')}"
    
    @property
    def is_expired(self):
        """Check if the guest session is expired (e.g., after 30 days)"""
        from django.utils import timezone
        from datetime import timedelta
        return self.last_activity < timezone.now() - timedelta(days=365)
    