from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .cache import invalidate_event_list
from .models import Event


@receiver([post_save, post_delete], sender=Event)
def clear_event_list_cache(sender, **kwargs):
    transaction.on_commit(invalidate_event_list)