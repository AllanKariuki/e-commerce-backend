# from celery import shared_task

# @shared_task
# def sample_task(param1, param2):
#     return f"Tasks completed with {param1} and {param2}"


import logging
from celery import shared_task
from django.core.mail import send_mail
from django.conf import settings
from datetime import datetime
from orders.models import Order, OrderItem
from products.models import Product

# Simple test task to verify Celery connection
@shared_task
def test_celery():
    """
    Simple task to verify Celery is working.
    Logs a message and returns a success string.
    """
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    logging.info(f"Test task executed at {current_time}")
    return f"Celery test task completed successfully at {current_time}"

    