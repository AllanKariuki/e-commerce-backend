from django.apps import AppConfig


class ProductsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'products'

    def ready(self):
        # Importing connects the @receiver decorators in signals.py.
        # Local import keeps Django from trying to resolve models too early.
        from products import signals  # noqa: F401
