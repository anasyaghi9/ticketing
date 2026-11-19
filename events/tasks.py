from celery import shared_task

from .services import expire_holds


@shared_task
def release_expired_holds():
    count = expire_holds()
    return f"expired {count} holds"