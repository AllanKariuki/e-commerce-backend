from django.core.management.base import BaseCommand
from django.core.cache import cache

class Command(BaseCommand):
    help = 'Test Redis connection'

    def handle(self, *args, **options):
        try:
            # Test cache
            cache.set('test_key', 'test_value', 30)
            result = cache.get('test_key')
            
            if result == 'test_value':
                self.stdout.write(
                    self.style.SUCCESS('✅ Redis connection successful!')
                )
                self.stdout.write(f'Retrieved value: {result}')
            else:
                self.stdout.write(
                    self.style.ERROR('❌ Redis test failed - value mismatch')
                )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'❌ Redis connection failed: {e}')
            )