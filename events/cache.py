from django.core.cache import cache

EVENT_LIST_TTL = 60  # seconds, a safety net if an invalidation is ever missed
EVENT_LIST_VERSION_KEY = "events:list:version"


def event_list_key(page, size):
    version = cache.get(EVENT_LIST_VERSION_KEY, 1)
    return f"events:list:v{version}:p{page}:s{size}"


def invalidate_event_list():
    cache.add(EVENT_LIST_VERSION_KEY, 1, None)
    cache.incr(EVENT_LIST_VERSION_KEY)