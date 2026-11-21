from django.core.cache import cache
from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import EVENT_LIST_KEY
from .models import Event


@receiver([post_save, post_delete], sender=Event)
def clear_event_list_cache(sender, **kwargs):
    transaction.on_commit(lambda: cache.delete(EVENT_LIST_KEY))