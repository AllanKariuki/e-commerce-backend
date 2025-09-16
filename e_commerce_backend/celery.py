import os
from celery import Celery

#Set the default django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'e_commerce_backend.settings')

#Create the celery app
app = Celery('e_commerce_backend')

app.config_from_object('django.conf:settings', namespace='CELERY')

# Autodiscover tasks from Django apps and explicitly include the main project tasks
app.autodiscover_tasks()

# Explicitly include tasks from the main project module
app.autodiscover_tasks(['e_commerce_backend'])
