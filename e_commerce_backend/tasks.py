from celery import shared_task

@shared_task
def sample_task(param1, param2):
    return f"Tasks completed with {param1} and {param2}"
